# -*- coding: utf-8 -*-
"""경북 시군 OSM 피처 밀도 census. 한 줄씩 즉시 flush."""
import sys, time, warnings
for st in (sys.stdout, sys.stderr):
    if hasattr(st, "reconfigure"): st.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
import osmnx as ox
ox.settings.use_cache = True
ox.settings.requests_timeout = 90

TAGS = [
    ("가로수",   {"natural": "tree"}),
    ("공원·정원", {"leisure": ["park", "garden"]}),
    ("숲",       {"landuse": "forest", "natural": "wood"}),
    ("문화재",   {"historic": True}),
    ("공공미술", {"tourism": "artwork"}),
    ("하천·수역", {"waterway": ["river", "stream", "canal"], "natural": "water"}),
]

SITES = [
    ("서울 종로(기준)", (37.5735, 126.9788)),
    ("포항 시청",       (36.0190, 129.3435)),
    ("포항 영일대",     (36.0570, 129.3780)),
    ("경주 황리단길",   (35.8360, 129.2100)),
    ("안동 하회마을",   (36.5390, 128.5180)),
    ("구미 시청",       (36.1195, 128.3445)),
]
R = 1500

print(f"반경 {R}m OSM 피처 건수 (경북 대상 타당성 점검)\n", flush=True)
print(f"{'지역':16s}" + "".join(f"{n:>9s}" for n, _ in TAGS) + f"{'보행간선':>9s}", flush=True)
print("-" * 76, flush=True)

for label, pt in SITES:
    cells = []
    for _, tags in TAGS:
        try:
            g = ox.features_from_point(pt, tags, dist=R)
            cells.append(0 if g is None else len(g))
        except Exception:
            cells.append(0)
        time.sleep(0.4)
    try:
        G = ox.graph_from_point(pt, dist=R, network_type="walk", simplify=True)
        e = G.number_of_edges()
    except Exception:
        e = 0
    print(f"{label:16s}" + "".join(f"{c:>9,}" for c in cells) + f"{e:>9,}", flush=True)
print("\ndone", flush=True)
