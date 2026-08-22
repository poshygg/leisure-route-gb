# -*- coding: utf-8 -*-
"""백엔드 엔진 → 프론트엔드 데이터 (frontend/src/data/plan.json).

server/engine.py 의 BeltEngine 으로 기본 구간(경주 대릉원 → 동궁과 월지)을
계획하고, 프론트가 쓰는 RouteTheme 스키마로 변환해 저장한다.
프론트는 이 파일만 import 하면 서버 없이도 실데이터로 동작한다 (재현 가능).

  python scripts/40_export_frontend_plan.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

from engine import AXES, BeltEngine  # noqa: E402

ORIGIN = (35.8380, 129.2100)   # 대릉원 일원
DEST = (35.8290, 129.2270)     # 동궁과 월지

#: 엔진 축 → 프론트 WaypointType
WP_TYPE = {"heritage": "heritage", "parks": "park", "coast": "water",
           "trees": "tree", "quiet": "culture"}
SOURCE = {"heritage": "국가유산청 국가유산 공간정보",
          "parks": "전국도시공원정보표준데이터",
          "coast": "국립해양조사원 해안선"}


def to_theme(route: dict, theme_key: str, idx: int) -> dict:
    """ui.build_payload 의 route → 프론트 RouteTheme."""
    path = [{"lng": lon, "lat": lat}
            for seg_i, seg in enumerate(route["segments"])
            for lat, lon in (seg["c"] if seg_i == 0 else seg["c"][1:])]

    waypoints, used = [], set()
    for j, p in enumerate(route.get("pois", [])):
        wid = f"w{idx}-{j}"
        # 가장 가까운 경로 노드에 waypointId 를 붙인다
        best, best_d = None, float("inf")
        for ni, n in enumerate(path):
            d = (n["lng"] - p["lon"]) ** 2 + (n["lat"] - p["lat"]) ** 2
            if d < best_d:
                best, best_d = ni, d
        if best is None or best in used:
            continue
        used.add(best)
        path[best] = {**path[best], "waypointId": wid}
        axis = p["axis"]
        waypoints.append({
            "id": wid, "name": p["name"],
            "type": WP_TYPE.get(axis, "culture"),
            "reason": f"{AXES[axis].label} 축 인접 — 경로 점수에 기여",
            "source": SOURCE.get(axis, "공공데이터"),
        })

    means = route.get("axis_means", {})
    top = sorted(means, key=lambda k: -means[k])[:2]
    NAMES = {
        "heritage": ("문화재 여유길", "고분과 월성 사이, 천년을 걷는 길"),
        "nature": ("자연 여유길", "공원과 조용한 골목으로 도는 길"),
        "fast": ("빠른 길", "우회 없이 곧장 가는 기준선"),
    }
    name, tagline = NAMES[theme_key]
    return {
        "id": f"r-{theme_key}", "themeKey": theme_key,
        "name": name,
        "tagline": tagline + f" · {route['km']}km · {route['min']}분",
        "path": path, "waypoints": waypoints,
        "stats": {"km": route["km"], "min": route["min"],
                  "detour": route["detour"], "score": route["score"],
                  "axisMeans": means},
    }


def main() -> int:
    eng = BeltEngine()
    payload = eng.plan(ORIGIN, DEST, k=3)
    routes = payload["routes"]

    # 테마 배정: 최소 우회=fast, 남은 것 중 문화재 최고=heritage, 나머지=nature
    order = list(range(len(routes)))
    fast_i = min(order, key=lambda i: routes[i]["detour"])
    rest = [i for i in order if i != fast_i]
    her_i = max(rest, key=lambda i: routes[i]["axis_means"].get("heritage", 0)) if rest else fast_i
    nat_i = next((i for i in rest if i != her_i), her_i)

    themes = [to_theme(routes[nat_i], "nature", nat_i),
              to_theme(routes[her_i], "heritage", her_i),
              to_theme(routes[fast_i], "fast", fast_i)]

    o_rev = eng.reverse(ORIGIN[1], ORIGIN[0])
    d_rev = eng.reverse(DEST[1], DEST[0])
    start = {"id": "start", "name": o_rev["placeName"],
             "address": o_rev["roadAddress"],
             "pos": {"lng": ORIGIN[1], "lat": ORIGIN[0]}}
    goal = {"id": "goal", "name": d_rev["placeName"],
            "address": d_rev["roadAddress"],
            "pos": {"lng": DEST[1], "lat": DEST[0]}}

    # 검색 제안: 경로 주변 유명 장소 (문화재 우선, 이름 짧은 순)
    sugg = eng.search("경주", 0) or []
    places = sorted((p for p in eng.places if p.kind == "heritage"
                     and math.dist((p.lat, p.lon), ORIGIN) < 0.03),
                    key=lambda p: len(p.name))[:6]
    suggestions = [{"id": f"s{i}", "name": p.name, "address": p.addr or "경상북도 경주시",
                    "pos": {"lng": p.lon, "lat": p.lat}} for i, p in enumerate(places)]

    out = ROOT / "frontend" / "src" / "data" / "plan.json"
    out.write_text(json.dumps({
        "start": start, "goal": goal, "routes": themes,
        "suggestions": suggestions,
        "axes": payload["axes"], "excluded": payload["excluded"],
        "baseline": payload["baseline"], "meta": payload["meta"],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"저장: {out}")
    for t in themes:
        print(f"  {t['id']}: {t['stats']['km']}km 우회 {t['stats']['detour']}x "
              f"경유요소 {len(t['waypoints'])}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
