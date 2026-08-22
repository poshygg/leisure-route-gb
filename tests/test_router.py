"""Router — 합성 그래프로 검증. 외부 데이터 불필요."""
import igraph as ig
import numpy as np
import pytest

from leisure_route.routing import Router


@pytest.fixture
def toy():
    """0 →1→ 3 (짧고 밋밋)  /  0 →2→ 3 (길지만 예쁨)

        edge 0: 0-1  len 100  A 0.0
        edge 1: 1-3  len 100  A 0.0
        edge 2: 0-2  len 120  A 1.0
        edge 3: 2-3  len 120  A 1.0
    """
    g = ig.Graph(n=4, edges=[(0, 1), (1, 3), (0, 2), (2, 3)], directed=False)
    L = np.array([100.0, 100.0, 120.0, 120.0])
    PHI = np.array([[0.0], [0.0], [1.0], [1.0]])
    return Router(g, L, PHI)


def test_shortest_when_no_detour_allowed(toy):
    r = toy.route(0, 3, w=np.array([1.0]), beta=1.0)
    assert r.length_m == pytest.approx(200.0)
    assert r.amenity == pytest.approx(0.0)


def test_picks_pretty_route_within_budget(toy):
    r = toy.route(0, 3, w=np.array([1.0]), beta=1.3)
    assert r.length_m == pytest.approx(240.0)
    assert r.amenity == pytest.approx(1.0)
    assert r.detour_ratio == pytest.approx(1.2)
    assert r.lam > 0


def test_budget_is_respected(toy):
    """beta=1.1 이면 240m(=1.2배) 경로는 예산 초과라 선택되면 안 됩니다."""
    r = toy.route(0, 3, w=np.array([1.0]), beta=1.1)
    assert r.length_m <= 1.1 * r.baseline_m


def test_options_returns_three(toy):
    opts = toy.options(0, 3, w=np.array([1.0]))
    assert set(opts) == {"shortest", "balanced", "leisurely"}
    assert opts["shortest"].length_m <= opts["leisurely"].length_m


def test_shape_mismatch_raises():
    g = ig.Graph(n=2, edges=[(0, 1)], directed=False)
    with pytest.raises(ValueError):
        Router(g, np.array([1.0, 2.0]), np.zeros((2, 1)))


def test_disconnected_raises(toy):
    g = ig.Graph(n=3, edges=[(0, 1)], directed=False)
    r = Router(g, np.array([10.0]), np.zeros((1, 1)))
    with pytest.raises(ValueError):
        r.route(0, 2, w=np.array([1.0]))
