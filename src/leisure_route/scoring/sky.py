"""⑨ 하늘이 잘 보이는 길 — Sky View Factor.  [미구현]

데이터 : 건축물대장 층수(×3m 근사) 또는 국토지리정보원 3D 건물
         + 연속수치지형도 도로폭
방법   : 협곡비 H/W 기반 근사.  SVF ≈ 1 / sqrt(1 + (H/W)^2)
         H = 양측 건물 평균 높이, W = 도로폭
함정   : - 로드뷰 어안 이미지의 sky 픽셀 비율이 더 정확하지만 훨씬 비쌉니다.
           기하 계산이 충분히 정확하니 먼저 이걸로 하세요 (docs/03_architecture.md).
         - 층수 × 3m 는 근사입니다. 상업건물은 층고가 더 높습니다.
주의   : ⑤ 나무와 직접 충돌합니다. 두 축을 같이 최대화할 수 없습니다.
"""
from .base import NotImplementedScorer


class SkyScorer(NotImplementedScorer):
    name = "sky"
    requires = ("interim/buildings.gpkg",)
