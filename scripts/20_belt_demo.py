# -*- coding: utf-8 -*-
"""벨트 데이터 × MVP 엔진 데모.

gyeongbuk-scenic-route(협업 저장소)의 가공 데이터를 **읽기 전용**으로 불러와
romantic_route MVP의 라우팅 엔진(페널티 A*·k-경로·다양성 재정렬)과
새 UI(ui.make_ui_map)에 그대로 꽂는다. OSM 피처 → 공공데이터 교체 실증.

  python scripts/20_belt_demo.py --from 35.8442,129.4728 --to 35.8365,129.4890 \
      --out belt_demo.html
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "legacy_mvp"))
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

import networkx as nx
import pyproj
from scipy.spatial import cKDTree

from romantic_route import routing, ui
from romantic_route.config import AXES, Axis, QUIET_BY_HIGHWAY, QUIET_DEFAULT

# gyeongbuk-scenic-route 체크아웃의 data/processed 경로.
# 기본값: 이 저장소와 나란히 clone 된 위치. 다르면 BELT_DATA 환경변수로 지정.
import os
BELT = Path(os.environ.get(
    "BELT_DATA",
    Path(__file__).resolve().parents[2] / "gyeongbuk-scenic-route" / "data" / "processed"))
CRS = "EPSG:32652"          # UTM 52N — 벨트(동해안) 전역이 한 존에 들어간다
_TF = pyproj.Transformer.from_crs(4326, CRS, always_xy=True)

# 런타임 축 확장 — 저장소·MVP 코드 어느 쪽도 수정하지 않는다
AXES["coast"] = Axis(key="coast", label="해안", kind="near", buffer_m=300,
                     note="국립해양조사원 해안선(협업 저장소 가공본)")
AXES["parks"] = Axis(key="parks", label="공원", kind="near", buffer_m=250,
                     note="도시공원 표준데이터(협업 저장소 가공본)")
ui.AXIS_COLORS["coast"] = "#4a3aa7"
ui.AXIS_COLORS["parks"] = "#1baf7a"
# {조용함 #2a78d6, 문화재 #eda100, 해안 #4a3aa7, 공원 #1baf7a}
# → dataviz validate_palette.js all-pairs PASS (light)


def load_graph(center, radius_m):
    """벨트 보행망 CSV -> bbox 크롭 -> 투영 MultiGraph."""
    lat0, lon0 = center
    dlat = radius_m / 111_000
    dlon = radius_m / (111_000 * np.cos(np.radians(lat0)))

    nodes = pd.read_csv(BELT / "network/nodes.csv")
    sel = nodes[(nodes.lat.between(lat0 - dlat, lat0 + dlat))
                & (nodes.lon.between(lon0 - dlon, lon0 + dlon))]
    keep = set(sel.id)

    edges = pd.read_csv(BELT / "network/edges.csv")
    edges = edges[edges.u.isin(keep) & edges.v.isin(keep)]

    xs, ys = _TF.transform(sel.lon.values, sel.lat.values)
    G = nx.MultiGraph(crs=CRS)
    for nid, x, y in zip(sel.id, xs, ys):
        G.add_node(nid, x=float(x), y=float(y))
    for u, v, L, hw in zip(edges.u, edges.v, edges.length_m, edges.highway):
        G.add_edge(u, v, length=float(L), highway=(hw if isinstance(hw, str) else ""))

    # 최대 연결성분만 (섬 조각 제거)
    if G.number_of_nodes():
        cc = max(nx.connected_components(G), key=len)
        G = G.subgraph(cc).copy()
    return G


def _proj_pts(df, loncol, latcol):
    x, y = _TF.transform(df[loncol].values, df[latcol].values)
    return np.column_stack([x, y])


def load_features():
    """협업 저장소 가공 CSV -> (KDTree용 좌표, POI용 GeoDataFrame)."""
    import geopandas as gpd
    from shapely.geometry import Point

    her = pd.read_csv(BELT / "heritage_belt_mapped.csv", encoding="utf-8-sig")
    her = her[(her.has_coord == "Y") & her.longitude.gt(0)]
    her_xy = _proj_pts(her, "longitude", "latitude")

    coast = pd.read_csv(BELT / "coastline_belt.csv", encoding="utf-8-sig")
    coast_xy = _proj_pts(coast, "lon", "lat")

    parks = pd.read_csv(BELT / "parks_belt.csv", encoding="utf-8-sig")
    parks = parks[~parks.parkSe.isin(["어린이공원", "묘지공원"])]     # SPEC A7 규칙
    parks = parks.dropna(subset=["latitude", "longitude"])
    parks_xy = _proj_pts(parks, "longitude", "latitude")

    ind = pd.read_csv(BELT / "network/industrial.csv", encoding="utf-8-sig")
    ind_xy = _proj_pts(ind, "lon", "lat")

    def gdfp(xy, names):
        return gpd.GeoDataFrame({"name": list(names)},
                                geometry=[Point(*p) for p in xy], crs=CRS)

    feats_ui = {
        "heritage": {"points": gdfp(her_xy, her.ccbaMnm1), "areas": None},
        "parks":    {"points": gdfp(parks_xy, parks.parkNm), "areas": None},
        "coast":    {"points": None, "areas": None},
        "quiet":    {"points": None, "areas": None},
    }
    return {"her_xy": her_xy, "her_w": her.grade_w.values,
            "coast_xy": coast_xy, "parks_xy": parks_xy,
            "ind_xy": ind_xy}, feats_ui


def score_edges(Gp, raw):
    """간선 중점 기준 4축 점수 + 공단 감점."""
    edges_index, mids, hws, lens = [], [], [], []
    for u, v, key, d in Gp.edges(keys=True, data=True):
        edges_index.append((u, v, key))
        mids.append(((Gp.nodes[u]["x"] + Gp.nodes[v]["x"]) / 2,
                     (Gp.nodes[u]["y"] + Gp.nodes[v]["y"]) / 2))
        hws.append(d.get("highway", ""))
        lens.append(d["length"])
    mids = np.array(mids)

    def near_score(xy, decay):
        if len(xy) == 0:
            return np.zeros(len(mids))
        dist, _ = cKDTree(xy).query(mids)
        return np.exp(-dist / decay)

    # 문화재: 150m 내 등급가중 합, 3점이면 만점 (MVP heritage saturate=3 유지)
    hs = np.zeros(len(mids))
    if len(raw["her_xy"]):
        tree = cKDTree(raw["her_xy"])
        for i, m in enumerate(mids):
            idx = tree.query_ball_point(m, 150.0)
            hs[i] = min(1.0, raw["her_w"][idx].sum() / 3.0)

    quiet = np.array([QUIET_BY_HIGHWAY.get(h, QUIET_DEFAULT) for h in hws])
    # 공단 200m 이내면 조용함을 깎는다 (Z1 임시 대체 — SPEC 규칙)
    ind_pen = near_score(raw["ind_xy"], 200.0)
    quiet = np.clip(quiet - 0.6 * ind_pen, 0.0, 1.0)

    scores = {
        "heritage": hs,
        "coast": near_score(raw["coast_xy"], 300.0),
        "parks": near_score(raw["parks_xy"], 250.0),
        "quiet": quiet,
    }
    return edges_index, scores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="orig", required=True)
    ap.add_argument("--to", dest="dest", required=True)
    ap.add_argument("--axes", nargs="+",
                    default=["heritage", "coast", "parks", "quiet"])
    ap.add_argument("--strength", type=float, default=2.0)
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--pad", type=int, default=1200)
    ap.add_argument("--out", default="belt_demo.html")
    args = ap.parse_args()

    o = tuple(map(float, args.orig.split(",")))
    d = tuple(map(float, args.dest.split(",")))
    center = ((o[0] + d[0]) / 2, (o[1] + d[1]) / 2)
    import math
    span = math.dist(_TF.transform(o[1], o[0]), _TF.transform(d[1], d[0]))
    radius = span / 2 + args.pad

    print(f"[1/4] 벨트 보행망 로드 (반경 {radius:,.0f}m)")
    Gp = load_graph(center, radius)
    print(f"    노드 {Gp.number_of_nodes():,}  간선 {Gp.number_of_edges():,}")
    if Gp.number_of_edges() == 0:
        print("    보행망이 비어 있다."); return 1

    print("[2/4] 공공데이터 점수화 (읽기 전용)")
    raw, feats_ui = load_features()
    edges_index, scores = score_edges(Gp, raw)

    weights = {k: 1.0 / len(args.axes) for k in args.axes}
    excluded = [
        {"label": "하천", "reason": "rivers_belt.csv 빈 파일 — KRF 수령 전 (SPEC A3)"},
        {"label": "화목 가로수", "reason": "벨트 등재 3~4구간뿐 — 특징 유도 불가 (SPEC A6 blocked)"},
    ]
    for k in args.axes:
        good = float((scores[k] >= 0.3).mean())
        print(f"    {AXES[k].label:<8s} 쓸만한 간선 {good:5.1%}")
        if good < 0.03:
            excluded.append({"label": AXES[k].label,
                             "reason": f"쓸만한 간선 {good:.1%} (기준 3%)"})
            weights.pop(k)
    tot = sum(weights.values())
    weights = {k: v / tot for k, v in weights.items()}
    if len(weights) < len(args.axes):
        print("    가중치 재분배: " +
              ", ".join(f"{AXES[k].label} {v:.0%}" for k, v in weights.items()))

    routing.attach_costs(Gp, edges_index, scores, weights, args.strength)

    print("[3/4] 경로 탐색")
    node_xy = np.array([[Gp.nodes[n]["x"], Gp.nodes[n]["y"]] for n in Gp.nodes])
    node_ids = list(Gp.nodes)
    tree = cKDTree(node_xy)
    orig = node_ids[tree.query(_TF.transform(o[1], o[0]))[1]]
    dest = node_ids[tree.query(_TF.transform(d[1], d[0]))[1]]

    try:
        baseline_nodes = nx.shortest_path(Gp, orig, dest, weight="length")
        baseline = nx.path_weight(Gp, baseline_nodes, weight="length")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        print("    두 지점이 보행망으로 연결되지 않는다."); return 1
    ok, shared = routing.diversity_feasible(Gp, orig, dest)
    if not ok:
        print(f"    [!] 대안 경로 없음 (최단과 {shared:.0%} 일치) — 망 밀도 문제")
    cands = routing.k_routes(Gp, orig, dest, k=args.k)
    stats = routing.rank([routing.evaluate(Gp, r, weights, baseline) for r in cands])
    print(f"    기준선 {baseline/1000:.2f}km · 후보 {len(cands)}개")

    print("[4/4] UI 렌더")
    for i, st in enumerate(stats, 1):
        tops = " · ".join(f"{AXES[k].label} {v:.0%}"
                          for k, v in sorted(st.axis_means.items(),
                                             key=lambda x: -x[1]))
        print(f"    {i}위 {st.length_m/1000:.2f}km 우회 {st.detour:.2f}x "
              f"점수 {st.score:.3f} — {tops}")

    path = ui.make_ui_map(
        Gp, stats, CRS, args.out, feats=feats_ui, weights=weights,
        query="벨트 공공데이터 데모 — " + " + ".join(AXES[k].label for k in weights),
        summary="국가유산·해안선·도시공원·OSM 위계 (gyeongbuk-scenic-route 가공본, 읽기 전용)",
        baseline_nodes=baseline_nodes, excluded=excluded)
    print(f"지도 저장: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
