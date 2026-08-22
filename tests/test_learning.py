"""가중치 학습 — 합성 데이터로 검증."""
import numpy as np

from leisure_route.learning import fit_weights, route_score
from leisure_route.learning.rank import pairwise_accuracy


def test_route_score_is_length_weighted():
    L = np.array([100.0, 300.0])
    PHI = np.array([[1.0], [0.0]])
    # 길이가중이면 100*1 / 400 = 0.25
    assert route_score([0, 1], L, PHI, np.array([1.0])) == 0.25


def test_fit_recovers_the_informative_attribute():
    """속성 0만 전문가 경로에서 높은 경우, w[0]가 가장 커야 합니다."""
    rng = np.random.default_rng(0)
    M = 60
    L = np.full(M, 100.0)
    PHI = rng.random((M, 3))
    PHI[:20, 0] = 0.95          # 엣지 0~19 = "좋은" 구간
    pairs = [([i, i + 1], [40 + i, 41 + i]) for i in range(0, 18, 2)]

    w, loss = fit_weights(pairs, L, PHI)
    assert w.sum() == np.float64(1.0).item() or abs(w.sum() - 1.0) < 1e-6
    assert np.all(w >= 0)
    assert w.argmax() == 0
    assert pairwise_accuracy(pairs, L, PHI, w) == 1.0
