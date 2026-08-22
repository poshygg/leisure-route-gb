"""스코어러 인터페이스 — 공동작업의 계약.

10가지 속성이 각각 독립된 Scorer 하나입니다. 이 인터페이스만 지키면
다른 사람 코드를 볼 필요가 없습니다.

    class MyScorer(Scorer):
        name = "my"
        def score(self, edges) -> np.ndarray:   # (M,) in [0, 1]
            ...

규칙 (CONTRIBUTING.md 참조):
  - 출력은 반드시 shape (len(edges),) 이고 값이 [0, 1] 안에 있어야 합니다.
  - 거리·버퍼 연산은 CRS_METRIC(EPSG:5179)로 변환 후 수행하세요 (ADR-005).
  - 상한이 애매하면 분위수 클리핑을 쓰세요. normalize() 헬퍼가 있습니다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import geopandas as gpd
import numpy as np

from ..config import CRS_METRIC


class Scorer(ABC):
    """엣지 GeoDataFrame → [0,1] 점수 배열."""

    name: str = "base"
    #: 이 스코어러가 필요로 하는 data/ 하위 파일들. 없으면 skip 처리됩니다.
    requires: tuple[str, ...] = ()

    @abstractmethod
    def score(self, edges: gpd.GeoDataFrame) -> np.ndarray:
        """(M,) float in [0, 1] 을 반환."""

    # --- 헬퍼 ---

    @staticmethod
    def to_metric(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """거리 연산용 투영 (ADR-005)."""
        return gdf.to_crs(CRS_METRIC)

    @staticmethod
    def normalize(x: np.ndarray, q: float = 0.95) -> np.ndarray:
        """분위수 클리핑 후 [0,1] 정규화. 이상치에 강건합니다."""
        x = np.nan_to_num(np.asarray(x, dtype=float), nan=0.0)
        hi = np.quantile(x, q) if np.any(x > 0) else 1.0
        if hi <= 0:
            return np.zeros_like(x)
        return np.clip(x / hi, 0.0, 1.0)

    @staticmethod
    def decay(dist_m: np.ndarray, scale: float = 50.0) -> np.ndarray:
        """거리 감쇠 exp(-d/scale). 근접성 기반 속성의 공통 형태."""
        return np.exp(-np.asarray(dist_m, dtype=float) / scale)

    def validate(self, out: np.ndarray, n: int) -> np.ndarray:
        if out.shape != (n,):
            raise ValueError(f"[{self.name}] shape {out.shape} != ({n},)")
        if not np.all((out >= 0) & (out <= 1)):
            raise ValueError(f"[{self.name}] 값이 [0,1] 범위를 벗어남")
        return out

    def __call__(self, edges: gpd.GeoDataFrame) -> np.ndarray:
        return self.validate(self.score(edges), len(edges))


class NotImplementedScorer(Scorer):
    """아직 아무도 안 맡은 스코어러. 0을 반환해 파이프라인은 돌아가게 합니다."""

    def score(self, edges: gpd.GeoDataFrame) -> np.ndarray:
        return np.zeros(len(edges))
