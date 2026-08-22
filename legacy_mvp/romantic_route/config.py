# -*- coding: utf-8 -*-
"""축(axis) 정의 — '좋은 길'을 무엇으로 볼 것인가.

설계 원칙 세 가지:
  1. 모든 축은 링크(간선)마다 0.0~1.0 점수로 환산된다. 1.0 = 최고.
  2. 점수는 페널티로만 변환한다 (배수 >= 1). 절대 할인하지 않는다.
     -> cost(e) >= length(e) 가 항상 성립하므로 A* 직선거리 휴리스틱이 admissible.
  3. 시간 게이트(months)가 있는 축은 철이 아니면 비활성화하고
     그 가중치를 나머지 축에 재분배한다.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Axis:
    key: str
    label: str
    kind: str                       # "count" | "near" | "intrinsic" | "derived"
    buffer_m: float = 50.0          # count: 이 반경 안을 셈 / near: 감쇠 거리
    saturate: float = 10.0          # count: 이 개수면 만점
    months: Tuple[int, ...] = ()    # 비어있으면 상시
    point_tags: Optional[dict] = None   # OSM 점 피처
    area_tags: Optional[dict] = None    # OSM 면/선 피처
    note: str = ""


# ---------------------------------------------------------------------------
# 9개 축
# ---------------------------------------------------------------------------
AXES: Dict[str, Axis] = {
    "flower": Axis(
        key="flower", label="꽃", kind="count",
        buffer_m=40, saturate=8,
        months=(3, 4, 5, 6, 7, 9, 10),
        point_tags={"natural": "tree"},
        area_tags={"leisure": ["garden", "park"], "landuse": "flowerbed"},
        note="OSM에 수종 태그가 드물어 근사치. 산림청 가로수(86.9만건, 수종명 포함)로 "
             "교체하면 왕벚나무/이팝나무/배롱나무 등 개화 수종만 정확히 잡힌다.",
    ),
    "trees": Axis(
        key="trees", label="나무 그늘", kind="count",
        buffer_m=30, saturate=12,
        point_tags={"natural": "tree"},
        area_tags={"landuse": "forest", "natural": "wood", "leisure": "park"},
        note="산림청 데이터의 흉고직경(DBH)이 있으면 개수가 아니라 수관피복률로 승급 가능.",
    ),
    "heritage": Axis(
        key="heritage", label="문화재", kind="count",
        buffer_m=150, saturate=3,
        point_tags={"historic": True},
        area_tags={"historic": True, "heritage": True},
        note="국가유산청 공간정보(WMS/WFS)로 교체 시 경계 폴리곤까지 사용 가능. 경북이 전국 최다.",
    ),
    "art": Axis(
        key="art", label="벽화·공공미술", kind="count",
        buffer_m=100, saturate=2,
        point_tags={"tourism": "artwork"},
        area_tags=None,
        note="전국공공미술및조형물정보표준데이터로 보강 가능.",
    ),
    "water": Axis(
        key="water", label="물가", kind="near",
        buffer_m=150,
        area_tags={"waterway": ["river", "stream", "canal"], "natural": "water"},
        note="전국하천표준데이터 / 국토부 하천망 API로 교체 가능.",
    ),
    "quiet": Axis(
        key="quiet", label="조용함", kind="intrinsic",
        note="OSM highway 위계에서 직접 계산. 공공 교통량 데이터(상시조사 3,920지점)는 "
             "이면도로를 안 담아서 오히려 이쪽이 낫다.",
    ),
    "skyview": Axis(
        key="skyview", label="트인 하늘", kind="intrinsic",
        buffer_m=45,
        area_tags={"building": True},
        note="진짜 SVF는 반구 적분이 필요. 여기선 건물 점유율의 역수로 근사. "
             "VWorld 3D LoD1(전국 구축)로 승급 가능.",
    ),
    "gentle": Axis(
        key="gentle", label="완만함", kind="intrinsic",
        note="DEM 필요(--dem). 없으면 축 자체를 비활성화하고 가중치를 재분배한다.",
    ),
    "snow": Axis(
        key="snow", label="설경", kind="derived",
        months=(12, 1, 2),
        note="전용 데이터 없음. trees/water/heritage/skyview 조합 휴리스틱임을 명시.",
    ),
}

# 파생축 조합 규칙
DERIVED = {
    "snow": {"trees": 0.40, "water": 0.25, "heritage": 0.20, "skyview": 0.15},
}

# ---------------------------------------------------------------------------
# 조용함: OSM highway 위계 -> 0~1
# ---------------------------------------------------------------------------
QUIET_BY_HIGHWAY = {
    "pedestrian": 1.00, "footway": 1.00, "path": 1.00, "track": 0.95,
    "steps": 0.90, "living_street": 0.90, "residential": 0.72,
    "service": 0.68, "unclassified": 0.60, "tertiary": 0.40,
    "tertiary_link": 0.40, "secondary": 0.22, "secondary_link": 0.22,
    "primary": 0.10, "primary_link": 0.10, "trunk": 0.02, "trunk_link": 0.02,
    "motorway": 0.0, "motorway_link": 0.0,
}
QUIET_DEFAULT = 0.55

# 경사(%) -> 완만함 점수. 보행 기준.
GRADE_COMFORT = [(2.0, 1.00), (4.0, 0.85), (6.0, 0.60), (8.0, 0.35), (12.0, 0.15)]

# 회피 강도: 최악(deficit=1) 링크가 length의 (1+STRENGTH)배 비용이 된다.
# 2.0이면 완벽한 길을 찾으려고 최대 3배까지 우회한다.
DEFAULT_STRENGTH = 2.0

MONTH_NAMES = {1: "1월", 2: "2월", 3: "3월", 4: "4월", 5: "5월", 6: "6월",
               7: "7월", 8: "8월", 9: "9월", 10: "10월", 11: "11월", 12: "12월"}


def active_axes(month: int, requested: List[str]) -> Tuple[List[str], Dict[str, str]]:
    """계절 게이트를 적용해 (활성 축, 비활성 사유) 반환."""
    active, dropped = [], {}
    for k in requested:
        ax = AXES[k]
        if ax.months and month not in ax.months:
            nxt = min((m for m in ax.months if m > month), default=min(ax.months))
            dropped[k] = f"{ax.label}은(는) 지금 철이 아님 (다음: {MONTH_NAMES[nxt]})"
        else:
            active.append(k)
    return active, dropped
