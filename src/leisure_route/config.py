"""전역 설정: 경로, 좌표계, 스코어 컬럼, 라우팅 파라미터."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- 경로 ---
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW, INTERIM, PROCESSED = DATA / "raw", DATA / "interim", DATA / "processed"

# --- 좌표계 (ADR-005) ---
CRS_WGS84 = "EPSG:4326"   # 저장·교환 표준
CRS_METRIC = "EPSG:5179"  # UTM-K. 거리·버퍼·면적 연산은 반드시 여기서

# --- 스코어 컬럼 순서 (PHI 행렬 열 순서와 일치해야 함) ---
SCORE_COLS = [
    "s_river",      # ④ 강변
    "s_comfort",    # ⑩ 발 편함
    "s_heritage",   # ② 문화재
    "s_tree",       # ⑤ 나무
    "s_flower",     # ① 꽃길
    "s_sky",        # ⑨ 하늘
    "s_artwork",    # ⑦ 오브제
    "s_street",     # ⑥ 벽화·특화거리
    "s_quiet",      # ③ 조용함
    "s_building",   # ⑧ 볼 만한 건물
]

MVP_SCORERS = ["river", "comfort", "heritage"]  # ADR-004

# --- 라우팅 (ADR-002) ---
LAMBDA_GRID = (0.0, 8.0, 24)   # (start, stop, num) — 이분탐색 아님
DETOUR_PRESETS = {"shortest": 1.0, "balanced": 1.25, "leisurely": 1.6}

# --- 대상 지역 ---
REGIONS = {
    "gyeongju": {"name": "경주시", "code": "47130"},
    "andong": {"name": "안동시", "code": "47170"},
}

# --- 외부 서비스 ---
DATA_GO_KR_KEY = os.getenv("DATA_GO_KR_KEY", "")
VALHALLA_URL = os.getenv("VALHALLA_URL", "http://localhost:8002")
