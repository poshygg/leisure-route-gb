# -*- coding: utf-8 -*-
"""비용 합성 -> 최단경로 -> 대안 경로 -> 다양성 재정렬."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import networkx as nx
import numpy as np

from .config import AXES

WALK_M_PER_MIN = 75.0        # 4.5 km/h


# ---------------------------------------------------------------------------
# 1. 비용 부여
# ---------------------------------------------------------------------------
def attach_costs(Gp, edges_index, scores: Dict[str, np.ndarray],
                 weights: Dict[str, float], strength: float) -> None:
    """cost(e) = length(e) * (1 + strength * deficit(e)).

    deficit in [0,1] 이므로 cost >= length 가 항상 성립한다.
    -> A* 직선거리 휴리스틱이 admissible 하게 유지된다. (할인 배수를 쓰면 깨진다)
    """
    active = {k: w for k, w in weights.items() if k in scores}
    tot = sum(active.values()) or 1.0
    active = {k: w / tot for k, w in active.items()}

    deficit = np.zeros(len(edges_index))
    for k, w in active.items():
        deficit += w * (1.0 - scores[k])
    deficit = np.clip(deficit, 0.0, 1.0)

    for i, (u, v, key) in enumerate(edges_index):
        d = Gp[u][v][key]
        length = float(d.get("length", 1.0))
        d["ambience_cost"] = length * (1.0 + strength * float(deficit[i]))
        d["ambience_deficit"] = float(deficit[i])
        d["axis_scores"] = {k: float(scores[k][i]) for k in active}


# ---------------------------------------------------------------------------
# 2. 경로 탐색
# ---------------------------------------------------------------------------
def _best_parallel_edge(G, u, v):
    """평행 간선 중 비용이 가장 싼 것."""
    return min(G[u][v].items(), key=lambda kv: kv[1].get("ambience_cost", float("inf")))


def route_edges(G, route: List[int]):
    out = []
    for u, v in zip(route[:-1], route[1:]):
        key, data = _best_parallel_edge(G, u, v)
        out.append((u, v, key, data))
    return out


def k_routes(Gp, orig: int, dest: int, k: int = 3, penalty: float = 2.0) -> List[List[int]]:
    """반복 페널티 방식으로 서로 다른 경로 k개. (nx.shortest_simple_paths 는 너무 느리다)"""
    for _, _, _, d in Gp.edges(keys=True, data=True):
        d["_pen"] = d.get("ambience_cost", d.get("length", 1.0))

    routes: List[List[int]] = []
    seen = set()
    for _ in range(k * 2):
        if len(routes) >= k:
            break
        try:
            r = nx.shortest_path(Gp, orig, dest, weight="_pen")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            break
        sig = tuple(r)
        if sig not in seen:
            seen.add(sig)
            if not _too_similar(Gp, r, routes, thresh=0.80):
                routes.append(r)
        for u, v in zip(r[:-1], r[1:]):
            for key in Gp[u][v]:
                Gp[u][v][key]["_pen"] *= penalty
    return routes


def _edge_set(route):
    return {frozenset((u, v)) for u, v in zip(route[:-1], route[1:])}


def _too_similar(G, cand, existing, thresh=0.80) -> bool:
    cs = _edge_set(cand)
    for r in existing:
        rs = _edge_set(r)
        if not cs or not rs:
            continue
        if len(cs & rs) / len(cs | rs) > thresh:
            return True
    return False


def find_loop(Gp, start: int, minutes: float, weights: Dict[str, float]) -> Optional[List[int]]:
    """산책(회귀) 모드: 예산의 절반 거리에서 분위기가 가장 좋은 지점을 찍고 왕복.

    (엄밀한 최적 순환은 Orienteering Problem = NP-hard. 여기선 그 완화판이다.)
    """
    budget_m = minutes * WALK_M_PER_MIN
    half = budget_m / 2.0

    dist = nx.single_source_dijkstra_path_length(Gp, start, cutoff=half * 1.15, weight="length")
    band = [n for n, d in dist.items() if half * 0.75 <= d <= half * 1.15]
    if not band:
        return None

    amb = nx.single_source_dijkstra_path_length(Gp, start, cutoff=half * 1.4,
                                                weight="ambience_cost")
    # 실제거리 대비 분위기비용이 가장 낮은 = 가는 길이 가장 예쁜 지점
    target = min(band, key=lambda n: amb.get(n, float("inf")) / max(dist[n], 1.0))

    out = nx.shortest_path(Gp, start, target, weight="ambience_cost")
    for u, v in zip(out[:-1], out[1:]):
        for key in Gp[u][v]:
            Gp[u][v][key]["_pen"] = Gp[u][v][key]["ambience_cost"] * 3.0
    for _, _, _, d in Gp.edges(keys=True, data=True):
        d.setdefault("_pen", d["ambience_cost"])

    try:
        back = nx.shortest_path(Gp, target, start, weight="_pen")
    except nx.NetworkXNoPath:
        back = list(reversed(out))
    return out + back[1:]


# ---------------------------------------------------------------------------
# 3. 평가 + 다양성 재정렬
# ---------------------------------------------------------------------------
@dataclass
class RouteStats:
    nodes: List[int]
    length_m: float
    minutes: float
    quality: float                       # 0~1, 가중 평균 점수
    axis_means: Dict[str, float] = field(default_factory=dict)
    variety: float = 0.0                 # 0~1, 지배축 시퀀스의 엔트로피
    detour: float = 1.0                  # 최단거리 대비 배수
    score: float = 0.0


def evaluate(Gp, route: List[int], weights: Dict[str, float],
             baseline_m: Optional[float] = None) -> RouteStats:
    eds = route_edges(Gp, route)
    lengths = np.array([float(d.get("length", 0.0)) for *_, d in eds])
    total = float(lengths.sum())

    axis_means, dominant = {}, []
    keys = [k for k in weights if k in (eds[0][3].get("axis_scores") or {})] if eds else []

    for k in keys:
        vals = np.array([d["axis_scores"].get(k, 0.0) for *_, d in eds])
        axis_means[k] = float(np.average(vals, weights=np.maximum(lengths, 1e-6)))

    for *_, d in eds:
        s = d.get("axis_scores") or {}
        if s:
            dominant.append(max(s, key=lambda k: s[k] * weights.get(k, 0.0)))

    variety = 0.0
    if dominant:
        _, cnt = np.unique(dominant, return_counts=True)
        p = cnt / cnt.sum()
        ent = -(p * np.log(p)).sum()
        variety = float(ent / math.log(len(keys))) if len(keys) > 1 else 0.0

    quality = sum(weights.get(k, 0.0) * v for k, v in axis_means.items())
    quality /= (sum(weights.get(k, 0.0) for k in axis_means) or 1.0)

    return RouteStats(
        nodes=route, length_m=total, minutes=total / WALK_M_PER_MIN,
        quality=float(quality), axis_means=axis_means, variety=variety,
        detour=(total / baseline_m) if baseline_m else 1.0,
    )


def rank(stats: List[RouteStats], variety_bonus: float = 0.15,
         detour_penalty: float = 0.20) -> List[RouteStats]:
    """좋음의 총량 + 변화 - 우회비용.

    '좋은 길은 좋은 게 많은 길이 아니라 변하는 길'이라서 variety 를 넣는다.
    variety 는 링크 속성이 아니라 경로 전체의 속성이라 Dijkstra 로는 못 넣는다
    -> 후보를 뽑아놓고 여기서 재정렬한다.
    """
    for s in stats:
        s.score = (s.quality
                   + variety_bonus * s.variety
                   - detour_penalty * max(0.0, s.detour - 1.0))
    return sorted(stats, key=lambda s: -s.score)


def diversity_feasible(Gp, orig: int, dest: int) -> Tuple[bool, float]:
    """이 구간에 애초에 '선택지'가 존재하는가.

    안동 하회~병산 검증에서 드러난 실패 유형: 축은 전부 usable 인데 보행망 간선이
    806개뿐이라 우회로 자체가 없다. 어떤 가중치를 줘도 같은 길이 나온다.
    데이터 게이트로는 못 잡는다 — 데이터가 아니라 그래프의 문제이기 때문이다.

    반환: (대안 있음?, 최단경로와의 공유율)
    """
    try:
        sp = nx.shortest_path(Gp, orig, dest, weight="length")
        amb = nx.shortest_path(Gp, orig, dest, weight="ambience_cost")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return False, 1.0
    a, b = _edge_set(sp), _edge_set(amb)
    shared = len(a & b) / max(len(a), 1)
    return shared < 0.98, shared
