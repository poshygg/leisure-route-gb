# -*- coding: utf-8 -*-
"""벨트 보행망 × MVP 엔진 — 서버용.

scripts/20_belt_demo.py 의 로직을 그대로 쓰되, 한 번 실행하고 끝나는 CLI 가 아니라
**기동 시 1회 적재 → 요청마다 크롭·점수화·탐색** 하는 서비스 형태로 재구성한 것.

읽기 전용 참조 (어느 쪽도 수정하지 않는다):
  - C:\\...\\gyeongbuk-scenic-route\\data\\processed\\**   협업 저장소 가공 데이터
  - C:\\...\\romantic_route\\romantic_route\\**            MVP 라우팅·UI 엔진

CLI 대비 달라진 점은 성능뿐이다:
  CLI  = 요청마다 nodes.csv(51MB)+edges.csv(55MB) 를 pandas 로 다시 읽음
  서버 = 기동 시 numpy 배열로 한 번 올리고, 요청은 bbox 불리언 마스크로 크롭
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- 경로 설정

def _env_path(name: str, default: str) -> Path:
    p = Path(os.environ.get(name, default)).expanduser()
    if not p.exists():
        raise RuntimeError(f"{name} 경로가 없습니다: {p}")
    return p


# 엔진=legacy_mvp. 데이터 우선순위:
#   1) BELT_DATA 환경변수
#   2) 나란히 clone 된 gyeongbuk-scenic-route 전체 벨트 (있으면 — 벨트 전역 커버)
#   3) demos/data 고정 스냅샷 (항상 있음 — 데모 3구간만, 재현 보장)
ROOT = Path(__file__).resolve().parents[1]
MVP_ROOT = _env_path("ROMANTIC_ROUTE_ROOT", str(ROOT / "legacy_mvp"))
_sibling = ROOT.parent / "gyeongbuk-scenic-route" / "data" / "processed"
BELT = _env_path("BELT_DATA", str(_sibling if (_sibling / "network" / "nodes.csv").exists()
                                 else ROOT / "demos" / "data"))

# MVP 패키지를 import 경로에 올린다 (20_belt_demo.py 와 동일한 방식)
if str(MVP_ROOT) not in sys.path:
    sys.path.insert(0, str(MVP_ROOT))

import networkx as nx  # noqa: E402
import pyproj  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

from romantic_route import routing, ui  # noqa: E402
from romantic_route.config import AXES, QUIET_BY_HIGHWAY, QUIET_DEFAULT, Axis  # noqa: E402

CRS = "EPSG:32652"  # UTM 52N — 동해안 벨트 전역이 한 존에 들어간다
_TF = pyproj.Transformer.from_crs(4326, CRS, always_xy=True)

# 런타임 축 확장 — 저장소·MVP 코드 어느 쪽도 수정하지 않는다 (20_belt_demo.py 와 동일)
AXES.setdefault("coast", Axis(key="coast", label="해안", kind="near", buffer_m=300,
                              note="국립해양조사원 해안선(협업 저장소 가공본)"))
AXES.setdefault("parks", Axis(key="parks", label="공원", kind="near", buffer_m=250,
                              note="도시공원 표준데이터(협업 저장소 가공본)"))
ui.AXIS_COLORS.setdefault("coast", "#4a3aa7")
ui.AXIS_COLORS.setdefault("parks", "#1baf7a")

#: 이 엔진이 다루는 축 — 벨트 가공본으로 점수화 가능한 것만
AXIS_KEYS = ("heritage", "coast", "parks", "quiet")

#: 데이터가 없어서 v1 에서 못 쓰는 축 (UI 의 '데이터 게이트'에 항상 노출)
STATIC_GATES = [
    {"label": "하천", "reason": "rivers_belt.csv 빈 파일 — KRF 수령 전 (SPEC A3)"},
    {"label": "화목 가로수", "reason": "벨트 등재 3~4구간뿐 — 특징 유도 불가 (SPEC A6 blocked)"},
]

#: 축이 살아남기 위한 최소 커버리지 (쓸만한 간선 비율). 20_belt_demo.py 와 동일
GATE_MIN_COVERAGE = 0.03
GATE_GOOD_SCORE = 0.3

WALK_SPEED_M_PER_MIN = 67.0


class PlanError(RuntimeError):
    """사용자에게 그대로 보여줄 수 있는 실패 사유."""


@dataclass
class Place:
    name: str
    kind: str
    lat: float
    lon: float
    reason: str
    source: str
    addr: str


# ------------------------------------------------------------------- 엔진

class BeltEngine:
    """기동 시 1회 적재. 이후 plan() 은 인메모리 크롭만 한다."""

    def __init__(self, log=print):
        self.log = log
        self._load_network()
        self._load_features()
        self._load_places()

    # ---- 적재 -----------------------------------------------------------

    def _load_network(self):
        self.log("보행망 적재 …")
        nodes = pd.read_csv(BELT / "network/nodes.csv")
        # searchsorted 로 id→index 를 하려면 정렬되어 있어야 한다
        nodes = nodes.sort_values("id", kind="stable").reset_index(drop=True)
        self.node_id = nodes["id"].to_numpy(np.int64)
        self.node_lat = nodes["lat"].to_numpy(np.float64)
        self.node_lon = nodes["lon"].to_numpy(np.float64)

        edges = pd.read_csv(BELT / "network/edges.csv")
        eu = self._to_index(edges["u"].to_numpy(np.int64))
        ev = self._to_index(edges["v"].to_numpy(np.int64))
        ok = (eu >= 0) & (ev >= 0)
        self.edge_u = eu[ok]
        self.edge_v = ev[ok]
        self.edge_len = edges["length_m"].to_numpy(np.float64)[ok]
        # highway 문자열 1.5M 개를 그대로 들고 있으면 메모리 낭비 → 카테고리 코드로
        hw = edges["highway"].fillna("").astype("category")[ok]
        self.hw_codes = hw.cat.codes.to_numpy(np.int16)
        self.hw_names = list(hw.cat.categories)
        # 위계별 조용함 점수를 카테고리 단위로 미리 계산
        self.hw_quiet = np.array(
            [QUIET_BY_HIGHWAY.get(h, QUIET_DEFAULT) for h in self.hw_names], dtype=np.float64
        )

        # 스냅용 전역 KDTree (투영 좌표)
        nx_, ny_ = _TF.transform(self.node_lon, self.node_lat)
        self.node_x, self.node_y = nx_, ny_
        self.snap_tree = cKDTree(np.c_[nx_, ny_])
        self.log(f"  노드 {len(self.node_id):,} · 간선 {len(self.edge_u):,}")

    def _to_index(self, ids: np.ndarray) -> np.ndarray:
        pos = np.searchsorted(self.node_id, ids)
        pos = np.clip(pos, 0, len(self.node_id) - 1)
        miss = self.node_id[pos] != ids
        pos = pos.astype(np.int64)
        pos[miss] = -1
        return pos

    def _load_features(self):
        self.log("특징 데이터 적재 …")
        import geopandas as gpd
        from shapely.geometry import Point

        her = pd.read_csv(BELT / "heritage_belt_mapped.csv", encoding="utf-8-sig")
        her = her[(her.has_coord == "Y") & her.longitude.gt(0)]
        her_xy = self._proj(her, "longitude", "latitude")

        coast = pd.read_csv(BELT / "coastline_belt.csv", encoding="utf-8-sig")
        coast_xy = self._proj(coast, "lon", "lat")

        parks = pd.read_csv(BELT / "parks_belt.csv", encoding="utf-8-sig")
        parks = parks[~parks.parkSe.isin(["어린이공원", "묘지공원"])]  # SPEC A7 규칙
        parks = parks.dropna(subset=["latitude", "longitude"])
        parks_xy = self._proj(parks, "longitude", "latitude")

        ind = pd.read_csv(BELT / "network/industrial.csv", encoding="utf-8-sig")
        ind_xy = self._proj(ind, "lon", "lat")

        self.her_tree = cKDTree(her_xy) if len(her_xy) else None
        self.her_w = her["grade_w"].to_numpy(np.float64)
        self.coast_tree = cKDTree(coast_xy) if len(coast_xy) else None
        self.parks_tree = cKDTree(parks_xy) if len(parks_xy) else None
        self.ind_tree = cKDTree(ind_xy) if len(ind_xy) else None

        def gdfp(xy, names):
            return gpd.GeoDataFrame({"name": list(names)},
                                    geometry=[Point(*p) for p in xy], crs=CRS)

        # ui._route_pois 가 쓰는 형태
        self.feats_ui = {
            "heritage": {"points": gdfp(her_xy, her.ccbaMnm1), "areas": None},
            "parks": {"points": gdfp(parks_xy, parks.parkNm), "areas": None},
            "coast": {"points": None, "areas": None},
            "quiet": {"points": None, "areas": None},
        }
        self.log(f"  국가유산 {len(her_xy):,} · 해안선 {len(coast_xy):,} · "
                 f"공원 {len(parks_xy):,} · 공단 {len(ind_xy):,}")

    @staticmethod
    def _proj(df, loncol, latcol) -> np.ndarray:
        x, y = _TF.transform(df[loncol].to_numpy(), df[latcol].to_numpy())
        return np.column_stack([x, y])

    def _load_places(self):
        """역지오코딩·장소검색용 목록 (backend/app.py 의 _load_places 와 같은 소스)."""
        places: List[Place] = []
        parks = pd.read_csv(BELT / "parks_belt.csv", encoding="utf-8-sig")
        for r in parks.dropna(subset=["latitude", "longitude"]).itertuples():
            name = str(getattr(r, "parkNm", "") or "공원")
            if not name.endswith(("공원", "숲", "정원")):
                name += "공원"
            places.append(Place(name, "park", float(r.latitude), float(r.longitude),
                                "도시공원(" + str(getattr(r, "parkSe", "") or "") + ")",
                                "전국도시공원정보표준데이터",
                                str(getattr(r, "lnmadr", "") or getattr(r, "rdnmadr", "") or "")))

        her = pd.read_csv(BELT / "heritage_belt_mapped.csv", encoding="utf-8-sig")
        # 검색·역지오코딩은 점수가 아니라 "장소 찾기"라 전 계열을 포함한다.
        # (REVIEW=미매핑, ANCHOR=명승, EXCLUDE 중 벨트 안 좌표 — 첨성대가 유물>과학기술로
        #  EXCLUDE 처리돼 있어서 빼면 검색이 안 된다. 누출 방지는 특징 점수에만 적용.)
        # 단 벨트 밖 좌표(서울 박물관 소장품 등 소장처 좌표)는 지리적으로 걸러낸다.
        her = her[(her.has_coord == "Y")
                  & her.longitude.between(128.5, 130.5) & her.latitude.between(35.3, 37.5)
                  & (her.b_class != "EXCLUDE")
                  | ((her.b_class == "EXCLUDE") & (her.has_coord == "Y")
                     & her.longitude.between(128.8, 130.0) & her.latitude.between(35.5, 37.2))]
        for r in her.itertuples():
            addr = str(getattr(r, "ccbaLcad", "") or "")
            addr = addr.replace("<![CDATA[", "").replace("]]>", "").strip()
            places.append(Place(
                str(r.ccbaMnm1), "tree" if r.b_class == "NATURE" else "heritage",
                float(r.latitude), float(r.longitude),
                str(r.ccmaName) + " · " + str(getattr(r, "scodeName", "") or
                                              getattr(r, "gcodeName", "") or "문화유산"),
                "국가유산청 국가유산 공간정보", addr))

        self.places = places
        pxy = np.array([[p.lon, p.lat] for p in places])
        px, py = _TF.transform(pxy[:, 0], pxy[:, 1])
        self.place_tree = cKDTree(np.c_[px, py])
        self.log(f"  장소 {len(places):,}")

    # ---- 요청 처리 -------------------------------------------------------

    def _crop(self, center: Tuple[float, float], radius_m: float):
        lat0, lon0 = center
        dlat = radius_m / 111_000
        dlon = radius_m / (111_000 * math.cos(math.radians(lat0)))
        keep = ((self.node_lat >= lat0 - dlat) & (self.node_lat <= lat0 + dlat)
                & (self.node_lon >= lon0 - dlon) & (self.node_lon <= lon0 + dlon))
        emask = keep[self.edge_u] & keep[self.edge_v]

        G = nx.MultiGraph(crs=CRS)
        eu, ev = self.edge_u[emask], self.edge_v[emask]
        used = np.unique(np.concatenate([eu, ev])) if len(eu) else np.array([], dtype=np.int64)
        for i in used:
            G.add_node(int(self.node_id[i]), x=float(self.node_x[i]), y=float(self.node_y[i]))
        for u, v, L, hc in zip(eu, ev, self.edge_len[emask], self.hw_codes[emask]):
            G.add_edge(int(self.node_id[u]), int(self.node_id[v]),
                       length=float(L), highway=self.hw_names[hc], _q=float(self.hw_quiet[hc]))
        if G.number_of_nodes():
            cc = max(nx.connected_components(G), key=len)
            G = G.subgraph(cc).copy()
        return G

    def _score_edges(self, G):
        """간선 중점 기준 4축 점수 + 공단 감점 (20_belt_demo.score_edges 와 동일한 규칙)."""
        edges_index, mids, quiet_base = [], [], []
        for u, v, key, d in G.edges(keys=True, data=True):
            edges_index.append((u, v, key))
            mids.append(((G.nodes[u]["x"] + G.nodes[v]["x"]) / 2,
                         (G.nodes[u]["y"] + G.nodes[v]["y"]) / 2))
            quiet_base.append(d.get("_q", QUIET_DEFAULT))
        mids = np.asarray(mids)

        def near(tree, decay):
            if tree is None or not len(mids):
                return np.zeros(len(mids))
            dist, _ = tree.query(mids)
            return np.exp(-dist / decay)

        # 문화재: 150m 내 등급가중 합, 3점이면 만점 (MVP heritage saturate=3)
        # 간선마다 query_ball_point 를 부르면 수천 번 왕복하므로 한 번에 질의한다
        hs = np.zeros(len(mids))
        if self.her_tree is not None and len(mids):
            for i, idx in enumerate(self.her_tree.query_ball_point(mids, 150.0, return_sorted=False)):
                if idx:
                    hs[i] = min(1.0, float(self.her_w[idx].sum()) / 3.0)

        quiet = np.asarray(quiet_base, dtype=np.float64)
        quiet = np.clip(quiet - 0.6 * near(self.ind_tree, 200.0), 0.0, 1.0)  # 공단 감점(Z1 임시)

        return edges_index, {
            "heritage": hs,
            "coast": near(self.coast_tree, 300.0),
            "parks": near(self.parks_tree, 250.0),
            "quiet": quiet,
        }

    def _apply_exclusions(self, G, edges_index, exclude: List[Tuple[float, float]],
                          radius_m: float = 90.0, factor: float = 40.0) -> int:
        """제외한 경유 요소 주변 간선에 페널티를 건다.

        간선을 **지우지 않는다** — 지우면 그래프가 끊겨 경로 자체가 사라질 수 있고,
        A* 휴리스틱의 admissibility 도 깨진다. 비용만 크게 올려 우회를 유도한다.
        (romantic_route MVP 의 '페널티만 사용' 원칙과 동일)
        """
        if not exclude:
            return 0
        xy = np.array([_TF.transform(lng, lat) for lat, lng in exclude])
        tree = cKDTree(xy)
        hit = 0
        for (u, v, key) in edges_index:
            mx = (G.nodes[u]["x"] + G.nodes[v]["x"]) / 2
            my = (G.nodes[u]["y"] + G.nodes[v]["y"]) / 2
            if tree.query_ball_point((mx, my), radius_m):
                d = G[u][v][key]
                d["ambience_cost"] = float(d.get("ambience_cost", d.get("length", 1.0))) * factor
                d["excluded_near"] = True
                hit += 1
        return hit

    def plan(self, origin: Tuple[float, float], dest: Tuple[float, float],
             axes: Optional[List[str]] = None, k: int = 3, strength: float = 2.0,
             pad: float = 1200.0, exclude: Optional[List[Tuple[float, float]]] = None) -> dict:
        """MVP UI 가 그대로 먹는 payload 를 만든다 (ui.build_payload 형식)."""
        axes = [a for a in (axes or list(AXIS_KEYS)) if a in AXIS_KEYS]
        if not axes:
            raise PlanError("사용할 축을 하나 이상 골라 주세요.")

        ox, oy = _TF.transform(origin[1], origin[0])
        dx, dy = _TF.transform(dest[1], dest[0])
        span = math.dist((ox, oy), (dx, dy))
        if span < 30:
            raise PlanError("출발지와 목적지가 너무 가깝습니다.")
        center = ((origin[0] + dest[0]) / 2, (origin[1] + dest[1]) / 2)
        radius = span / 2 + pad

        G = self._crop(center, radius)
        if G.number_of_edges() == 0:
            raise PlanError("이 구간에는 보행망 데이터가 없습니다.")

        edges_index, scores = self._score_edges(G)

        # 데이터 게이트 — 커버리지가 기준 미만인 축은 빼고 가중치를 재분배한다
        weights = {a: 1.0 / len(axes) for a in axes}
        excluded = list(STATIC_GATES)
        coverage = {}
        for a in axes:
            good = float((scores[a] >= GATE_GOOD_SCORE).mean())
            coverage[a] = round(good, 4)
            if good < GATE_MIN_COVERAGE:
                excluded.append({
                    "label": AXES[a].label,
                    "reason": f"쓸만한 간선 {good:.1%} (기준 {GATE_MIN_COVERAGE:.0%}) "
                              f"— 이 지역 데이터로는 경로를 유도할 수 없다",
                })
                weights.pop(a)
        if not weights:
            raise PlanError("이 구간에서는 선택한 축 전부가 데이터 게이트에 걸렸습니다. "
                            "축을 바꾸거나 다른 구간을 골라 주세요.")
        tot = sum(weights.values())
        weights = {a: w / tot for a, w in weights.items()}

        routing.attach_costs(G, edges_index, scores, weights, strength)
        excluded_edges = self._apply_exclusions(G, edges_index, exclude or [])

        node_ids = list(G.nodes)
        node_xy = np.array([[G.nodes[n]["x"], G.nodes[n]["y"]] for n in node_ids])
        tree = cKDTree(node_xy)
        orig_n = node_ids[int(tree.query((ox, oy))[1])]
        dest_n = node_ids[int(tree.query((dx, dy))[1])]
        if orig_n == dest_n:
            raise PlanError("출발지와 목적지가 같은 지점으로 붙습니다.")

        try:
            baseline_nodes = nx.shortest_path(G, orig_n, dest_n, weight="length")
            baseline_m = nx.path_weight(G, baseline_nodes, weight="length")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            raise PlanError("두 지점이 보행망으로 이어지지 않습니다.")

        feasible, shared = routing.diversity_feasible(G, orig_n, dest_n)
        cands = routing.k_routes(G, orig_n, dest_n, k=k)
        stats = routing.rank([routing.evaluate(G, r, weights, baseline_m) for r in cands])
        if not stats:
            raise PlanError("경로를 찾지 못했습니다.")

        payload = ui.build_payload(
            G, stats, weights, self.feats_ui, CRS,
            query="여유길 — " + " + ".join(AXES[a].label for a in weights),
            summary="국가유산·해안선·도시공원·OSM 위계 (gyeongbuk-scenic-route 가공본, 읽기 전용)",
            baseline_nodes=baseline_nodes, excluded=excluded,
        )
        # 제외했는데도 경로에 남은 경유 요소를 표시해 둔다.
        # 출발·도착 바로 옆 요소는 스냅 지점 때문에 어떤 우회로도 피할 수 없다 —
        # 숨기면 거짓말이 되므로 dropped 로 찍어서 UI 가 그대로 드러내게 한다.
        if exclude:
            ex_xy = np.array([_TF.transform(lng, lat) for lat, lng in exclude])
            ex_tree = cKDTree(ex_xy)
            for r in payload["routes"]:
                for p in r.get("pois", []):
                    px, py = _TF.transform(p["lon"], p["lat"])
                    p["dropped"] = bool(ex_tree.query_ball_point((px, py), 120.0))

        payload["meta"] = {
            "origin": {"lat": origin[0], "lng": origin[1]},
            "dest": {"lat": dest[0], "lng": dest[1]},
            "baselineKm": round(baseline_m / 1000, 2),
            "baselineMin": int(round(baseline_m / WALK_SPEED_M_PER_MIN)),
            "graph": {"nodes": G.number_of_nodes(), "edges": G.number_of_edges(),
                      "radiusM": int(radius)},
            "coverage": coverage,
            "requestedAxes": axes,
            "diversityFeasible": bool(feasible),
            "diversityShared": round(float(shared), 3),
            "strength": strength,
            "excluded": [{"lat": a, "lng": b} for a, b in (exclude or [])],
            "excludedEdges": excluded_edges,
        }
        return payload

    # ---- 장소 -----------------------------------------------------------

    def reverse(self, lng: float, lat: float) -> dict:
        x, y = _TF.transform(lng, lat)
        d, i = self.place_tree.query((x, y))
        p = self.places[int(i)]
        if d <= 80:
            name = p.name
        elif d <= 1500:
            name = p.name + " 일대"
        else:
            name = "경상북도"
        return {"placeName": name,
                "roadAddress": p.addr if d <= 1500 and p.addr else "경상북도",
                "jibunAddress": p.addr or None,
                "position": {"lng": lng, "lat": lat}}

    def search(self, q: str, limit: int = 12) -> List[dict]:
        q = (q or "").strip()
        if not q:
            return []
        hits = [p for p in self.places if q in p.name]
        hits.sort(key=lambda p: (len(p.name), p.name))
        return [{"name": p.name, "kind": p.kind, "reason": p.reason,
                 "addr": p.addr, "lat": p.lat, "lng": p.lon} for p in hits[:limit]]
