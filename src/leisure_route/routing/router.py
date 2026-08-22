"""경로 탐색 — λ 격자 스윕 Dijkstra.

    cost(e) = length(e) / (1 + λ · A(e)),   A(e) = Σ wᵢ · scoreᵢ(e) ∈ [0,1]
    제약    : length(route) ≤ β · length(shortest)

왜 나눗셈인가 : length·(1-λA) 는 음수가 될 수 있고 Dijkstra는 음수 가중치에서 깨집니다.
                나눗셈은 항상 양수이고 해석도 자연스럽습니다 —
                A=1, λ=1 이면 "이 길 1m는 0.5m처럼 느껴진다".

왜 격자 스윕인가 (ADR-002) : λ → 우회율이 엄밀히 단조가 아니라 이분 탐색의 전제가
                깨집니다. 24점 스윕이면 단조성 가정 없이 정확하고, 최단/균형/여유
                3옵션을 같은 스윕에서 공짜로 얻습니다.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import igraph as ig
import numpy as np

from ..config import DETOUR_PRESETS, LAMBDA_GRID


@dataclass
class RouteResult:
    epath: list[int]        # 엣지 인덱스 열
    length_m: float
    baseline_m: float       # 최단경로 길이
    amenity: float          # 길이가중 평균 A
    lam: float

    @property
    def detour_ratio(self) -> float:
        return self.length_m / self.baseline_m if self.baseline_m else 1.0


class Router:
    """스코어링이 끝난 그래프 위에서 경로를 찾습니다.

    Parameters
    ----------
    graph  : igraph.Graph (무방향). 엣지 순서가 lengths / phi 의 행 순서와 일치해야 합니다.
    lengths: (M,) 엣지 길이 [m]
    phi    : (M, K) 속성 점수 행렬, 각 열이 [0,1]. 열 순서는 config.SCORE_COLS.
    """

    def __init__(self, graph: ig.Graph, lengths: np.ndarray, phi: np.ndarray):
        if len(graph.es) != len(lengths) or len(lengths) != phi.shape[0]:
            raise ValueError("graph / lengths / phi 의 엣지 수가 일치하지 않습니다")
        self.g = graph
        self.L = np.asarray(lengths, dtype=float)
        self.PHI = np.asarray(phi, dtype=float)

    # --- 내부 ---

    def _path(self, src: int, dst: int, cost: np.ndarray) -> list[int]:
        # 도달 불가는 정상적인 경우(빈 경로)로 처리하므로 igraph 경고는 억제합니다.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            out = self.g.get_shortest_paths(src, dst, weights=list(cost), output="epath")
        return out[0] if out else []

    def _amenity(self, epath: list[int], A: np.ndarray) -> float:
        if not epath:
            return 0.0
        l = self.L[epath]
        return float((l @ A[epath]) / l.sum()) if l.sum() else 0.0

    # --- 공개 API ---

    def route(
        self,
        src: int,
        dst: int,
        w: np.ndarray,
        beta: float = 1.25,
        lam_grid: np.ndarray | None = None,
    ) -> RouteResult:
        """우회 예산 beta 안에서 amenity가 최대인 경로."""
        A = np.clip(self.PHI @ np.asarray(w, dtype=float), 0.0, 1.0)

        p0 = self._path(src, dst, self.L)
        if not p0:
            raise ValueError(f"{src} → {dst} 경로 없음 (그래프가 끊겨 있습니다)")
        L0 = float(self.L[p0].sum())

        if lam_grid is None:
            lam_grid = np.linspace(*LAMBDA_GRID)

        best = RouteResult(p0, L0, L0, self._amenity(p0, A), 0.0)
        for lam in lam_grid:
            p = self._path(src, dst, self.L / (1.0 + lam * A))
            if not p:
                continue
            length = float(self.L[p].sum())
            if length > beta * L0:
                continue
            a = self._amenity(p, A)
            if a > best.amenity:
                best = RouteResult(p, length, L0, a, float(lam))
        return best

    def options(self, src: int, dst: int, w: np.ndarray) -> dict[str, RouteResult]:
        """최단 / 균형 / 여유 3안을 한 번에."""
        return {k: self.route(src, dst, w, beta=b) for k, b in DETOUR_PRESETS.items()}
