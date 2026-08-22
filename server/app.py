# -*- coding: utf-8 -*-
"""여유길 라이브 서버 — MVP 프론트 + 벨트 공공데이터 엔진.

  GET /                     MVP UI (romantic_route/ui.py 템플릿 재사용) — 실시간 탐색판
  GET /health               상태
  GET /api/plan             경로 탐색 → ui.build_payload 형식 그대로
  GET /api/reverse          역지오코딩
  GET /api/search           장소 검색
  GET /route/v1/foot/{...}  OSRM 호환 (Expo 앱의 RoutingAdapter 용)

실행:  python -m uvicorn app:app --port 8010   (server/ 안에서)
"""

from __future__ import annotations

import sys
from typing import List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from engine import AXES, AXIS_KEYS, BeltEngine, PlanError, ui
from live_ui import build_live_html

# 기본 구간 — 경주 대릉원 일원. 벨트 안에서 문화재·공원·조용함 세 축이 동시에
# 게이트를 통과하는 구간이라 첫 화면에서 축 채색이 실제로 보인다.
DEFAULT_ORIGIN = (35.83800, 129.21000)
DEFAULT_DEST = (35.82900, 129.22700)

app = FastAPI(title="여유길 라이브")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

print("=" * 60, flush=True)
ENGINE = BeltEngine(log=lambda m: print(m, flush=True))

AXES_META = [{"key": k, "label": AXES[k].label,
              "color": ui.AXIS_COLORS.get(k, "#8a8a85")} for k in AXIS_KEYS]

# MVP 템플릿 패치는 기동 시점에 한 번 — 앵커가 어긋나면 여기서 바로 죽는다
LIVE_HTML = build_live_html(AXES_META, DEFAULT_ORIGIN, DEFAULT_DEST)
print(f"라이브 UI 준비 완료 ({len(LIVE_HTML):,} bytes)", flush=True)
print("=" * 60, flush=True)


def _pair(s: str, what: str) -> Tuple[float, float]:
    try:
        lat, lng = (float(x) for x in s.split(","))
    except ValueError:
        raise HTTPException(400, f"{what} 좌표 형식이 잘못됐습니다 (lat,lng)")
    if not (32 <= lat <= 40 and 124 <= lng <= 132):
        raise HTTPException(400, f"{what} 좌표가 서비스 범위를 벗어납니다")
    return lat, lng


def _pairs(s: Optional[str]) -> List[Tuple[float, float]]:
    if not s:
        return []
    return [_pair(part, "제외 지점") for part in s.split(";") if part.strip()]


from pathlib import Path as _Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_DIST = _Path(__file__).resolve().parents[1] / "frontend" / "dist"


@app.get("/", response_class=HTMLResponse)
def index():
    """루트 = 여유길 웹앱 (frontend/dist). 빌드가 없으면 디버그 UI 폴백."""
    idx = _DIST / "index.html"
    if idx.exists():
        return FileResponse(idx)
    return HTMLResponse(LIVE_HTML)


@app.get("/debug", response_class=HTMLResponse)
def debug_ui():
    """엔진 디버그 뷰 (기존 낭만경로 스타일 실시간 탐색판)."""
    return HTMLResponse(LIVE_HTML)


if (_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")


@app.get("/health")
def health():
    return {"ok": True, "nodes": int(len(ENGINE.node_id)), "edges": int(len(ENGINE.edge_u)),
            "places": len(ENGINE.places), "axes": list(AXIS_KEYS)}


@app.get("/api/plan")
def plan(
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
    axes: str = Query(",".join(AXIS_KEYS)),
    k: int = Query(3, ge=1, le=6),
    strength: float = Query(2.0, ge=0.0, le=6.0),
    exclude: Optional[str] = Query(None, description="제외할 경유 요소 'lat,lng;lat,lng'"),
):
    o = _pair(from_, "출발지")
    d = _pair(to, "도착지")
    keys = [a.strip() for a in axes.split(",") if a.strip()]
    try:
        return ENGINE.plan(o, d, axes=keys, k=k, strength=strength, exclude=_pairs(exclude))
    except PlanError as e:
        raise HTTPException(422, str(e))


@app.get("/api/reverse")
def reverse(lng: float, lat: float):
    return ENGINE.reverse(lng, lat)


import requests as _rq

_geo_cache: dict = {}


def _nominatim(q: str, limit: int) -> list:
    """일반 지오코딩 폴백 — Photon(OSM, komoot). 검색-자동완성용이라
    '포항공' 같은 부분 입력에도 포항공과대학교가 뜬다. 실패는 빈 목록."""
    if q in _geo_cache:
        return _geo_cache[q]
    out = _photon_once(q, limit)
    # '포항공대'처럼 별칭이 정식 명칭(포항공과대학교)과 어긋나면 결과가 빈약하다
    # → 끝 글자를 줄여가며 재질의해 접두 매칭으로 보완한다 (포항공대→포항공→…)
    qq = q
    while len(out) < max(3, limit // 2) and len(qq) > 2:
        qq = qq[:-1]
        seen = {h["name"] for h in out}
        out += [h for h in _photon_once(qq, limit) if h["name"] not in seen]
    out = out[:limit]
    _geo_cache[q] = out
    return out


def _photon_once(q: str, limit: int) -> list:
    out = []
    try:
        r = _rq.get(
            "https://photon.komoot.io/api",
            params={"q": q, "limit": limit * 2, "lang": "default",
                    # 경북 중심 바이어스 — 전국 검색은 되고 근처가 위로 온다
                    "lat": 36.2, "lon": 129.0, "location_bias_scale": 0.3},
            headers={"User-Agent": "leisure-route-gb/0.1 (poshygg@gmail.com)"},
            timeout=5)
        r.raise_for_status()
        for f in r.json().get("features", []):
            p = f.get("properties", {})
            lng, lat = f["geometry"]["coordinates"]
            if not (124 <= lng <= 132 and 33 <= lat <= 39):     # 한국 밖 제외
                continue
            if p.get("osm_value") in ("parking", "parking_space", "bus_stop"):
                continue
            name = p.get("name")
            if not name:
                continue
            addr = ", ".join(x for x in (p.get("street"), p.get("district"),
                                         p.get("city"), p.get("state")) if x)
            out.append({"id": f"osm-{p.get('osm_id', name)}", "name": name,
                        "address": addr or "대한민국", "type": "place",
                        "pos": {"lng": float(lng), "lat": float(lat)}})
            if len(out) >= limit:
                break
    except Exception:
        out = []
    return out


@app.get("/api/search")
def search(q: str, limit: int = Query(12, ge=1, le=50)):
    """장소 검색 — 자체 데이터(국가유산·공원, 근거 있음) 우선 + 전 지역 지오코딩 폴백."""
    # 자체 데이터(근거 있는 문화재·공원)는 상위 절반까지만 — 나머지는 항상
    # 일반 지오코딩으로 채워서 '포항공→포항공과대학교' 같은 자동완성이 밀리지 않게 한다
    hits = [{"id": f"pl-{i}-{h['name']}", "name": h["name"],
             "address": h["addr"] or "경상북도", "type": h["kind"],
             "pos": {"lng": h["lng"], "lat": h["lat"]}}
            for i, h in enumerate(ENGINE.search(q, max(3, limit // 2)))]
    if len(hits) < limit:
        seen = {h["name"] for h in hits}
        for g in _nominatim(q, limit - len(hits)):
            if g["name"] in seen:          # 동명 중복(해수욕장+역 등)은 첫 건만
                continue
            seen.add(g["name"])
            hits.append(g)
    return hits[:limit]


# ---------------------------------------------------------------- Expo 앱 규격
# gyeongbuk-scenic-route-app 의 backendRoutes.ts 계약 (/api/routes).
# 앱 코드는 무수정 — EXPO_PUBLIC_API_URL 만 이 서버(:8010)로 바꾸면 된다.

_WP_TYPE = {"heritage": "heritage", "parks": "park", "coast": "water", "trees": "tree"}
_WP_SOURCE = {"heritage": "국가유산청 국가유산 공간정보",
              "parks": "전국도시공원정보표준데이터",
              "coast": "국립해양조사원 해안선"}


def _wp_id(lat: float, lng: float) -> str:
    """경유요소 id 에 좌표를 인코딩 — 앱이 exclude 로 돌려주면 좌표로 복원한다."""
    return f"wp_{lat:.6f}_{lng:.6f}"


def _decode_wp(s: str) -> Optional[Tuple[float, float]]:
    try:
        _, lat, lng = s.split("_")
        return float(lat), float(lng)
    except ValueError:
        return None


def _backend_route(r: dict, theme: str, label: str, icon: str) -> dict:
    geometry = []
    for i, seg in enumerate(r["segments"]):
        geometry += seg["c"] if i == 0 else seg["c"][1:]
    waypoints = []
    for p in r.get("pois", []):
        ax = p["axis"]
        waypoints.append({
            "id": _wp_id(p["lat"], p["lon"]), "name": p["name"],
            "type": _WP_TYPE.get(ax, "culture"),
            "reason": f"{AXES[ax].label} 축 인접 — 경로 점수에 기여",
            "source": _WP_SOURCE.get(ax, "공공데이터"),
            "pos": {"lng": p["lon"], "lat": p["lat"]},
        })
    return {"theme": theme, "themeLabel": label, "icon": icon,
            "distance_m": int(round(r["km"] * 1000)),
            "duration_s": int(round(r["min"] * 60)),
            "detourRatio": r["detour"], "geometry": geometry, "waypoints": waypoints}


@app.get("/api/routes")
def app_routes(
    from_: str = Query(..., alias="from", description="lng,lat (앱 규격 주의)"),
    to: str = Query(...),
    exclude: Optional[str] = Query(None, description="제외 경유요소 id (콤마 구분)"),
):
    # 앱은 lng,lat 순서로 보낸다 (backendRoutes.ts point()) — /api/plan 과 반대
    try:
        o_lng, o_lat = (float(x) for x in from_.split(","))
        d_lng, d_lat = (float(x) for x in to.split(","))
    except ValueError:
        raise HTTPException(400, "from/to 는 'lng,lat' 형식입니다")

    excl_ids = [s for s in (exclude.split(",") if exclude else []) if s.strip()]
    excl_coords = [c for c in (_decode_wp(s) for s in excl_ids) if c]
    try:
        p = ENGINE.plan((o_lat, o_lng), (d_lat, d_lng), k=3, exclude=excl_coords)
    except PlanError as e:
        raise HTTPException(422, str(e))

    rs = p["routes"]
    her_i = max(range(len(rs)), key=lambda i: rs[i]["axis_means"].get("heritage", 0.0))
    nat_i = next((i for i in range(len(rs)) if i != her_i), her_i)

    meta = p["meta"]
    return {
        "shortest": {"distance_m": int(meta["baselineKm"] * 1000),
                     "duration_s": int(meta["baselineMin"] * 60)},
        "excluded": excl_ids,
        "routes": [
            _backend_route(rs[nat_i], "nature", "자연 친화", "🌿"),
            _backend_route(rs[her_i], "history", "문화재", "🏛"),
        ],
    }


@app.get("/route/v1/foot/{coords}")
def osrm(coords: str, geometries: str = "polyline", overview: str = "full"):
    """Expo 앱의 RoutingAdapter(OSRM 규격)용 — 최단 경로만."""
    try:
        pts = [tuple(map(float, c.split(","))) for c in coords.split(";")]  # (lng, lat)
    except ValueError:
        raise HTTPException(400, "bad coords")
    if len(pts) < 2:
        return {"code": "Ok", "routes": [], "waypoints": []}
    try:
        p = ENGINE.plan((pts[0][1], pts[0][0]), (pts[-1][1], pts[-1][0]), k=1)
    except PlanError:
        return {"code": "NoRoute", "routes": [], "waypoints": []}
    line = p["baseline"] or []
    if not line:
        return {"code": "NoRoute", "routes": [], "waypoints": []}
    meters = p["meta"]["baselineKm"] * 1000
    return {
        "code": "Ok",
        "routes": [{"geometry": _encode_polyline(line), "distance": round(meters),
                    "duration": round(meters / 1.25), "weight": round(meters / 1.25),
                    "weight_name": "routability"}],
        "waypoints": [{"location": [lng, lat],
                       "name": "출발지" if i == 0 else "도착지"}
                      for i, (lng, lat) in enumerate([pts[0], pts[-1]])],
    }


def _encode_polyline(pts, precision: int = 5) -> str:
    factor = 10 ** precision
    out: List[str] = []
    plat = plon = 0
    for lat, lon in pts:
        ilat, ilon = round(lat * factor), round(lon * factor)
        for v in (ilat - plat, ilon - plon):
            v = ~(v << 1) if v < 0 else v << 1
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        plat, plon = ilat, ilon
    return "".join(out)


# SPA 라우팅 폴백 — /search, /routes 같은 프론트 경로 새로고침도 index.html 로.
# (구체 라우트들이 먼저 정의돼 있어 /api·/route/v1·/assets 는 여기 안 온다)
@app.get("/{path:path}", response_class=HTMLResponse, include_in_schema=False)
def spa_fallback(path: str):
    idx = _DIST / "index.html"
    if idx.exists() and not path.startswith(("api/", "route/", "assets/")):
        return FileResponse(idx)
    raise HTTPException(404, "not found")


if __name__ == "__main__":
    import uvicorn

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8010
    uvicorn.run(app, host="0.0.0.0", port=port)
