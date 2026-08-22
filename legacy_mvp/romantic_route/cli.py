# -*- coding: utf-8 -*-
"""낭만 경로 탐색기 — CLI.

  python -m romantic_route.cli --from "경복궁" --to "창덕궁" --query "꽃 보면서 조용히"
  python -m romantic_route.cli --from "안동역" --loop 40 --query "강변 따라 걷고 싶어"
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from typing import Optional, Tuple

for _stream in (sys.stdout, sys.stderr):     # Windows cp949 대비
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

import networkx as nx
import osmnx as ox

from . import explain, features, intent, layers, pbf, routing
from .config import AXES, active_axes


def _resolve(q: str) -> Tuple[float, float]:
    """'37.57,126.98' 또는 지명 -> (lat, lon)."""
    if "," in q:
        try:
            a, b = q.split(",", 1)
            return float(a.strip()), float(b.strip())
        except ValueError:
            pass
    return ox.geocoder.geocode(q)


def _nearest(Gp, latlon):
    import pyproj
    from shapely.geometry import Point
    from shapely.ops import transform

    tf = pyproj.Transformer.from_crs(4326, Gp.graph["crs"], always_xy=True).transform
    p = transform(tf, Point(latlon[1], latlon[0]))
    return ox.distance.nearest_nodes(Gp, p.x, p.y)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="낭만 경로 탐색기 — 좋은 것들을 지나는 도보 경로를 찾는다")
    ap.add_argument("--from", dest="origin", required=True, help="출발지 (지명 또는 lat,lon)")
    ap.add_argument("--to", dest="dest", help="도착지 (지명 또는 lat,lon)")
    ap.add_argument("--loop", type=float, metavar="MIN",
                    help="산책 모드: 출발지로 돌아오는 N분 코스")
    ap.add_argument("--query", default="", help='자연어 요청. 예: "꽃 보면서 조용히 걷고 싶어"')
    ap.add_argument("--axes", nargs="+", metavar="KEY",
                    help=f"버튼 모드. 선택: {', '.join(AXES)}")
    ap.add_argument("--llm", action="store_true", help="Claude로 자연어 파싱 (실패 시 사전 폴백)")
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--strength", type=float, help="회피 강도 수동 지정 (기본: 질의에서 추론)")
    ap.add_argument("--k", type=int, default=3, help="후보 경로 수")
    ap.add_argument("--dem", help="경사 계산용 DEM GeoTIFF (국토지리정보원 5m DEM)")
    ap.add_argument("--pbf", help="로컬 .osm.pbf 경로. 주면 Overpass 대신 이걸 쓴다 "
                                  "(경북처럼 넓은 지역엔 사실상 필수)")
    ap.add_argument("--month", type=int, help="계절 게이트용 월 (기본: 오늘)")
    ap.add_argument("--pad", type=int, default=900, help="탐색 반경 여유(m)")
    ap.add_argument("--out", default="route.html")
    ap.add_argument("--list-axes", action="store_true")
    args = ap.parse_args(argv)

    if args.list_axes:
        for k, ax in AXES.items():
            season = ("상시" if not ax.months
                      else "/".join(f"{m}월" for m in ax.months))
            print(f"  {k:<10s} {ax.label:<14s} [{season}]\n             {ax.note}")
        return 0

    if not args.dest and not args.loop:
        ap.error("--to 또는 --loop 중 하나는 필요하다")

    month = args.month or _dt.date.today().month

    # ---- 1. 의도 파싱 -----------------------------------------------------
    print("\n[1/5] 의도 파싱")
    if args.axes:
        weights, strength = intent.from_buttons(args.axes)
        summary = " + ".join(AXES[k].label for k in weights)
        source = "buttons"
    else:
        weights, strength, summary, source = intent.parse(
            args.query or "나무 많고 조용한 길", use_llm=args.llm, model=args.model)
    if args.strength is not None:
        strength = args.strength

    print(f"    입력: {args.query or '(' + ', '.join(args.axes or []) + ')'}")
    print(f"    파서: {source}   회피강도: {strength}")
    print(f"    해석: {summary}")

    requested = list(weights)
    act, dropped = active_axes(month, requested)
    if args.dem is None and "gentle" in act:
        act.remove("gentle")
        dropped["gentle"] = "DEM 미지정 (--dem 으로 국토지리정보원 5m DEM 을 주면 활성화)"
    for k, why in dropped.items():
        print(f"    [-] {k} 제외: {why}")
    if not act:
        print("    활성 축이 없다. 기본 조합으로 대체한다.")
        act, weights = ["trees", "quiet"], {"trees": 0.5, "quiet": 0.5}
    weights = {k: weights[k] for k in act}
    tot = sum(weights.values())
    weights = {k: v / tot for k, v in weights.items()}   # 재분배

    # ---- 2. 그래프 --------------------------------------------------------
    print("\n[2/5] 보행 네트워크 로드")
    o_ll = _resolve(args.origin)
    if args.dest:
        d_ll = _resolve(args.dest)
        center = ((o_ll[0] + d_ll[0]) / 2, (o_ll[1] + d_ll[1]) / 2)
        span = ox.distance.great_circle(o_ll[0], o_ll[1], d_ll[0], d_ll[1])
        radius = int(span / 2 + args.pad)
    else:
        d_ll, center = None, o_ll
        radius = int(args.loop * routing.WALK_M_PER_MIN / 2 * 1.3 + 400)

    print(f"    중심 {center[0]:.5f}, {center[1]:.5f}   반경 {radius:,}m")
    prefetched = None
    if args.pbf:
        print(f"    로컬 PBF: {args.pbf}  (Overpass 미사용)")
        Gp, prefetched = pbf.load_region(args.pbf, center, radius,
                                         list(weights), AXES)
        boundary = None
    else:
        Gp, boundary = features.load_walk_graph(center=center, dist_m=radius)
    print(f"    노드 {Gp.number_of_nodes():,}  간선 {Gp.number_of_edges():,}")
    if Gp.number_of_edges() == 0:
        print("    보행망이 비어 있다. 중심/반경을 확인하라.")
        return 1

    if args.dem:
        print(f"    DEM 적용: {args.dem}")
        if not features.add_elevation(Gp, args.dem) and "gentle" in weights:
            weights.pop("gentle")
            tot = sum(weights.values()) or 1.0
            weights = {k: v / tot for k, v in weights.items()}

    edges = ox.graph_to_gdfs(Gp, nodes=False, edges=True)
    edges_index = list(edges.index)

    # ---- 3. 레이어 --------------------------------------------------------
    print("\n[3/5] 피처 수집 + 링크별 점수")
    if prefetched is not None:
        feats = prefetched
        for k, f in feats.items():
            ax = AXES[k]
            if not (ax.point_tags or ax.area_tags):
                print(f"    {ax.label:12s} 내재 속성 — 링크에서 직접 계산")
            else:
                print(f"    {ax.label:12s} 피처 {len(f['points'])+len(f['areas']):>6,}건  "
                      f"(점 {len(f['points']):,} / 면·선 {len(f['areas']):,})")
    else:
        feats = features.fetch_all(boundary, edges.crs, list(weights))
    scores, diag = layers.compute_scores(edges, feats, list(weights))

    print()
    usable = []
    for k in list(weights):
        d = diag.get(k, {"usable": True, "coverage": 0, "good_frac": 0, "reason": ""})
        mark = "OK " if d["usable"] else "[-]"
        print(f"    {mark} {AXES[k].label:<12s} 커버리지 {d['coverage']:5.1%}  "
              f"쓸만한 간선 {d['good_frac']:5.1%}")
        if d["usable"]:
            usable.append(k)
        else:
            print(f"        -> 제외: {d['reason']}")

    if not usable:
        print()
        print("    이 지역 데이터로 유도 가능한 축이 하나도 없다.")
        print("    범위를 넓히거나(--pad), 다른 축을 골라보라. "
              "(--list-axes 로 목록 확인)")
        return 1

    if len(usable) < len(weights):
        tot = sum(weights[k] for k in usable)
        weights = {k: weights[k] / tot for k in usable}
        print("    가중치 재분배: " +
              ", ".join(f"{AXES[k].label} {v:.0%}" for k, v in weights.items()))

    routing.attach_costs(Gp, edges_index, scores, weights, strength)

    # ---- 4. 경로 ----------------------------------------------------------
    print("\n[4/5] 경로 탐색")
    orig = _nearest(Gp, o_ll)
    if args.loop:
        r = routing.find_loop(Gp, orig, args.loop, weights)
        if r is None:
            print("    예산 안에 회귀 코스를 못 찾았다. --loop 값을 늘려보라.")
            return 1
        cands, baseline = [r], None
    else:
        dest = _nearest(Gp, d_ll)
        try:
            baseline = nx.shortest_path_length(Gp, orig, dest, weight="length")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            print("    두 지점이 보행망으로 연결되지 않는다.")
            return 1
        ok, shared = routing.diversity_feasible(Gp, orig, dest)
        if not ok:
            print(f"    [!] 이 구간은 보행망에 대안 경로가 없다 "
                  f"(최단경로와 {shared:.0%} 일치).")
            print(f"        간선 {Gp.number_of_edges():,}개 — 어떤 가중치를 줘도 같은 길이 나온다.")
            print(f"        데이터 문제가 아니라 망 밀도 문제다. 도심 쪽으로 옮기거나 "
                  f"--loop 산책 모드를 써보라.")
        cands = routing.k_routes(Gp, orig, dest, k=args.k, penalty=2.0)
        print(f"    최단거리 기준선 {baseline/1000:.2f} km · 후보 {len(cands)}개")

    stats = routing.rank([routing.evaluate(Gp, r, weights, baseline) for r in cands])

    # ---- 5. 출력 ----------------------------------------------------------
    print("\n[5/5] 결과\n")
    show = list(weights)
    for i, st in enumerate(stats, 1):
        geom = explain.route_geometry(Gp, st.nodes)
        named = explain.nearby_named(geom, feats, show)
        print(explain.describe(i, st, weights, named))
        print()

    path = explain.make_map(Gp, stats, edges.crs, args.out, feats, show)
    print(f"지도 저장: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
