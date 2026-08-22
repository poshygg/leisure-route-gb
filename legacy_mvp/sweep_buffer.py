# -*- coding: utf-8 -*-
"""버퍼 반경 민감도 + 면적비 모드 비교. 경주/포항 캐시 사용."""
import sys, warnings
for st in (sys.stdout, sys.stderr):
    if hasattr(st, "reconfigure"): st.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

import geopandas as gpd, networkx as nx, numpy as np, osmnx as ox, pyproj
from shapely.geometry import Point
from shapely.ops import transform, unary_union
from romantic_route import layers, pbf, routing
from romantic_route.config import AXES

PBF = "data/south-korea-latest.osm.pbf"
CASES = [("경주", (35.8375,129.2095), (35.8340,129.2255)),
         ("포항", (36.0190,129.3435), (36.0335,129.3650))]
AX = ["trees","heritage","quiet"]


def area_ratio(edges, areas, radius):
    """면적비 모드: 버퍼 면적 중 피처 폴리곤이 차지하는 비율."""
    if areas is None or areas.empty:
        return np.zeros(len(edges))
    polys = areas[areas.geometry.geom_type.isin(["Polygon","MultiPolygon"])]
    if polys.empty:
        return np.zeros(len(edges))
    u = unary_union(polys.geometry.values)
    buf = edges.geometry.buffer(radius)
    inter = buf.intersection(u).area.to_numpy()
    return np.clip(inter / np.maximum(buf.area.to_numpy(), 1.0), 0.0, 1.0)


for label, O, D in CASES:
    center = ((O[0]+D[0])/2, (O[1]+D[1])/2)
    radius = int(ox.distance.great_circle(O[0],O[1],D[0],D[1])/2 + 900)
    Gp, feats = pbf.load_region(PBF, center, radius, AX, AXES)
    edges = ox.graph_to_gdfs(Gp, nodes=False, edges=True); idx = list(edges.index)
    tf = pyproj.Transformer.from_crs(4326, Gp.graph["crs"], always_xy=True).transform
    orig = ox.distance.nearest_nodes(Gp, *transform(tf, Point(O[1],O[0])).coords[0])
    dest = ox.distance.nearest_nodes(Gp, *transform(tf, Point(D[1],D[0])).coords[0])
    base = nx.shortest_path_length(Gp, orig, dest, weight="length")
    quiet = layers.score_quiet(edges)

    print(f"\n{'='*92}\n{label}   간선 {len(edges):,}   문화재 "
          f"{len(feats['heritage']['points'])+len(feats['heritage']['areas'])}건\n{'='*92}")

    for key in ("heritage", "trees"):
        f = feats[key]
        print(f"\n[{AXES[key].label}] 점 계열(count) — 버퍼 민감도")
        print(f"  {'버퍼':>6} | {'good%':>6} | {'spread':>7} | {'std':>6} | "
              f"{'품질':>6} | {'우회':>5} | {'최단과공유':>8}")
        print("  " + "-"*70)
        for r in (50, 100, 200, 300, 500, 800):
            raw = layers.score_count(edges, f["points"], f["areas"], r,
                                     AXES[key].saturate, density=(key=="trees"))
            sc = layers.adaptive_rescale(raw, key)
            good = (sc >= 0.30).mean()
            spread = np.percentile(sc,95) - np.percentile(sc,50)
            W = {key:0.5, "quiet":0.5}
            routing.attach_costs(Gp, idx, {key:sc, "quiet":quiet}, W, 2.0)
            rt = nx.shortest_path(Gp, orig, dest, weight="ambience_cost")
            st = routing.evaluate(Gp, rt, W, base)
            sp = nx.shortest_path(Gp, orig, dest, weight="length")
            sh = len(routing._edge_set(rt)&routing._edge_set(sp))/max(len(routing._edge_set(sp)),1)
            print(f"  {r:>5}m | {good:>5.1%} | {spread:>7.3f} | {sc.std():>6.3f} | "
                  f"{st.quality:>6.3f} | {st.detour:>5.2f}x | {sh:>7.0%}")

    print(f"\n[나무 그늘] 면적비(area-ratio) 모드 — count 모드와 비교")
    print(f"  {'버퍼':>6} | {'good%':>6} | {'spread':>7} | {'std':>6} | {'평균 면적비':>9}")
    print("  " + "-"*54)
    for r in (100, 200, 300, 500):
        ar = area_ratio(edges, feats["trees"]["areas"], r)
        sc = layers.adaptive_rescale(ar, "trees")
        print(f"  {r:>5}m | {(sc>=0.30).mean():>5.1%} | "
              f"{np.percentile(sc,95)-np.percentile(sc,50):>7.3f} | {sc.std():>6.3f} | "
              f"{ar.mean():>8.3f}")
