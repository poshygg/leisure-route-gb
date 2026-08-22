"""④ 강변 — 하천 중심선 근접도.

데이터 : OSM waterway=river|stream|canal (Geofabrik 한국 추출본)
         보완 — 국가하천망 (국가공간정보포털)
방법   : d = 엣지 중점 → 최근접 하천 중심선 거리(m),  score = exp(-d / 50)
함정   : - 복개천은 waterway=river 인데 지상에서 물이 안 보입니다.
           tunnel=yes / covered=yes 를 제외하세요.
         - 대형 하천은 제방 때문에 50m 안이어도 물이 안 보일 수 있습니다.
우선순위: ★ MVP 1순위. 강변은 조용·하늘·나무·발편함을 동시에 만족시킵니다 (ADR-004).
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np

from ..config import INTERIM
from .base import Scorer

DECAY_M = 50.0


class RiverScorer(Scorer):
    name = "river"
    requires = ("interim/waterways.gpkg",)

    def __init__(self, waterways: gpd.GeoDataFrame | None = None):
        self._w = waterways

    def _load(self) -> gpd.GeoDataFrame:
        if self._w is not None:
            return self._w
        path = INTERIM / "waterways.gpkg"
        if not path.exists():
            raise FileNotFoundError(f"{path} 없음 — scripts/01_fetch_data.py 먼저 실행")
        w = gpd.read_file(path)
        # 복개천 제외
        for col in ("tunnel", "covered"):
            if col in w.columns:
                w = w[w[col].isna() | (w[col] == "no")]
        return w

    def score(self, edges: gpd.GeoDataFrame) -> np.ndarray:
        w = self.to_metric(self._load())
        e = self.to_metric(edges)
        pts = e.geometry.interpolate(0.5, normalized=True)
        joined = gpd.GeoDataFrame(geometry=pts, crs=e.crs).sjoin_nearest(
            w[["geometry"]], how="left", distance_col="_d"
        )
        d = joined.groupby(level=0)["_d"].min().reindex(range(len(e))).to_numpy()
        return self.decay(np.nan_to_num(d, nan=1e9), DECAY_M)
