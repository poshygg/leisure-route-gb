"""⑥ 벽화길 · 지역특화거리.  [미구현]

데이터 : 전국지역특화거리표준데이터 (data.go.kr 15017322) — 거리명, 소재지, 소개, 점포수
         보완 — TourAPI 관광지(벽화마을), 지자체 도시재생사업 목록
방법   : 지오코딩 → 거리 구간과 엣지 매칭 → 불리언 또는 소개문 키워드 가중
함정 ★ : 좌표 없이 주소만. ⑦과 같은 지오코딩 문제입니다.
         "특화거리"에는 음식거리·의료기거리처럼 걷기와 무관한 것도 섞여 있으니
         `거리소개` 텍스트로 한 번 더 필터하세요.
"""
from .base import NotImplementedScorer


class StreetScorer(NotImplementedScorer):
    name = "street"
    requires = ("interim/themed_streets.gpkg",)
