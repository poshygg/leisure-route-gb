"""가중치 학습 — pairwise margin ranking (ADR-003).

정답셋 : 두루누비 GPX 284코스(positive) vs 같은 OD의 최단경로(negative).
         전문가가 P를 고르고 최단이 Q라는 사실 자체가 라벨입니다.

파라미터가 10개뿐이라 scipy로 충분합니다. PyTorch 불필요.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

MARGIN = 0.05


def route_score(epath, lengths: np.ndarray, phi: np.ndarray, w: np.ndarray) -> float:
    """경로의 길이가중 평균 amenity. 길이 정규화가 없으면 긴 경로가 무조건 이깁니다."""
    if len(epath) == 0:
        return 0.0
    l = lengths[epath]
    return float((l @ (phi[epath] @ w)) / l.sum()) if l.sum() else 0.0


def _project(raw: np.ndarray) -> np.ndarray:
    """w ≥ 0, Σw = 1 로 사영. 식별성을 확보합니다."""
    w = np.abs(raw)
    s = w.sum()
    return w / s if s > 0 else np.full_like(w, 1.0 / len(w))


def fit_weights(
    pairs: list[tuple[list[int], list[int]]],
    lengths: np.ndarray,
    phi: np.ndarray,
    margin: float = MARGIN,
) -> tuple[np.ndarray, float]:
    """(positive_epath, negative_epath) 쌍들로부터 w를 학습.

    Returns
    -------
    (w, final_loss)
    """
    k = phi.shape[1]

    def loss(raw: np.ndarray) -> float:
        w = _project(raw)
        d = np.array([
            route_score(p, lengths, phi, w) - route_score(q, lengths, phi, w)
            for p, q in pairs
        ])
        return float(np.maximum(0.0, margin - d).mean())

    res = minimize(loss, x0=np.ones(k) / k, method="Nelder-Mead",
                   options={"maxiter": 4000, "xatol": 1e-5, "fatol": 1e-7})
    return _project(res.x), float(res.fun)


def pairwise_accuracy(pairs, lengths, phi, w) -> float:
    """학습된 w가 전문가 경로를 최단경로보다 높게 매기는 비율."""
    if not pairs:
        return 0.0
    hits = sum(
        route_score(p, lengths, phi, w) > route_score(q, lengths, phi, w)
        for p, q in pairs
    )
    return hits / len(pairs)
