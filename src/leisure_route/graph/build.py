"""OSM 보행 네트워크 → igraph.  [부분 구현]

MVP는 시군 하나입니다 (ADR-004). 전국을 한 번에 하면 죽습니다.

주의 : 이 프로젝트의 3단계 게이트에서 실패하는 원인은 대부분 스코어링이 아니라
       **OSM 보행로 누락**입니다. 그래프를 만들자마자 연결성부터 확인하세요.
"""
from __future__ import annotations

import geopandas as gpd
import igraph as ig
import numpy as np

WALK_FILTER = (
    '["highway"]["area"!~"yes"]'
    '["highway"!~"motorway|motorway_link|trunk|trunk_link|construction|proposed"]'
    '["foot"!~"no"]["access"!~"private"]'
)


def build_pedestrian_graph(place: str):
    """osmnx로 보행 그래프를 내려받습니다.

    TODO: elevation 부착 (DEM 5m) → edges['grade'] 컬럼. ComfortScorer가 이걸 씁니다.
    """
    import osmnx as ox

    G = ox.graph_from_place(place, custom_filter=WALK_FILTER, simplify=True)
    return G


def to_igraph(edges: gpd.GeoDataFrame) -> tuple[ig.Graph, np.ndarray]:
    """엣지 GeoDataFrame → (igraph.Graph, lengths).

    엣지 순서가 lengths / phi 행 순서와 반드시 일치해야 합니다 (Router의 전제).
    """
    nodes = {n: i for i, n in enumerate(
        sorted(set(edges["u"]).union(set(edges["v"])))
    )}
    pairs = list(zip(edges["u"].map(nodes), edges["v"].map(nodes)))
    g = ig.Graph(n=len(nodes), edges=pairs, directed=False)
    lengths = edges["length_m"].to_numpy(dtype=float)
    return g, lengths


def connectivity_report(g: ig.Graph) -> dict:
    """게이트 점검용 — 최대 연결성분이 전체의 몇 %인가."""
    comps = g.connected_components()
    sizes = sorted((len(c) for c in comps), reverse=True)
    return {
        "nodes": g.vcount(),
        "edges": g.ecount(),
        "components": len(sizes),
        "largest_share": sizes[0] / g.vcount() if g.vcount() else 0.0,
    }
