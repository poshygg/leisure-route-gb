# -*- coding: utf-8 -*-
"""데모 재현용 고정 픽스처 생성 → demos/data/

협업 저장소는 보행망 CSV(149만 간선)를 git에 안 올리고 OSM에서 재생성하는
정책인데, OSM은 매일 바뀌므로 재생성본은 동일 결과를 보장하지 않는다.
그래서 두 데모의 bbox 합집합만 잘라낸 스냅샷(2026-08-23 기준)을 이 저장소에
커밋한다. 특징 CSV 4종도 같은 시점 사본을 동봉해 단일 clone 재현이 되게 한다.

실행에는 gyeongbuk-scenic-route 체크아웃이 필요하다 (BELT_DATA 환경변수 가능).
"""
from __future__ import annotations

import math
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import importlib.util

spec = importlib.util.spec_from_file_location("bd", ROOT / "scripts" / "20_belt_demo.py")
bd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bd)

OUT = ROOT / "demos" / "data"
(OUT / "network").mkdir(parents=True, exist_ok=True)

# 20_belt_demo와 동일한 bbox 계산 (README 재현 커맨드의 두 데모)
DEMOS = [
    ((35.7482, 129.4768), (35.7444, 129.4919)),   # 감은사지 → 문무대왕릉
    ((36.0567, 129.3785), (36.0335, 129.3650)),   # 영일대 → 죽도시장
    ((35.8380, 129.2100), (35.8290, 129.2270)),   # 대릉원 → 동궁과 월지 (서버 기본)
]
PAD = 1200

nodes = pd.read_csv(bd.BELT / "network/nodes.csv")
edges = pd.read_csv(bd.BELT / "network/edges.csv")

keep = pd.Series(False, index=nodes.index)
for o, d in DEMOS:
    lat0, lon0 = (o[0] + d[0]) / 2, (o[1] + d[1]) / 2
    span = math.dist(bd._TF.transform(o[1], o[0]), bd._TF.transform(d[1], d[0]))
    r = span / 2 + PAD
    dlat = r / 111_000
    dlon = r / (111_000 * np.cos(np.radians(lat0)))
    keep |= nodes.lat.between(lat0 - dlat, lat0 + dlat) & \
            nodes.lon.between(lon0 - dlon, lon0 + dlon)

sel = nodes[keep]
ids = set(sel.id)
esel = edges[edges.u.isin(ids) & edges.v.isin(ids)]
sel.to_csv(OUT / "network/nodes.csv", index=False)
esel.to_csv(OUT / "network/edges.csv", index=False)
print(f"network: 노드 {len(sel):,}  간선 {len(esel):,}")

for f in ("heritage_belt_mapped.csv", "coastline_belt.csv", "parks_belt.csv"):
    shutil.copy2(bd.BELT / f, OUT / f)
    print("copy:", f)
shutil.copy2(bd.BELT / "network/industrial.csv", OUT / "network/industrial.csv")
print("copy: network/industrial.csv")
print(f"\n완료 → {OUT}  (재현: python scripts/20_belt_demo.py ... --data demos/data)")
