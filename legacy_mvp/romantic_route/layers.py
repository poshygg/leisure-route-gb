# -*- coding: utf-8 -*-
"""링크(간선)별 축 점수 계산. 모든 출력은 0.0~1.0, 1.0 = 최고."""

from __future__ import annotations

from typing import Dict

import geopandas as gpd
import numpy as np
import pandas as pd

from .config import AXES, DERIVED, GRADE_COMFORT, QUIET_BY_HIGHWAY, QUIET_DEFAULT

# 길이로 정규화하는 축(100m당 밀도) vs 버퍼 내 총개수로 보는 축
DENSITY_AXES = {"flower", "trees"}
COUNT_AXES = {"heritage", "art"}


def _first(val):
    """OSM 태그는 리스트로 올 때가 있다."""
    if isinstance(val, list):
        return val[0] if val else None
    return val


# ---------------------------------------------------------------------------
# 공간 집계
# ---------------------------------------------------------------------------
def _buffers(edges: gpd.GeoDataFrame, radius: float) -> gpd.GeoDataFrame:
    # edges 는 (u, v, key) MultiIndex 다. eid 와 정렬하려면 인덱스를 눕혀야 한다.
    geom = edges.geometry.buffer(radius).reset_index(drop=True)
    return gpd.GeoDataFrame(
        {"eid": np.arange(len(edges))}, geometry=geom, crs=edges.crs)


def _count_in_buffer(edges, points, areas, radius) -> np.ndarray:
    """버퍼 안의 피처 개수. 면 피처는 '겹치면 1건'으로 센다."""
    counts = np.zeros(len(edges))
    buf = _buffers(edges, radius)

    if points is not None and not points.empty:
        hit = gpd.sjoin(points[["geometry"]], buf, predicate="within", how="inner")
        if not hit.empty:
            agg = hit.groupby("eid").size()
            counts[agg.index.to_numpy()] += agg.to_numpy()

    if areas is not None and not areas.empty:
        hit = gpd.sjoin(areas[["geometry"]], buf, predicate="intersects", how="inner")
        if not hit.empty:
            agg = hit.groupby("eid").size()
            counts[agg.index.to_numpy()] += agg.to_numpy()

    return counts


def score_count(edges, points, areas, radius, saturate, density: bool) -> np.ndarray:
    counts = _count_in_buffer(edges, points, areas, radius)
    if density:
        length = np.maximum(edges["length"].to_numpy(dtype=float), 20.0)
        value = counts / length * 100.0          # 100m당 개수
    else:
        value = counts
    return np.clip(value / max(saturate, 1e-6), 0.0, 1.0)


def score_near(edges, points, areas, decay_m) -> np.ndarray:
    """가장 가까운 피처까지의 거리 -> 선형 감쇠."""
    frames = [g[["geometry"]] for g in (points, areas)
              if g is not None and not g.empty]
    if not frames:
        return np.zeros(len(edges))

    target = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True),
                              geometry="geometry", crs=edges.crs)
    left = edges[["geometry"]].reset_index(drop=True)
    joined = gpd.sjoin_nearest(left, target, how="left", distance_col="_d")
    # sjoin_nearest 는 동거리 타이에서 행이 늘어날 수 있다 -> 최소값만 취한다
    dist = joined.groupby(joined.index)["_d"].min().reindex(range(len(edges)))
    dist = dist.fillna(np.inf).to_numpy(dtype=float)
    return np.clip(1.0 - dist / max(decay_m, 1e-6), 0.0, 1.0)


# ---------------------------------------------------------------------------
# 내재 속성
# ---------------------------------------------------------------------------
def score_quiet(edges) -> np.ndarray:
    hw = edges["highway"].map(_first) if "highway" in edges else pd.Series([None] * len(edges))
    base = hw.map(lambda h: QUIET_BY_HIGHWAY.get(h, QUIET_DEFAULT)).to_numpy(dtype=float)

    if "lanes" in edges.columns:
        def _lanes(v):
            try:
                f = float(_first(v))
            except (TypeError, ValueError):
                return 1.0
            return 1.0 if not np.isfinite(f) else f   # float('nan') 은 예외를 안 낸다
        lanes = edges["lanes"].map(_lanes).to_numpy(dtype=float)
        base = base * np.clip(1.0 - (lanes - 2.0) * 0.08, 0.35, 1.0)

    return np.clip(np.nan_to_num(base, nan=QUIET_DEFAULT), 0.0, 1.0)


def score_skyview(edges, buildings, radius) -> np.ndarray:
    """건물 점유율의 역수로 SVF 근사. 진짜 SVF는 3D 반구 적분이 필요하다."""
    if buildings is None or buildings.empty:
        return np.full(len(edges), 0.85)     # 건물 없음 = 대체로 트여 있음

    b = buildings[["geometry"]].copy()
    b["_area"] = b.geometry.area
    b = b[b["_area"] > 0]
    if b.empty:
        return np.full(len(edges), 0.85)
    b["geometry"] = b.geometry.centroid       # 중심점 기준 집계(속도)

    buf = _buffers(edges, radius)
    buf_area = buf.geometry.area.to_numpy(dtype=float)

    hit = gpd.sjoin(b, buf, predicate="within", how="inner")
    occupied = np.zeros(len(edges))
    if not hit.empty:
        agg = hit.groupby("eid")["_area"].sum()
        occupied[agg.index.to_numpy()] = agg.to_numpy()

    coverage = np.clip(occupied / np.maximum(buf_area, 1.0), 0.0, 1.0)
    return np.clip(1.0 - coverage * 1.8, 0.0, 1.0)


def score_gentle(edges) -> np.ndarray:
    col = "grade_abs" if "grade_abs" in edges.columns else (
        "grade" if "grade" in edges.columns else None)
    if col is None:
        return np.full(len(edges), 0.5)

    grade = np.abs(pd.to_numeric(edges[col], errors="coerce").fillna(0.0).to_numpy()) * 100.0
    xs = [0.0] + [g for g, _ in GRADE_COMFORT]
    ys = [1.0] + [s for _, s in GRADE_COMFORT]
    return np.clip(np.interp(grade, xs, ys, left=1.0, right=GRADE_COMFORT[-1][1]), 0.0, 1.0)


# ---------------------------------------------------------------------------
# 적응 정규화 + 사용가능성 게이트
# ---------------------------------------------------------------------------
MIN_GOOD_FRAC = 0.03      # 점수 >= 0.3 인 간선이 이 비율은 되어야 경로를 유도할 수 있다
GOOD_THRESH = 0.30
HI_PCTL = 85              # 이 지역 상위 15% 를 '만점'으로 본다


def adaptive_rescale(raw: np.ndarray, key: str) -> np.ndarray:
    """절대 saturate 상수 대신 '이 지역의 실제 분포'로 다시 스케일한다.

    왜 필요한가: OSM 가로수 태깅 밀도는 지역마다 10배 이상 차이 난다.
    서울 기준 saturate 를 포항에 그대로 쓰면 전 구간이 0점 근처로 뭉개지고,
    비용이 사실상 균일해져서 최단경로와 같은 답이 나온다(= 라우팅 무력화).
    """
    nz = raw[raw > 0]
    if nz.size == 0:
        return raw
    hi = float(np.percentile(nz, HI_PCTL))
    if hi <= 0:
        return raw
    return np.clip(raw / hi, 0.0, 1.0)


def diagnose(score: np.ndarray, key: str, fetch_failed: bool = False) -> dict:
    """축이 실제로 간선을 구분할 수 있는지 판정."""
    if fetch_failed:
        return {"usable": False, "coverage": 0.0, "good_frac": 0.0,
                "reason": "피처 조회 실패"}
    coverage = float((score > 0).mean())
    good = float((score >= GOOD_THRESH).mean())
    spread = float(np.percentile(score, 95) - np.percentile(score, 50))
    if good < MIN_GOOD_FRAC:
        return {"usable": False, "coverage": coverage, "good_frac": good,
                "reason": f"쓸만한 간선이 {good:.1%}뿐 (기준 {MIN_GOOD_FRAC:.0%}) "
                          f"— 이 지역 데이터로는 경로를 유도할 수 없다"}
    if spread < 0.02:
        return {"usable": False, "coverage": coverage, "good_frac": good,
                "reason": "점수가 거의 균일해 간선을 구분하지 못한다"}
    return {"usable": True, "coverage": coverage, "good_frac": good, "reason": ""}


# ---------------------------------------------------------------------------
# 오케스트레이션
# ---------------------------------------------------------------------------
def compute_scores(edges: gpd.GeoDataFrame,
                   feats: Dict[str, Dict[str, gpd.GeoDataFrame]],
                   axes_needed):
    """(scores, diag) 반환. diag 로 축의 사용가능성을 호출부에 알린다."""
    scores: Dict[str, np.ndarray] = {}
    diag: Dict[str, dict] = {}

    for key in axes_needed:
        ax = AXES[key]
        if ax.kind == "derived":
            continue
        f = feats.get(key)
        if f is None:                                  # 조회 실패
            scores[key] = np.zeros(len(edges))
            diag[key] = diagnose(scores[key], key, fetch_failed=True)
            continue
        pts, areas = f.get("points"), f.get("areas")

        if ax.kind == "count":
            scores[key] = score_count(edges, pts, areas, ax.buffer_m, ax.saturate,
                                      density=key in DENSITY_AXES)
        elif ax.kind == "near":
            scores[key] = score_near(edges, pts, areas, ax.buffer_m)
        elif key == "quiet":
            scores[key] = score_quiet(edges)
        elif key == "skyview":
            scores[key] = score_skyview(edges, areas, ax.buffer_m)
        elif key == "gentle":
            scores[key] = score_gentle(edges)

        # 피처 기반 축만 재스케일. 내재축(quiet/gentle)은 이미 절대 의미가 있다.
        if ax.kind in ("count", "near"):
            scores[key] = adaptive_rescale(scores[key], key)
        diag[key] = diagnose(scores[key], key)

    # 파생축은 다른 축 점수의 조합 (없는 축은 중립 0.5 로 대체)
    for key in axes_needed:
        if AXES[key].kind != "derived":
            continue
        acc = np.zeros(len(edges))
        for src, w in DERIVED[key].items():
            acc += w * scores.get(src, _fallback_score(edges, feats, src))
        scores[key] = np.clip(acc, 0.0, 1.0)
        diag[key] = diagnose(scores[key], key)

    return scores, diag


def _fallback_score(edges, feats, key) -> np.ndarray:
    """파생축이 요구하는데 사용자가 선택하지 않은 축을 즉석 계산."""
    ax = AXES[key]
    f = feats.get(key)
    if not f:                       # None(실패) 또는 미수집
        return np.full(len(edges), 0.5)
    if ax.kind == "count":
        return score_count(edges, f["points"], f["areas"], ax.buffer_m,
                           ax.saturate, density=key in DENSITY_AXES)
    if ax.kind == "near":
        return score_near(edges, f["points"], f["areas"], ax.buffer_m)
    if key == "skyview":
        return score_skyview(edges, f["areas"], ax.buffer_m)
    return np.full(len(edges), 0.5)
