# -*- coding: utf-8 -*-
"""OSM 보행 그래프 + 주변 피처 로드 (osmnx >= 2.0)."""

from __future__ import annotations

import warnings
from typing import Dict, Optional, Tuple

import geopandas as gpd
import osmnx as ox
from shapely.geometry import Polygon

from .config import AXES

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="osmnx")

ox.settings.use_cache = True
ox.settings.log_console = False


def load_walk_graph(place: Optional[str] = None,
                    center: Optional[Tuple[float, float]] = None,
                    dist_m: int = 2000):
    """보행 네트워크를 받아 (투영 그래프, WGS84 경계폴리곤) 반환."""
    if place:
        G = ox.graph_from_place(place, network_type="walk", simplify=True)
    elif center:
        G = ox.graph_from_point(center, dist=dist_m, network_type="walk", simplify=True)
    else:
        raise ValueError("place 또는 center 중 하나는 필요하다")

    nodes_wgs = ox.graph_to_gdfs(G, nodes=True, edges=False)
    # 피처 조회 범위: 노드 볼록껍질 + 여유 200m(약 0.002도)
    boundary: Polygon = nodes_wgs.union_all().convex_hull.buffer(0.002)

    Gp = ox.projection.project_graph(G)
    return Gp, boundary


class FetchError(RuntimeError):
    """Overpass 조회 자체가 실패했다. '결과 0건'과 반드시 구분해야 한다."""


def _fetch(boundary: Polygon, tags: dict, target_crs) -> gpd.GeoDataFrame:
    """태그로 피처를 받아 target_crs 로 투영.

    결과 0건은 빈 GDF, 조회 실패는 FetchError. 이 둘을 뭉뚱그리면
    '이 동네엔 나무가 없다'와 '서버가 죽었다'가 같은 결과가 되어
    라우팅이 조용히 엉뚱한 답을 낸다.
    """
    empty = gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=target_crs)
    if not tags:
        return empty
    try:
        gdf = ox.features_from_polygon(boundary, tags)
    except ox._errors.InsufficientResponseError:
        return empty                                    # 진짜로 0건
    except Exception as e:                              # noqa: BLE001
        raise FetchError(f"{type(e).__name__}: {e}") from e
    if gdf is None or gdf.empty:
        return empty
    gdf = gdf[gdf.geometry.notna()].copy()
    if gdf.empty:
        return empty
    return gdf.to_crs(target_crs)


def _split_points_areas(gdf: gpd.GeoDataFrame):
    """점 피처와 면/선 피처를 분리. 면은 대표점도 함께 만든다."""
    if gdf.empty:
        return gdf, gdf
    is_pt = gdf.geometry.geom_type.isin(["Point", "MultiPoint"])
    return gdf[is_pt].copy(), gdf[~is_pt].copy()


def fetch_all(boundary: Polygon, crs, axes_needed) -> Dict[str, Dict[str, gpd.GeoDataFrame]]:
    """축별로 필요한 OSM 피처를 한 번에 받아온다."""
    out: Dict[str, Dict[str, gpd.GeoDataFrame]] = {}
    for key in axes_needed:
        ax = AXES[key]
        if ax.kind == "derived":
            continue
        try:
            pts = _fetch(boundary, ax.point_tags or {}, crs)
            areas_raw = _fetch(boundary, ax.area_tags or {}, crs)
        except FetchError as e:
            print(f"    {ax.label:12s} [!] 조회 실패 — {e}")
            print(f"    {'':12s}     이 축은 신뢰할 수 없으므로 제외한다.")
            out[key] = None                             # None = 실패, 빈 GDF = 0건
            continue
        area_pts, areas = _split_points_areas(areas_raw)

        # area_tags 로 잡힌 점(예: leisure=park 를 노드로 찍은 것)도 점 집합에 합류
        if not area_pts.empty:
            pts = gpd.GeoDataFrame(
                __import__("pandas").concat([pts, area_pts], ignore_index=True),
                geometry="geometry", crs=crs) if not pts.empty else area_pts

        out[key] = {"points": pts, "areas": areas}
        if not (ax.point_tags or ax.area_tags):
            print(f"    {ax.label:12s} 내재 속성 — 링크에서 직접 계산")
            continue
        n = len(pts) + len(areas)
        print(f"    {ax.label:12s} 피처 {n:>6,}건  (점 {len(pts):,} / 면·선 {len(areas):,})")
    return out


def add_elevation(Gp, dem_path: str) -> bool:
    """로컬 DEM 래스터로 노드 표고 + 간선 경사 부여. 성공하면 True."""
    try:
        ox.elevation.add_node_elevations_raster(Gp, dem_path)
        ox.elevation.add_edge_grades(Gp)
        return True
    except Exception as e:                              # noqa: BLE001
        print(f"    [!] DEM 적용 실패: {type(e).__name__}: {e}")
        return False
