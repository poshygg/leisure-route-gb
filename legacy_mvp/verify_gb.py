# -*- coding: utf-8 -*-
"""경북 검증: (1) 분위기 라우팅이 실제로 우회하는가 (2) 시군별 데이터 충분한가."""
import sys, time, warnings
for st in (sys.stdout, sys.stderr):
    if hasattr(st, "reconfigure"): st.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

import networkx as nx, numpy as np, osmnx as ox
from romantic_route import layers, pbf, routing
from romantic_route.config import AXES

PBF = "data/south-korea-latest.osm.pbf"
W = {"trees": 1/3, "heritage": 1/3, "quiet": 1/3}

CASES = [
    ("경주 대릉원~월지", (35.8375, 129.2095), (35.8340, 129.2255)),
    ("포항 시청~죽도시장", (36.0190, 129.3435), (36.0335, 129.3650)),
    ("안동 하회~병산",    (36.5390, 128.5180), (36.5470, 128.5390)),
]

for label, O, D in CASES:
    print(f"\n{'='*84}\n{label}\n{'='*84}", flush=True)
    center = ((O[0]+D[0])/2, (O[1]+D[1])/2)
    span = ox.distance.great_circle(O[0], O[1], D[0], D[1])
    radius = int(span/2 + 900)
    t0 = time.time()
    try:
        Gp, feats = pbf.load_region(PBF, center, radius, list(W), AXES)
    except Exception as e:
        print(f"  로드 실패: {type(e).__name__}: {e}", flush=True); continue
    print(f"  노드 {Gp.number_of_nodes():,} 간선 {Gp.number_of_edges():,}  ({time.time()-t0:.0f}s)", flush=True)

    edges = ox.graph_to_gdfs(Gp, nodes=False, edges=True); idx = list(edges.index)
    scores, diag = layers.compute_scores(edges, feats, list(W))
    for k, d in diag.items():
        n = len(feats[k]["points"]) + len(feats[k]["areas"])
        print(f"  {AXES[k].label:<10s} 피처 {n:>5,}  usable={str(d['usable']):<5} "
              f"cov={d['coverage']:5.1%} good={d['good_frac']:5.1%} {d['reason']}", flush=True)

    use = [k for k in W if diag[k]["usable"]]
    if not use:
        print("  -> 사용 가능한 축 없음", flush=True); continue
    Wu = {k: 1/len(use) for k in use}

    import pyproj
    from shapely.geometry import Point
    from shapely.ops import transform
    tf = pyproj.Transformer.from_crs(4326, Gp.graph["crs"], always_xy=True).transform
    orig = ox.distance.nearest_nodes(Gp, *transform(tf, Point(O[1], O[0])).coords[0])
    dest = ox.distance.nearest_nodes(Gp, *transform(tf, Point(D[1], D[0])).coords[0])

    routing.attach_costs(Gp, idx, scores, Wu, 0.0)
    try:
        sp = nx.shortest_path(Gp, orig, dest, weight="ambience_cost")
    except Exception:
        print("  경로 없음", flush=True); continue
    base = routing.evaluate(Gp, sp, Wu).length_m

    print(f"\n  {'strength':>8} | {'거리':>7} | {'우회':>5} | {'품질':>6} | {'최단과공유':>8} | " +
          " / ".join(AXES[k].label for k in use), flush=True)
    print("  " + "-"*78, flush=True)
    for stg in (0.0, 1.0, 2.0, 4.0, 8.0):
        routing.attach_costs(Gp, idx, scores, Wu, stg)
        r = nx.shortest_path(Gp, orig, dest, weight="ambience_cost")
        st = routing.evaluate(Gp, r, Wu, base)
        sh = len(routing._edge_set(r) & routing._edge_set(sp)) / max(len(routing._edge_set(sp)), 1)
        vals = " / ".join(f"{st.axis_means.get(k,0):.2f}" for k in use)
        print(f"  {stg:>8.1f} | {st.length_m:>6.0f}m | {st.detour:>5.2f}x | "
              f"{st.quality:>6.3f} | {sh:>7.0%} | {vals}", flush=True)
