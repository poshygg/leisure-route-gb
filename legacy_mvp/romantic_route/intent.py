# -*- coding: utf-8 -*-
"""자연어/버튼 -> 축 가중치 벡터.

기본은 사전(lexicon) 기반. 키 없이 즉시 동작한다.
--llm 플래그를 주면 Claude로 파싱하고, 실패하면 조용히 사전으로 폴백한다.
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Tuple

from .config import AXES, DEFAULT_STRENGTH

# ---------------------------------------------------------------------------
# 사전: 축 -> 트리거 표현
# ---------------------------------------------------------------------------
LEXICON: Dict[str, List[str]] = {
    "flower": ["꽃", "꽃길", "벚꽃", "벚나무", "개화", "화사", "봄길", "꽃구경",
               "이팝", "배롱", "장미", "튤립", "flower", "blossom"],
    "trees": ["나무", "가로수", "숲", "녹음", "우거", "그늘", "수목", "삼림",
              "메타세쿼이아", "플라타너스", "green", "tree", "shade"],
    "heritage": ["문화재", "유적", "고궁", "궁궐", "한옥", "서원", "향교", "고택",
                 "사찰", "절", "역사", "옛", "전통", "근대건축", "heritage", "historic"],
    "art": ["벽화", "공공미술", "예술", "그래피티", "조형물", "미술", "갤러리",
            "art", "mural", "graffiti"],
    "water": ["강", "강변", "천", "하천", "개천", "물", "물가", "냇가", "호수",
              "river", "water", "stream", "waterfront"],
    "quiet": ["조용", "한적", "고요", "차 없", "차없", "인적", "호젓", "골목",
              "이면도로", "번잡하지", "시끄럽지", "quiet", "calm", "peaceful"],
    "skyview": ["하늘", "트인", "탁 트", "개방", "시원", "전망", "탁트",
                "답답하지", "sky", "open", "view"],
    "gentle": ["완만", "평지", "평탄", "언덕 없", "오르막 없", "힘들지", "무릎",
               "유모차", "휠체어", "캐리어", "flat", "gentle"],
    "snow": ["눈", "설경", "눈길", "겨울", "snow", "winter"],
}

# 강도 조절 표현
STRENGTH_CUES: List[Tuple[List[str], float]] = [
    (["아무리", "많이 돌아", "돌아가도", "멀어도", "천천히", "산책", "여유"], 3.5),
    (["조금", "살짝", "약간", "적당히"], 1.2),
    (["빨리", "최단", "지름길", "급해", "바로", "빠르게"], 0.4),
]

# 부정 표현 — 해당 축 요구를 무효화
NEGATIONS = ["말고", "빼고", "제외", "싫", "안 좋", "필요 없", "없이"]

# 기피어: '없음'이 곧 좋음인 축들. "언덕은 싫어" = 완만함을 원한다는 뜻이므로
# 일반 부정 규칙(요구 무효화)을 적용하면 안 되고, 오히려 해당 축을 강화해야 한다.
AVERSION: Dict[str, List[str]] = {
    "gentle":  ["언덕", "오르막", "내리막", "경사", "계단", "가파", "비탈"],
    "quiet":   ["시끄", "소음", "번잡", "차 많", "차많", "대로변", "매연", "북적"],
    "skyview": ["답답", "빌딩숲", "좁은 골목", "그늘져"],
    "water":   [],
}

DEFAULT_MIX = {"trees": 0.30, "quiet": 0.30, "water": 0.20, "heritage": 0.20}


def _normalize(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return dict(DEFAULT_MIX)
    return {k: v / total for k, v in weights.items() if v > 0}


def parse_lexicon(text: str) -> Tuple[Dict[str, float], float]:
    """문장 -> (가중치, 회피강도). 사전 매칭 기반."""
    t = (text or "").lower()
    hits: Dict[str, float] = {}

    for axis, words in LEXICON.items():
        score = 0.0
        for w in words:
            if w.lower() not in t:
                continue
            # 부정 표현이 단어 뒤 6글자 안에 붙으면 요구 취소
            idx = t.find(w.lower())
            tail = t[idx + len(w): idx + len(w) + 6]
            if any(neg in tail for neg in NEGATIONS):
                continue
            score += 1.0
        if score:
            hits[axis] = score

    # 기피어는 언급 자체가 요구다. 부정이 붙으면 더 강하게.
    for axis, words in AVERSION.items():
        for w in words:
            if w.lower() not in t:
                continue
            idx = t.find(w.lower())
            tail = t[idx + len(w): idx + len(w) + 8]
            hits[axis] = hits.get(axis, 0.0) + (
                1.5 if any(neg in tail for neg in NEGATIONS) else 1.0)

    if not hits:
        hits = dict(DEFAULT_MIX)

    strength = DEFAULT_STRENGTH
    for cues, val in STRENGTH_CUES:
        if any(c in t for c in cues):
            strength = val
            break

    return _normalize(hits), strength


# ---------------------------------------------------------------------------
# 선택: Claude 파서
# ---------------------------------------------------------------------------
_LLM_SYSTEM = """너는 산책 경로 추천기의 의도 파서다.
사용자 문장을 읽고 아래 9개 축에 가중치를 배분한다.

축: flower(꽃), trees(나무·그늘), heritage(문화재), art(벽화·공공미술),
    water(강변·물가), quiet(조용함), skyview(트인 하늘), gentle(완만한 경사),
    snow(설경)

규칙:
- weights 는 언급되거나 강하게 함의된 축만 포함한다. 0인 축은 넣지 마라.
- 합이 1.0 이 되도록 정규화한다.
- strength 는 우회 허용도다. 0.4=최단 우선, 2.0=보통, 3.5=많이 돌아가도 좋음.
- JSON 객체 하나만 출력한다. 설명이나 코드펜스를 붙이지 마라.

형식: {"weights": {"axis": float, ...}, "strength": float, "summary": "한 줄 요약"}"""


def parse_llm(text: str, model: str = "claude-opus-5") -> Tuple[Dict[str, float], float, str]:
    """Claude로 파싱. 실패 시 예외를 올리므로 호출부에서 폴백할 것."""
    import anthropic

    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 또는 `ant auth login` 프로파일
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=_LLM_SYSTEM,
        output_config={"effort": "low"},   # 작은 분류 작업이라 저강도로 충분
        messages=[{"role": "user", "content": text}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("intent parse refused")

    raw = "".join(b.text for b in resp.content if b.type == "text").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    data = json.loads(raw)

    weights = {k: float(v) for k, v in data.get("weights", {}).items()
               if k in AXES and float(v) > 0}
    if not weights:
        raise ValueError("no valid axes returned")

    strength = float(data.get("strength", DEFAULT_STRENGTH))
    strength = max(0.1, min(6.0, strength))
    return _normalize(weights), strength, data.get("summary", "")


def parse(text: str, use_llm: bool = False, model: str = "claude-opus-5"):
    """(weights, strength, summary, source) 반환."""
    if use_llm:
        try:
            w, s, summary = parse_llm(text, model=model)
            return w, s, summary, "llm"
        except Exception as e:                      # noqa: BLE001
            print(f"  [!] LLM 파싱 실패({type(e).__name__}) -> 사전 파서로 폴백")
    w, s = parse_lexicon(text)
    summary = " + ".join(f"{AXES[k].label} {v:.0%}" for k, v in
                         sorted(w.items(), key=lambda x: -x[1]))
    return w, s, summary, "lexicon"


def from_buttons(keys: List[str]) -> Tuple[Dict[str, float], float]:
    """UI 버튼 선택용. 균등 배분."""
    keys = [k for k in keys if k in AXES]
    if not keys:
        return dict(DEFAULT_MIX), DEFAULT_STRENGTH
    return {k: 1.0 / len(keys) for k in keys}, DEFAULT_STRENGTH
