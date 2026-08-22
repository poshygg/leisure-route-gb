"""⑩ 발 편함 — 경사 + 노면 + 계단.

데이터 : 국토지리정보원 수치표고모델(DEM) 5m  +  OSM surface / highway=steps / sidewalk
방법   : slope_pen  = clip(|Δh / Δd| / 0.08, 0, 1)        # 8% 경사에서 최대 페널티
         surface_pen= {paved:0, asphalt:0, concrete:0.1, gravel:0.5, ground:0.6, sand:0.9}
         step_pen   = 1.0 if highway == steps else 0
         score      = 1 - clip(0.5*slope + 0.3*surface + 1.0*step, 0, 1)
함정   : - DEM 해상도가 5m라 짧은 엣지는 노이즈가 큽니다. 10m 미만 엣지는 이웃과 합치세요.
         - OSM surface 태그 누락률이 한국에서 높습니다. 결측은 도로위계로 추정하세요.
우선순위: ★ MVP. Valhalla의 use_hills / step_penalty 와 같은 역할을 자체 계산합니다.
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np

from .base import Scorer

SURFACE_PENALTY = {
    "paved": 0.0, "asphalt": 0.0, "concrete": 0.1, "paving_stones": 0.1,
    "compacted": 0.3, "fine_gravel": 0.4, "gravel": 0.5, "ground": 0.6,
    "dirt": 0.6, "grass": 0.7, "sand": 0.9,
}
MAX_SLOPE = 0.08  # 8%


class ComfortScorer(Scorer):
    name = "comfort"
    requires = ("processed/edges_with_elevation.gpkg",)

    def score(self, edges: gpd.GeoDataFrame) -> np.ndarray:
        n = len(edges)

        # 경사 — grade 컬럼(=Δh/Δd)이 이미 붙어 있다고 가정 (02_build_graph.py에서 부착)
        grade = np.abs(edges.get("grade", np.zeros(n)).to_numpy(dtype=float))
        slope_pen = np.clip(grade / MAX_SLOPE, 0.0, 1.0)

        # 노면
        surf = edges.get("surface", np.full(n, "")).astype(str).str.lower()
        surface_pen = surf.map(SURFACE_PENALTY).fillna(0.2).to_numpy()

        # 계단
        hw = edges.get("highway", np.full(n, "")).astype(str)
        step_pen = (hw == "steps").to_numpy(dtype=float)

        penalty = 0.5 * slope_pen + 0.3 * surface_pen + 1.0 * step_pen
        return 1.0 - np.clip(penalty, 0.0, 1.0)
