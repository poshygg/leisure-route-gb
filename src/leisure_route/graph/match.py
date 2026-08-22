"""GPX → 그래프 엣지열 맵매칭.  [미구현]

두루누비 284코스를 학습 정답셋으로 쓰려면 GPX를 우리 엣지 인덱스 열로 바꿔야 합니다.

방법 A (권장) — Valhalla trace_attributes
    GPX → Valhalla → edge.way_id → OSM way id 로 우리 엣지에 조인.
    이 프로젝트에서 Valhalla를 쓰는 유일한 곳입니다 (ADR-001).

방법 B (충분함) — 자체 그리디 매처
    GPX 포인트 → 20m 내 최근접 엣지 → 중복 제거 → 끊긴 구간은 최단경로로 연결.
    284개면 이걸로 충분합니다.
"""
from __future__ import annotations

import numpy as np


def match_gpx(gpx_points: np.ndarray, edges, method: str = "greedy") -> list[int]:
    """(N,2) lon/lat 배열 → 엣지 인덱스 열."""
    raise NotImplementedError("graph/match.py — CONTRIBUTING.md 참조")
