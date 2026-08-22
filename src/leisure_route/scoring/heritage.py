"""② 문화재 — 국가유산 폴리곤 인접도.

데이터 : 국가유산청_문화재 공간 정보 (data.go.kr 3070426)  ← SHP 다운로드
         약 15,000종 지정국가유산. 좌표 + 면적 + 규제범위 폴리곤 + 유형.
방법   : 등급 가중 버퍼와 엣지의 교차 길이 비율
         score = Σ_유산 (등급가중 × 교차길이) / 엣지길이,  분위수 정규화
함정   : ★ 착수 전 반드시 확인할 것 2개 (docs/01_data_sources.md)
         1) 좌표계 — .prj 확인 후 EPSG:4326 변환. 국내 TM 계열일 가능성 높음.
         2) geometry 타입 분포 — 15,000종 전부가 폴리곤은 아닐 수 있습니다.
            점만 있는 건 등급별 고정 반경으로 폴백 버퍼를 씌우세요.
왜 SHP : 문화재는 점이 아니라 면입니다. 경복궁을 점으로 두면 담장 따라 걷는 1.5km가
         "문화재 0개"로 계산됩니다. TourAPI(점)로는 이 계산이 성립하지 않습니다.
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np

from ..config import INTERIM
from .base import Scorer

# 등급별 가중치와 폴백 버퍼 반경(m) — 폴리곤이 없는 경우에만 반경 사용
# 종목명은 2024 국가유산 체계 개편 후 명칭 기준 (옛 명칭은 데이터에 더 이상 없음)
GRADE = {
    "국보":           (1.0, 300),
    "보물":           (0.8, 150),
    "사적":           (0.9, 300),
    "국가민속문화유산": (0.6, 100),
    "시도유형문화유산": (0.5, 80),
    "시도민속문화유산": (0.5, 80),
    "시도기념물":     (0.4, 80),
    "문화유산자료":   (0.3, 50),
    "국가등록문화유산": (0.3, 50),
    "시도등록문화유산": (0.3, 50),
}
DEFAULT = (0.3, 50)
# ⛔ 특징 사용 금지 종목 — 점수에 절대 넣지 않는다.
#    명승은 검증 정답(앵커)이라 넣는 순간 AUC가 무의미해지고 (docs/04 누출 방지),
#    자연유산(천연기념물·시도자연유산)은 v1 뷰포인트 전용이다 (scripts/01b 분류 규칙).
FORBIDDEN = {"명승", "천연기념물", "시도자연유산"}
VIEW_BUFFER_M = 80.0  # 폴리곤 경계로부터 "보이는" 거리


class HeritageScorer(Scorer):
    name = "heritage"
    requires = ("interim/heritage.gpkg",)

    def __init__(self, heritage: gpd.GeoDataFrame | None = None):
        self._h = heritage

    def _load(self) -> gpd.GeoDataFrame:
        if self._h is not None:
            return self._h
        path = INTERIM / "heritage.gpkg"
        if not path.exists():
            raise FileNotFoundError(f"{path} 없음 — scripts/01_fetch_data.py 먼저 실행")
        h = gpd.read_file(path)
        if "grade" in h.columns:                      # 앵커·자연유산 누출 차단
            h = h[~h["grade"].astype(str).isin(FORBIDDEN)]
        return h

    def score(self, edges: gpd.GeoDataFrame) -> np.ndarray:
        h = self.to_metric(self._load())
        e = self.to_metric(edges).reset_index(drop=True)

        # 폴리곤은 경계에서 VIEW_BUFFER, 점은 등급별 반경으로 버퍼
        def _buf(row):
            w, r = GRADE.get(str(row.get("grade", "")), DEFAULT)
            return row.geometry.buffer(VIEW_BUFFER_M if row.geometry.geom_type
                                       in ("Polygon", "MultiPolygon") else r)

        h = h.assign(geometry=h.apply(_buf, axis=1))
        h["_w"] = h.get("grade", "").map(lambda g: GRADE.get(str(g), DEFAULT)[0])

        lengths = e.geometry.length.to_numpy()
        acc = np.zeros(len(e))
        ov = gpd.overlay(
            e[["geometry"]].assign(_i=range(len(e))),
            h[["geometry", "_w"]], how="intersection", keep_geom_type=False,
        )
        if len(ov):
            ov["_c"] = ov.geometry.length * ov["_w"]
            agg = ov.groupby("_i")["_c"].sum()
            acc[agg.index.to_numpy()] = agg.to_numpy()

        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where(lengths > 0, acc / lengths, 0.0)
        return self.normalize(ratio)
