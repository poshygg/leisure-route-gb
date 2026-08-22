"""Scorer 계약 검증. 새 스코어러를 만들면 여기에 최소 2개를 추가하세요."""
import numpy as np
import pytest

from leisure_route.scoring import REGISTRY, get
from leisure_route.scoring.base import NotImplementedScorer, Scorer


def test_registry_covers_ten_attributes():
    assert len(REGISTRY) == 10


def test_get_unknown_raises():
    with pytest.raises(KeyError):
        get("nope")


def test_normalize_is_bounded():
    x = np.array([0.0, 1.0, 5.0, 100.0])
    out = Scorer.normalize(x)
    assert out.min() >= 0.0 and out.max() <= 1.0


def test_normalize_handles_all_zero():
    out = Scorer.normalize(np.zeros(5))
    assert np.all(out == 0.0)


def test_decay_monotonic():
    d = np.array([0.0, 50.0, 200.0])
    out = Scorer.decay(d, 50.0)
    assert out[0] > out[1] > out[2]
    assert out[0] == pytest.approx(1.0)


def test_validate_rejects_out_of_range():
    class Bad(Scorer):
        name = "bad"
        def score(self, edges):
            return np.array([1.5])

    with pytest.raises(ValueError):
        Bad().validate(np.array([1.5]), 1)


def test_not_implemented_scorer_returns_zeros():
    class Dummy(NotImplementedScorer):
        name = "dummy"

    edges = list(range(7))
    assert Dummy().score(edges).shape == (7,)
