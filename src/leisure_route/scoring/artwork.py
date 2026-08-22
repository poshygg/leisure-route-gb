"""⑦ 오브제 — 공공미술·조형물 밀도.  [미구현]

데이터 : 전국공공미술및조형물정보표준데이터 (data.go.kr 15129443)
         항목 — 작품명, 시도, 시군구, 소재지도로명주소, 지번주소, 작품유형, 규격, 관리기관
         보완 — 한국문화예술위원회_미술작품 정보 15083293 (건축물미술작품, 1988~2024)
                공공미술포털 publicart.or.kr
방법   : 지오코딩 → 엣지 30m 버퍼 내 작품 수 → 규격 가중 → 정규화
함정 ★ : 좌표가 없습니다. 주소만 있어서 지오코딩 단계가 반드시 낍니다.
         도로명주소/지번주소 둘 다 있으니 실패 시 폴백 체인을 만드세요.
"""
from .base import NotImplementedScorer


class ArtworkScorer(NotImplementedScorer):
    name = "artwork"
    requires = ("interim/public_art.gpkg",)
