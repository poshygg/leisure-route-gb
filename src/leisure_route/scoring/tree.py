"""⑤ 나무 — 녹지 피복률.  [미구현]

데이터 : Sentinel-2 NDVI (10m, 무료) 또는 환경부 토지피복지도 세분류
         보완 — 지자체 가로수 point
방법   : 엣지 20m 버퍼 내 평균 NDVI, 또는 활엽수림/침엽수림/혼효림/초지 피복 비율
함정   : - NDVI는 촬영 시기에 따라 크게 변합니다. 여름철(6~8월) 합성 영상을 쓰세요.
         - 농경지도 NDVI가 높습니다. 토지피복으로 마스킹하지 않으면 논밭이 "숲"이 됩니다.
정석   : Green View Index (MIT Treepedia) — 로드뷰 semantic segmentation으로
         시야 내 녹지 비율. 정확하지만 비쌉니다. NDVI부터 하세요.
주의   : ⑨ 하늘과 직접 충돌합니다 (수관이 하늘을 가림).
"""
from .base import NotImplementedScorer


class TreeScorer(NotImplementedScorer):
    name = "tree"
    requires = ("raw/ndvi_summer.tif",)
