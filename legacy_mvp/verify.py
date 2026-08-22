# -*- coding: utf-8 -*-
"""검증: 분위기 가중치가 실제로 경로를 바꾸고 품질을 올리는가."""
import sys
for st in (sys.stdout, sys.stderr):
    if hasattr(st, "reconfigure"): st.reconfigure(encoding="utf-8")

import networkx as nx, osmnx as ox, numpy as np
from romantic_route import features, layers, routing
from romantic_route.cli import _resolve, _nearest

O, D = _resolve("경복궁, 서울"), _resolve("창덕궁, 서울")
center = ((O[0]+D[0])/2, (O[1]+D[1])/2)
Gp, boundary = features.load_walk_graph(center=center, dist_m=1600)
edges = ox.graph_to_gdfs(Gp, nodes=False, edges=True); idx = list(edges.index)

W = {"trees": 1/3, "heritage": 1/3, "quiet": 1/3}
feats  = features.fetch_all(boundary, edges.crs, list(W))
scores, diag = layers.compute_scores(edges, feats, list(W))
for k, d in diag.items():
    print(f"  {k:9s} usable={d['usable']}  cov={d['coverage']:.1%}  good={d['good_frac']:.1%}  {d['reason']}")

orig, dest = _nearest(Gp, O), _nearest(Gp, D)

# 기준선: 순수 최단
routing.attach_costs(Gp, idx, scores, W, strength=0.0)   # strength=0 -> cost == length
shortest = nx.shortest_path(Gp, orig, dest, weight="ambience_cost")
base_len = routing.evaluate(Gp, shortest, W).length_m

print(f"\n{'strength':>9} | {'거리':>8} | {'우회':>5} | {'품질':>6} | {'최단과 공유':>9} | 축별 (나무/문화재/조용)")
print("-" * 88)
for s in (0.0, 0.5, 1.0, 2.0, 4.0, 8.0):
    routing.attach_costs(Gp, idx, scores, W, strength=s)
    r  = nx.shortest_path(Gp, orig, dest, weight="ambience_cost")
    st = routing.evaluate(Gp, r, W, base_len)
    shared = len(routing._edge_set(r) & routing._edge_set(shortest)) / len(routing._edge_set(shortest))
    a = st.axis_means
    print(f"{s:>9.1f} | {st.length_m:>7.0f}m | {st.detour:>5.2f}x | {st.quality:>6.3f} | "
          f"{shared:>8.0%} | {a.get('trees',0):.2f} / {a.get('heritage',0):.2f} / {a.get('quiet',0):.2f}")

# NaN / 범위 검사
print("\n무결성 검사")
for k, v in scores.items():
    print(f"  {k:9s} min={v.min():.3f} max={v.max():.3f} mean={v.mean():.3f} "
          f"NaN={int(np.isnan(v).sum())} 범위이탈={int(((v<0)|(v>1)).sum())}")
costs = np.array([d["ambience_cost"] for *_, d in Gp.edges(keys=True, data=True)])
lens  = np.array([d.get("length",0.0) for *_, d in Gp.edges(keys=True, data=True)])
print(f"  cost >= length (A* admissible 조건): {bool((costs >= lens - 1e-9).all())}")
