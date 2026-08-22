# -*- coding: utf-8 -*-
"""로컬 .osm.pbf 에서 보행망 + 피처를 뽑는다 — Overpass 없이.

왜 필요한가: 경북 23개 시군을 라이브 Overpass 로 훑는 건 불가능하다
(요청 수천 건 + IP 레이트리밋). 한국 전체 PBF(약 273MB) 한 장을 받아
시군 단위로 한 번만 훑으면 이후는 전부 로컬이고 재현 가능하다.

features.load_walk_graph / fetch_all 과 같은 모양을 반환하므로
layers / routing / explain 은 손댈 필요가 없다.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import pickle
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Tuple

import geopandas as gpd
import networkx as nx
import osmium
from shapely.geometry import LineString, Point, Polygon

# osmnx walk 프로파일과 동일하게 차량전용도로를 뺀다
WALK_EXCLUDE = {
    "motorway", "motorway_link", "trunk", "trunk_link",
    "construction", "proposed", "raceway", "bus_guideway", "escape",
}


def _match(tags, spec: dict) -> bool:
    """spec 예: {"natural": "tree"} / {"historic": True} / {"leisure": ["park","garden"]}"""
    for k, want in spec.items():
        if k not in tags:
            continue
        if want is True:
            return True
        v = tags[k]
        if isinstance(want, (list, tuple, set)):
            if v in want:
                return True
        elif v == want:
            return True
    return False


def utm_epsg(lon: float, lat: float) -> int:
    zone = int((lon + 180) // 6) + 1
    return (32600 if lat >= 0 else 32700) + zone


def _hav(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


class _Extractor:
    def __init__(self, bbox, specs: Dict[str, dict]):
        self.w, self.s, self.e, self.n = bbox
        self.specs = specs
        self.ways: List[dict] = []
        self.node_use = Counter()
        self.feat_pt: Dict[str, list] = defaultdict(list)
        self.feat_ar: Dict[str, list] = defaultdict(list)
        self.coord: Dict[int, Tuple[float, float]] = {}

    def _in(self, lon, lat) -> bool:
        return self.w <= lon <= self.e and self.s <= lat <= self.n

    def run(self, path: str, margin_deg: float = 0.01) -> None:
        """2패스. 전역 위치 인덱스(flex_mem)를 쓰지 않는다.

        한국 전체 PBF 의 노드는 수천만 개라 flex_mem 인덱스를 만들면 수 GB 를 먹는다.
        노드는 자기 좌표를 들고 있으므로, 패스 A 에서 bbox 안 노드만 골라 좌표표를
        만들고 패스 B 에서 way 를 그 표로 조립하면 메모리가 bbox 크기에만 비례한다.
        (margin: 경계에 걸친 way 의 좌표가 끊기지 않도록 노드 수집만 살짝 넓게)
        """
        mw, ms = self.w - margin_deg, self.s - margin_deg
        me, mn = self.e + margin_deg, self.n + margin_deg

        # ---- 패스 A: bbox 안 노드의 좌표 + 점 피처 ----
        for n in osmium.FileProcessor(path, osmium.osm.NODE):
            loc = n.location
            if not loc.valid():
                continue
            lon, lat = loc.lon, loc.lat
            if not (mw <= lon <= me and ms <= lat <= mn):
                continue
            self.coord[n.id] = (lon, lat)
            if not n.tags or not self._in(lon, lat):
                continue
            tags = dict(n.tags)
            for name, spec in self.specs.items():
                if name.endswith(":pt") and _match(tags, spec):
                    self.feat_pt[name[:-3]].append(
                        {"name": tags.get("name"), "geometry": Point(lon, lat)})

        # ---- 패스 B: way 조립 ----
        for w in osmium.FileProcessor(path, osmium.osm.WAY):
            self._way(w)

    def _way(self, w) -> None:
        nodes = [(nd.ref, *self.coord[nd.ref]) for nd in w.nodes
                 if nd.ref in self.coord]
        if len(nodes) < 2:
            return
        coords = [(lon, lat) for _, lon, lat in nodes]
        if not any(self._in(x, y) for x, y in coords):
            return

        tags = dict(w.tags)
        hw = tags.get("highway")
        if hw and hw not in WALK_EXCLUDE and tags.get("access") not in ("private", "no"):
            ids = [nid for nid, _, _ in nodes]
            self.ways.append({"ids": ids, "coords": coords, "highway": hw,
                              "lanes": tags.get("lanes"), "name": tags.get("name")})
            self.node_use.update(ids)
            self.node_use[ids[0]] += 1
            self.node_use[ids[-1]] += 1

        closed = len(coords) >= 4 and coords[0] == coords[-1]
        for name, spec in self.specs.items():
            if not name.endswith(":ar") or not _match(tags, spec):
                continue
            try:
                geom = Polygon(coords) if closed else LineString(coords)
                if not geom.is_valid:
                    geom = geom.buffer(0)
            except Exception:
                continue
            self.feat_ar[name[:-3]].append({"name": tags.get("name"), "geometry": geom})


def _add_edge(G, u, v, pts, w) -> None:
    if u == v or len(pts) < 2:
        return
    length = sum(_hav(pts[i][1], pts[i][0], pts[i + 1][1], pts[i + 1][0])
                 for i in range(len(pts) - 1))
    if length <= 0:
        return
    a = {"length": length, "highway": w["highway"], "lanes": w["lanes"],
         "name": w["name"], "_ll": list(pts)}
    G.add_edge(u, v, **a)
    G.add_edge(v, u, **dict(a, _ll=list(reversed(pts))))


def _build_graph(ex: _Extractor, epsg: int) -> nx.MultiDiGraph:
    """way 를 교차점에서 잘라 라우팅 가능한 그래프로 만든다."""
    G = nx.MultiDiGraph()
    G.graph["crs"] = f"EPSG:{epsg}"
    pos = {}
    for w in ex.ways:
        for nid, c in zip(w["ids"], w["coords"]):
            pos.setdefault(nid, c)

    for w in ex.ways:
        ids, coords = w["ids"], w["coords"]
        s_ids, s_pts = [ids[0]], [coords[0]]
        for nid, pt in zip(ids[1:], coords[1:]):
            s_ids.append(nid)
            s_pts.append(pt)
            if ex.node_use[nid] >= 2:
                _add_edge(G, s_ids[0], nid, s_pts, w)
                s_ids, s_pts = [nid], [pt]
        if len(s_pts) >= 2:
            _add_edge(G, s_ids[0], s_ids[-1], s_pts, w)

    for nid, (lon, lat) in pos.items():
        if G.has_node(nid):
            G.nodes[nid]["lon"], G.nodes[nid]["lat"] = lon, lat
    G.remove_nodes_from([n for n in list(G.nodes) if G.degree(n) == 0])
    return G


def _project(G, epsg: int):
    import pyproj
    tf = pyproj.Transformer.from_crs(4326, epsg, always_xy=True)
    for _, d in G.nodes(data=True):
        d["x"], d["y"] = tf.transform(d["lon"], d["lat"])
    for _, _, d in G.edges(data=True):
        pts = d.pop("_ll")
        xs, ys = tf.transform([p[0] for p in pts], [p[1] for p in pts])
        d["geometry"] = LineString(list(zip(xs, ys)))
    return G


def _extract_cached(pbf_path: str, bbox, specs: dict, cache_dir: str) -> "_Extractor":
    """추출 결과를 디스크에 캐시. PBF 2패스가 3분 걸려서 없으면 실험이 불가능하다."""
    key = hashlib.sha1(json.dumps(
        {"pbf": os.path.basename(pbf_path),
         "mtime": int(os.path.getmtime(pbf_path)),
         "bbox": [round(v, 6) for v in bbox],
         "specs": {k: sorted(map(str, v.items())) for k, v in sorted(specs.items())}},
        sort_keys=True).encode()).hexdigest()[:16]

    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"extract_{key}.pkl")
    if os.path.exists(path):
        print(f"    캐시 적중: {os.path.basename(path)}")
        with open(path, "rb") as f:
            return pickle.load(f)

    print("    PBF 2패스 추출 중... (첫 실행만, 이후 캐시)")
    ex = _Extractor(bbox, specs)
    ex.run(pbf_path)
    ex.coord = {}                      # 좌표표는 그래프 조립 후 불필요 — 캐시에서 뺀다
    with open(path, "wb") as f:
        pickle.dump(ex, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"    캐시 저장: {os.path.basename(path)}")
    return ex


def load_region(pbf_path: str, center: Tuple[float, float], dist_m: int,
                axes_needed: Iterable[str], axes_def,
                cache_dir: str = "data/extract_cache"):
    """(투영 그래프, feats) 반환. feats 는 features.fetch_all 과 동일 구조."""
    lat, lon = center
    dlat = dist_m / 111_320.0
    dlon = dist_m / (111_320.0 * max(math.cos(math.radians(lat)), 0.1))
    bbox = (lon - dlon, lat - dlat, lon + dlon, lat + dlat)
    epsg = utm_epsg(lon, lat)

    specs = {}
    for k in axes_needed:
        ax = axes_def[k]
        if ax.point_tags:
            specs[f"{k}:pt"] = ax.point_tags
        if ax.area_tags:
            specs[f"{k}:ar"] = ax.area_tags

    ex = _extract_cached(pbf_path, bbox, specs, cache_dir)
    G = _project(_build_graph(ex, epsg), epsg)
    crs = f"EPSG:{epsg}"

    def _gdf(rows):
        if not rows:
            return gpd.GeoDataFrame({"name": [], "geometry": []},
                                    geometry="geometry", crs=4326).to_crs(crs)
        return gpd.GeoDataFrame(rows, geometry="geometry", crs=4326).to_crs(crs)

    feats = {}
    for k in axes_needed:
        ax = axes_def[k]
        if ax.kind == "derived":
            continue
        feats[k] = {"points": _gdf(ex.feat_pt.get(k, [])),
                    "areas": _gdf(ex.feat_ar.get(k, []))}
    return G, feats
