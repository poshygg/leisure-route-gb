"""③ 조용한 길 — Land-Use Regression 으로 추정.  [미구현 · 난이도 상]

★ 직접 데이터가 존재하지 않습니다. 만들어야 합니다.

왜 : 한국환경공단 환경소음 측정망(15065396)은 전국 2,005지점·분기별입니다.
     전국 도로 수십만 km 대비 너무 성기고, 측정망 위치가 애초에 공항 주변·
     인구밀집지에 편향돼 있어 "조용한 길 찾기"에는 방향이 반대입니다.

방법 : Land-Use Regression (대기오염 지도 제작의 표준 기법을 소음에 적용)
       feature — 간선도로 거리, 도로위계, 차로수, 교통량, 건물밀도,
                 녹지율, 인구밀도, 철도·공항 거리
       target  — 측정 dB (2,005 지점)
       → 학습 후 전국 수십만 엣지에 추론
       score = 1 - normalize(추정 dB)

검증 : 측정지점 hold-out RMSE. 공간 자기상관 때문에 랜덤 분할은 낙관적으로 나옵니다.
       반드시 **공간 블록 분할(spatial block CV)** 을 쓰세요.

피처 데이터
  - 도로 위계        OSM highway
  - 차량 통행량      국토부·건기연 교통량 통계 API (data.go.kr 15097077)
  - 차로수·도로폭    국토지리정보원 연속수치지형도
  - 사람 밀도        서울 생활인구(무료) / 통신사 유동인구(유료)

이 프로젝트에서 가장 논문스럽고, 아직 아무도 안 해놓은 부분입니다.
"""
from .base import NotImplementedScorer


class QuietScorer(NotImplementedScorer):
    name = "quiet"
    requires = ("interim/noise_stations.gpkg", "processed/lur_model.pkl")
