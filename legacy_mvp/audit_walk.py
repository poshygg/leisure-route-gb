# -*- coding: utf-8 -*-
"""'걸을 수 있는 길'의 근거를 감사한다: sidewalk / foot 태그가 실제로 얼마나 붙어 있나."""
import sys, collections, warnings
for st in (sys.stdout, sys.stderr):
    if hasattr(st, "reconfigure"): st.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
import osmium
from romantic_route.pbf import WALK_EXCLUDE

PBF = "data/south-korea-latest.osm.pbf"
BOXES = {  # (w, s, e, n)
    "포항 시청권": (129.325, 36.005, 129.380, 36.045),
    "경주 도심":   (129.195, 35.822, 129.240, 35.850),
}

stat = {k: collections.Counter() for k in BOXES}
coord = {k: set() for k in BOXES}

# 패스 A: bbox 노드 id
for n in osmium.FileProcessor(PBF, osmium.osm.NODE):
    loc = n.location
    if not loc.valid():
        continue
    for k, (w, s, e, nn) in BOXES.items():
        if w <= loc.lon <= e and s <= loc.lat <= nn:
            coord[k].add(n.id)

# 패스 B: highway way 감사
for way in osmium.FileProcessor(PBF, osmium.osm.WAY):
    t = dict(way.tags)
    hw = t.get("highway")
    if not hw or hw in WALK_EXCLUDE:
        continue
    refs = [nd.ref for nd in way.nodes]
    for k in BOXES:
        if not any(r in coord[k] for r in refs):
            continue
        c = stat[k]
        c["총 way"] += 1
        if hw in ("footway", "path", "pedestrian", "steps", "living_street"):
            c["보행 전용 (footway/path/…)"] += 1
        else:
            c["차도 계열"] += 1
            if "sidewalk" in t:
                c["  └ sidewalk 태그 있음"] += 1
                if t["sidewalk"] in ("both", "left", "right", "yes", "separate"):
                    c["      └ 인도 있음 명시"] += 1
                elif t["sidewalk"] == "no":
                    c["      └ 인도 없음 명시"] += 1
        if "foot" in t:
            c["foot 태그 있음"] += 1

for k, c in stat.items():
    print(f"\n=== {k} ===")
    tot = c["총 way"] or 1
    for label in ["총 way", "보행 전용 (footway/path/…)", "차도 계열",
                  "  └ sidewalk 태그 있음", "      └ 인도 있음 명시",
                  "      └ 인도 없음 명시", "foot 태그 있음"]:
        print(f"  {label:32s} {c[label]:>6,}  {c[label]/tot:6.1%}")
