"""공공데이터포털(data.go.kr) 클라이언트.  [부분 구현]

활용신청이 필요한 데이터셋 (.env 의 DATA_GO_KR_KEY 하나로 공통):
  - 15101974  한국관광공사_두루누비 정보 서비스_GW   ← GPX 284코스, 1,000콜/일
  - 3070426   국가유산청_문화재 공간 정보            ← SHP는 웹에서 직접 다운로드
  - 15101578  한국관광공사_국문 관광정보 서비스_GW   ← 보조

주의 : 서비스키는 URL 인코딩/디코딩 두 종류가 발급됩니다. requests의 params= 로
       넘기면 자동 인코딩되므로 **디코딩 키**를 .env 에 넣으세요.
"""
from __future__ import annotations

import requests

from ..config import DATA_GO_KR_KEY

BASE = "https://apis.data.go.kr"


class DataGoKr:
    def __init__(self, key: str | None = None, timeout: int = 20):
        self.key = key or DATA_GO_KR_KEY
        if not self.key:
            raise RuntimeError("DATA_GO_KR_KEY 없음 — .env.example 참조")
        self.timeout = timeout

    def get(self, path: str, **params):
        params = {"serviceKey": self.key, "_type": "json", **params}
        r = requests.get(f"{BASE}{path}", params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # --- 두루누비 (학습 정답셋) ---

    def durunubi_courses(self, page: int = 1, rows: int = 100):
        """코스 목록. TODO: 엔드포인트 경로는 TourAPI_Guide_(두루누비)v4.1.zip 확인 필요."""
        raise NotImplementedError("io/portal.py — 두루누비 오퍼레이션 경로 확인 필요")
