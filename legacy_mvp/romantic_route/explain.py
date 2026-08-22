# -*- coding: utf-8 -*-
"""경로 설명 텍스트 + folium 지도."""

from __future__ import annotations

from typing import Dict, List

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString
from shapely.ops import linemerge

from .config import AXES
from .routing import RouteStats, route_edges

BARS = "▁▂▃▄▅▆▇█"


def _bar(v: float) -> str:
    if v is None or not np.isfinite(v):
        return "?"
    return BARS[min(len(BARS) - 1, max(0, int(round(v * (len(BARS) - 1)))))]


def route_geometry(Gp, route: List[int]) -> LineString:
    parts = []
    for u, v, key, d in route_edges(Gp, route):
        if d.get("geometry") is not None:
            parts.append(d["geometry"])
        else:
            parts.append(LineString([(Gp.nodes[u]["x"], Gp.nodes[u]["y"]),
                                     (Gp.nodes[v]["x"], Gp.nodes[v]["y"])]))
    merged = linemerge(parts)
    return merged if merged.geom_type == "LineString" else LineString(
        [pt for g in parts for pt in g.coords])


def nearby_named(geom: LineString, feats: Dict[str, dict], keys: List[str],
                 radius: float = 120.0, limit: int = 6) -> Dict[str, List[str]]:
    """경로 주변에서 이름이 있는 피처를 뽑아 '무엇을 보게 되는지' 설명한다."""
    buf = geom.buffer(radius)
    out: Dict[str, List[str]] = {}
    for k in keys:
        f = feats.get(k)
        if not f:
            continue
        names = []
        for gdf in (f.get("points"), f.get("areas")):
            if gdf is None or gdf.empty or "name" not in gdf.columns:
                continue
            sel = gdf[gdf.geometry.intersects(buf)]
            names += [n for n in sel["name"].dropna().unique().tolist() if n]
        if names:
            out[k] = sorted(set(names))[:limit]
    return out


def describe(idx: int, st: RouteStats, weights: Dict[str, float],
             named: Dict[str, List[str]]) -> str:
    lines = [
        f"── 경로 {idx}  ·  {st.length_m/1000:.2f} km  ·  도보 {st.minutes:.0f}분"
        f"  ·  우회 {st.detour:.2f}x  ·  점수 {st.score:.3f}"
    ]
    for k, w in sorted(weights.items(), key=lambda x: -x[1]):
        if k not in st.axis_means:
            continue
        v = st.axis_means[k]
        shown = f"{v:5.1%}" if np.isfinite(v) else "  n/a"
        lines.append(f"   {_bar(v)} {AXES[k].label:<12s} {shown}   (가중치 {w:.0%})")
    lines.append(f"   변화도(variety) {st.variety:.2f}"
                 f"  — 1에 가까울수록 풍경이 골고루 바뀐다")
    if named:
        lines.append("   지나며 보이는 것:")
        for k, names in named.items():
            lines.append(f"     · {AXES[k].label}: " + ", ".join(names))
    return "\n".join(lines)


def make_map(Gp, routes: List[RouteStats], crs, out_path: str,
             feats: Dict[str, dict] = None, show_keys: List[str] = None):
    import folium

    geoms = [route_geometry(Gp, s.nodes) for s in routes]
    gs = gpd.GeoSeries(geoms, crs=crs).to_crs(4326)
    center = gs.iloc[0].centroid

    m = folium.Map(location=[center.y, center.x], zoom_start=15,
                   tiles="CartoDB positron")

    colors = ["#e8590c", "#1c7ed6", "#2f9e44", "#9c36b5"]
    for i, (s, g) in enumerate(zip(routes, gs)):
        folium.PolyLine(
            [(y, x) for x, y in g.coords],
            color=colors[i % len(colors)],
            weight=7 - i, opacity=0.85 if i == 0 else 0.55,
            tooltip=f"경로 {i+1} · {s.length_m/1000:.2f}km · {s.minutes:.0f}분 "
                    f"· 점수 {s.score:.3f}",
        ).add_to(m)

    start, end = gs.iloc[0].coords[0], gs.iloc[0].coords[-1]
    folium.Marker([start[1], start[0]], tooltip="출발",
                  icon=folium.Icon(color="green", icon="play")).add_to(m)
    folium.Marker([end[1], end[0]], tooltip="도착",
                  icon=folium.Icon(color="red", icon="stop")).add_to(m)

    if feats and show_keys:
        buf = geoms[0].buffer(150)
        for k in show_keys:
            f = feats.get(k)
            if not f:
                continue
            grp = folium.FeatureGroup(name=AXES[k].label, show=(k != "trees"))
            for gdf in (f.get("points"), f.get("areas")):
                if gdf is None or gdf.empty:
                    continue
                sel = gdf[gdf.geometry.intersects(buf)]
                if sel.empty:
                    continue
                pts = sel.to_crs(4326).geometry.representative_point()
                names = (sel["name"] if "name" in sel.columns
                         else [None] * len(sel))
                for p, nm in zip(pts, names):
                    folium.CircleMarker(
                        [p.y, p.x], radius=3, weight=0, fill=True,
                        fill_opacity=0.7, color="#495057",
                        tooltip=f"{AXES[k].label}: {nm}" if nm else AXES[k].label,
                    ).add_to(grp)
            grp.add_to(m)
        folium.LayerControl(collapsed=True).add_to(m)

    m.save(out_path)
    return out_path
