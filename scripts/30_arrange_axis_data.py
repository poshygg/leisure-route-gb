# -*- coding: utf-8 -*-
"""백엔드 데이터를 특징 ID(A1~A7, B1~B6)별 파일로 정렬 → data/axis/

각 파일은 features.csv 의 feature_id 하나에 대응한다. 공통 컬럼:
  feature_id, name, lat, lon, value, weight, sigungu, source, geom
    - geom : point | segment(시작·끝 2점) | polyline_point(선을 점열로)
    - value: 특징의 원값 (비율·길이 등, 특징마다 의미 다름 — _manifest 참조)
  segment 는 lat/lon(시작) + lat2/lon2(끝) 를 갖는다.
  polyline_point 는 group_id + seq 로 선을 복원한다.

미수령 특징(A5·B5·B6, 임상도 원본)은 빈 파일 대신 _manifest.csv 에 사유를 남긴다.
협업 저장소(gyeongbuk-scenic-route)는 읽기만 한다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
BELT = Path(os.environ.get(
    "BELT_DATA", ROOT.parent / "gyeongbuk-scenic-route" / "data" / "processed"))
OUT = ROOT / "data" / "axis"
OUT.mkdir(parents=True, exist_ok=True)

manifest = []


def save(fid: str, df: pd.DataFrame, status: str, source: str, note: str = ""):
    df.insert(0, "feature_id", fid)
    df.to_csv(OUT / f"{fid}.csv", index=False, encoding="utf-8-sig")
    manifest.append({"feature_id": fid, "status": status, "rows": len(df),
                     "source": source, "note": note})
    print(f"  {fid}: {len(df):>6,}행  [{status}]  {source}")


def missing(fid: str, source: str, note: str):
    manifest.append({"feature_id": fid, "status": "missing", "rows": 0,
                     "source": source, "note": note})
    print(f"  {fid}:      0행  [missing]  {note}")


print("[A축 — 자연친화]")

# A1·A2·A6 — 가로수 수종분류본 (임상도 도착 전 프록시)
st = pd.read_csv(ROOT / "data/processed/streettrees_gb_classified.csv",
                 encoding="utf-8-sig")
base = pd.DataFrame({
    "name": st["name"], "lat": st.start_lat, "lon": st.start_lon,
    "lat2": st.end_lat, "lon2": st.end_lon, "sigungu": st.sigungu,
    "weight": st.tree_count, "geom": "segment",
})
for fid, col, note in (
        ("A1", "ratio_broadleaf", "임상도(FGIS) 승인 전 가로수 프록시. 정의는 면적비 — 도착 시 교체"),
        ("A2", "ratio_conifer",  "임상도(FGIS) 승인 전 가로수 프록시. 정의는 면적비 — 도착 시 교체"),
        ("A6", "ratio_flowering", "정본. value=개화종 그루수 비율, weight=전체 그루수")):
    save(fid, base.assign(value=st[col], source="가로수길 표준데이터 수종분류"),
         "proxy" if fid in ("A1", "A2") else "ready",
         "streettrees_gb_classified.csv", note)

# A3 — 하천 폴리라인 (벨트만 도착)
rv = pd.read_csv(BELT / "rivers_geometry_belt.csv", encoding="utf-8-sig")
save("A3", pd.DataFrame({
    "name": rv.riv_nm, "lat": rv.lat, "lon": rv.lon,
    "value": rv.rch_len_km, "group_id": rv.rch_id, "seq": rv.seq,
    "geom": "polyline_point", "source": "하천망(KRF) 벨트 클리핑",
}), "partial", "gyeongbuk-scenic-route/rivers_geometry_belt.csv",
    "벨트 4시군만. 전경북 확장 필요")

# A4 — 해안선 (벨트 = 사실상 경북 해안 전체)
co = pd.read_csv(BELT / "coastline_belt.csv", encoding="utf-8-sig")
save("A4", pd.DataFrame({
    "name": co.coast_type, "lat": co.lat, "lon": co.lon,
    "value": co.coast_type, "group_id": co.line_id, "seq": co.seq,
    "sigungu": co.sgg, "geom": "polyline_point",
    "source": "국립해양조사원 해안선 2026",
}), "ready", "gyeongbuk-scenic-route/coastline_belt.csv",
    "경북 해안 = 벨트 4시군이라 이것으로 완결 (울릉 제외, ADR-011)")

missing("A5", "환경부 토지피복 세분류", "EGIS 승인 대기. v1 제외(음수 특징) — 컬럼만 계산·보존 예정")

# A7 — 도시공원 (어린이·묘지 제외 규칙 적용해 usable 플래그)
pk = pd.read_csv(ROOT / "data/raw/parks/parks_gb.csv", encoding="utf-8-sig")
save("A7", pd.DataFrame({
    "name": pk.parkNm, "lat": pk.latitude, "lon": pk.longitude,
    "value": pk.parkSe, "weight": pk.parkAr, "sigungu": pk.institutionNm,
    "usable": ~pk.parkSe.isin(["어린이공원", "묘지공원"]),
    "geom": "point", "source": "전국도시공원정보표준데이터",
}), "ready", "data/raw/parks/parks_gb.csv",
    "usable=False(어린이·묘지 946건 중 일부)는 점수 제외, 표시만")

print("[B축 — 역사문화]")

# B1~B4 — 국가유산 분류본에서 b_class 별로
her = pd.read_csv(ROOT / "data/processed/heritage_gb_mapped.csv",
                  encoding="utf-8-sig")
B_NOTE = {
    "B1": "건축물형 (사찰·서원·고택·근대건축)",
    "B2": "석조물형 (석탑·석불·비석·마애불)",
    "B3": "유적형 (성곽·고분·봉수·터)",
    "B4": "전통마을 (5건뿐 — thin, 뷰포인트 위주 운용)",
}
for fid in ("B1", "B2", "B3", "B4"):
    sel = her[her.b_class == fid]
    save(fid, pd.DataFrame({
        "name": sel.ccbaMnm1, "lat": sel.latitude, "lon": sel.longitude,
        "value": sel.ccmaName, "weight": sel.grade_w, "sigungu": sel.ccsiName,
        "usable": sel.has_coord == "Y",
        "geom": "point", "source": "국가유산청 API + 01b 분류",
    }), "ready", "data/processed/heritage_gb_mapped.csv",
        B_NOTE[fid] + " · usable=False는 좌표 결측(지오코딩 대기)")

missing("B5", "전국공공미술및조형물표준데이터", "미수령 + 주소만 제공이라 지오코딩 단계 필요")
missing("B6", "전국지역특화거리표준데이터", "미수령 + 주소만 제공이라 지오코딩 단계 필요")

pd.DataFrame(manifest).to_csv(OUT / "_manifest.csv", index=False,
                              encoding="utf-8-sig")
print(f"\n완료 → {OUT}  (_manifest.csv 에 상태 요약)")
