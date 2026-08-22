"""국가유산 원본 → B분류 매핑 + 소분류 정렬 카탈로그 문서 생성.

입력: data/raw/heritage/heritage_gb.csv
출력: data/processed/heritage_gb_mapped.csv, docs/05_heritage_catalog.md
"""
import csv
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 종목 → 등급가중 (B1~B3 count_weighted 용)
GRADE_W = {
    "국보": 2.0, "보물": 2.0, "사적": 2.0, "국가민속문화유산": 2.0, "천연기념물": 2.0,
    "시도유형문화유산": 1.5, "시도기념물": 1.5, "시도민속문화유산": 1.5, "시도자연유산": 1.5,
    "문화유산자료": 1.0, "국가등록문화유산": 1.0, "시도등록문화유산": 1.0,
}


def classify(r):
    """행 → (클래스, 근거) 매핑. 우선순위 순서가 중요."""
    kind, g, b, m, s = r["ccmaName"], r["gcodeName"], r["bcodeName"], r["mcodeName"], r["scodeName"]
    name = r["ccbaMnm1"]
    if kind == "명승":
        return "ANCHOR", "명승은 정답(앵커) — 특징 사용 금지"
    if "무형" in kind or g == "무형유산":
        return "EXCLUDE", "무형유산 — 장소 경험 아님"
    if g == "유적건조물" and name.endswith("마을"):
        return "B4", "전통마을 (이름 기준)"
    if g == "자연유산" or kind in ("천연기념물", "시도자연유산"):
        return "NATURE", "자연유산 — v1 뷰포인트 전용 (점수 미반영, 지질명소 앵커와 중복 주의)"
    if g == "기록유산":
        if "금석" in b:
            return "B2", "금석문(비석) — 야외 석조"
        return "EXCLUDE", "서책·문서 — 실내 소장품"
    if g == "유물":
        if b in ("불교조각", "일반조각") and m in ("석조", "암벽조각"):
            return "B2", "야외 석불·마애불·암각화"
        return "EXCLUDE", "회화·공예·실내 조각 — 소장처 실내"
    if g == "등록문화유산":
        return "B1", "근대 건축물 다수"
    if g == "유적건조물":
        if b == "종교신앙":
            if s in ("탑", "당간", "부도", "장승"):
                return "B2", "석조물"
            return "B1", "사찰·불전·교회 등 경내 건축"
        if b in ("주거생활", "교육문화"):
            return "B1", "가옥·누정·서원·향교"
        if b == "인물사건":
            if s in ("사우",):
                return "B1", "사우 건물"
            return "B3", "탄생지·생활유적 등 터"
        if b == "정치국방":
            if m in ("궁궐·관아",):
                return "B1", "관아 건물"
            return "B3", "성곽·성지"
        if b in ("무덤", "유물산포지유적산포지", "산업생산", "교통통신"):
            return "B3", "고분·유적지·가마·봉수"
        return "REVIEW", f"미매핑 중분류: {b or '(공란)'}"
    return "REVIEW", f"미매핑 대분류: {g or '(공란)'}"


def main():
    rows = list(csv.DictReader(open(ROOT / "data/raw/heritage/heritage_gb.csv", encoding="utf-8-sig")))
    active = [r for r in rows if r["ccbaCncl"] != "Y"]
    for r in active:
        r["b_class"], r["b_reason"] = classify(r)
        try:
            r["has_coord"] = "Y" if float(r["longitude"] or 0) and float(r["latitude"] or 0) else "N"
        except ValueError:
            r["has_coord"] = "N"
        r["grade_w"] = GRADE_W.get(r["ccmaName"], 1.0)

    out_dir = ROOT / "data/processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    fields = list(active[0].keys())
    with open(out_dir / "heritage_gb_mapped.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(active)

    # ---- 카탈로그 문서 ----
    L = []
    L.append("# 경북 국가유산 카탈로그 (B분류 매핑)\n")
    L.append("> 원본: 국가유산청 Open API (키 불필요) · 경북(ccbaCtcd=37) · 지정해제 제외\n")
    cls_cnt = Counter(r["b_class"] for r in active)
    coord_cnt = Counter((r["b_class"], r["has_coord"]) for r in active)
    L.append("## 요약\n")
    L.append(f"- 전체 {len(rows)}건 → 유효(지정해제 제외) **{len(active)}건**")
    L.append(f"- 좌표 보유 {sum(1 for r in active if r['has_coord']=='Y')}건 / 결측 {sum(1 for r in active if r['has_coord']=='N')}건\n")
    L.append("| 클래스 | 건수 | 좌표有 | 용도 |")
    L.append("|---|---|---|---|")
    usage = {"B1": "건축물형 특징 (buffer 150m)", "B2": "석조물형 특징 (buffer 100m)",
             "B3": "유적형 특징 (buffer 200m)", "B4": "전통마을 근접도",
             "ANCHOR": "정답 앵커 — 특징 금지", "NATURE": "뷰포인트 전용 (v1 점수 미반영)",
             "EXCLUDE": "실내·무형 — 미사용", "REVIEW": "수동 검토 필요"}
    for c in ["B1", "B2", "B3", "B4", "ANCHOR", "NATURE", "EXCLUDE", "REVIEW"]:
        L.append(f"| {c} | {cls_cnt.get(c,0)} | {coord_cnt.get((c,'Y'),0)} | {usage[c]} |")

    L.append("\n## 명승 19건 — 앵커 목록 (특징 사용 절대 금지)\n")
    L.append("| 시군 | 이름 | 좌표 |")
    L.append("|---|---|---|")
    for r in sorted((r for r in active if r["b_class"] == "ANCHOR"), key=lambda x: x["ccsiName"]):
        co = f"{float(r['latitude']):.4f}, {float(r['longitude']):.4f}" if r["has_coord"] == "Y" else "결측"
        L.append(f"| {r['ccsiName']} | {r['ccbaMnm1']} | {co} |")

    L.append("\n## 소분류별 정렬 (대분류 > 중분류 > 소분류 > 세분류 → B클래스)\n")
    L.append("| 분류체계 | 건수 | 좌표有 | B클래스 |")
    L.append("|---|---|---|---|")
    tree = defaultdict(lambda: {"n": 0, "co": 0, "cls": Counter()})
    for r in active:
        key = (r["gcodeName"] or "(공란)", r["bcodeName"] or "-", r["mcodeName"] or "-", r["scodeName"] or "-")
        t = tree[key]
        t["n"] += 1
        t["co"] += r["has_coord"] == "Y"
        t["cls"][r["b_class"]] += 1
    for key in sorted(tree, key=lambda k: (k, -tree[k]["n"])):
        t = tree[key]
        cls = "/".join(f"{c}" for c, _ in t["cls"].most_common())
        L.append(f"| {' > '.join(key)} | {t['n']} | {t['co']} | {cls} |")

    rev = [r for r in active if r["b_class"] == "REVIEW"]
    if rev:
        L.append(f"\n## REVIEW 대상 {len(rev)}건 (분류 공란 등 — 수동 배정 필요)\n")
        L.append("| 종목 | 이름 | 시군 | 분류 |")
        L.append("|---|---|---|---|")
        for r in sorted(rev, key=lambda x: x["ccsiName"]):
            L.append(f"| {r['ccmaName']} | {r['ccbaMnm1']} | {r['ccsiName']} | {r['gcodeName']}>{r['bcodeName']} |")

    L.append("\n## 규칙 요약\n")
    L.append("- 등급가중: 국가지정 2.0 / 시도지정 1.5 / 자료·등록 1.0 (`grade_w` 컬럼)")
    L.append("- 좌표 결측 건은 특징 계산에서 제외 (마스터에는 유지)")
    L.append("- 야외/실내 구분: 유물 중 석조·암벽조각만 B2, 나머지(회화·공예·목조·금속조)는 실내 소장품이라 제외")
    L.append("- NATURE(천연기념물 등)는 지질명소 앵커와 겹칠 수 있어 v1에서는 뷰포인트 표시 전용")
    (ROOT / "docs/05_heritage_catalog.md").write_text("\n".join(L), encoding="utf-8")
    print("class counts:", dict(cls_cnt))
    print("saved: data/processed/heritage_gb_mapped.csv, docs/05_heritage_catalog.md")


if __name__ == "__main__":
    main()
