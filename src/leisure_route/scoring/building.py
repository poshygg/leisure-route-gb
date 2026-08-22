"""⑧ 볼 만한 건물.  [미구현 · 난이도 상]

★ 데이터 문제가 아니라 정의 문제입니다. "볼 만한"의 정의가 없습니다.

접근 3가지 (조합 권장)
  1) 등록문화유산(근대건축) — 국가유산청. 객관적이고 바로 씁니다.
  2) 건축물미술작품 설치 건물 (data.go.kr 15083293) — 연면적 1만㎡ 이상 건축물은
     미술작품 설치 의무가 있어, 이게 붙은 건물은 규모·격이 어느 정도 보장됩니다.
  3) 로드뷰 + CLIP zero-shot
        "a beautiful street with interesting architecture"
        vs "a plain street with parking lots and blank walls"
     텍스트-이미지 코사인 유사도 차이 = 시각적 매력. 학습 0, 라벨 0.

정석은 MIT Place Pulse 2.0 (쌍비교로 학습된 거리 인상 데이터셋) 방식이지만
MVP에는 CLIP이 압도적으로 효율적입니다.

선결 : 로드뷰 이미지 확보 가능 여부 (카카오/네이버 API 이용약관) 를 먼저 확인하세요.
       여기서 막히면 1)+2) 만으로 가야 합니다.
"""
from .base import NotImplementedScorer


class BuildingScorer(NotImplementedScorer):
    name = "building"
    requires = ("interim/registered_heritage.gpkg",)
