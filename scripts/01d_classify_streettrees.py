"""가로수길 수종 → species_dict 조회로 활엽/침엽/화목/단풍 분류.

입력: data/raw/streettrees/streettrees_gb.csv, config/species_dict.csv
출력: data/processed/streettrees_gb_classified.csv, data/interim/unknown_species.log
"""
import csv
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 사전 로드: canonical + 별칭 → 속성
DICT = {}
for r in csv.DictReader(open(ROOT / "config/species_dict.csv", encoding="utf-8")):
    names = [r["canonical"]] + ([a for a in r["aliases"].split("|") if a != "-"] if r["aliases"] else [])
    for n in names:
        DICT[n] = r

# 흔한 접두·변형 정규화 (사전 키 조회 전 적용)
NORM = [("벛", "벚"), ("느time나무", "느티나무")]


def lookup(raw):
    s = raw.strip().replace(" ", "")
    for a, b in NORM:
        s = s.replace(a, b)
    if not s or s in ("기타", "-"):
        return None, s
    if s in DICT:
        return DICT[s], s
    # 부분일치: 사전 키가 수종명에 포함 (예: "왕벚나무류" ← "벚")
    for k in sorted(DICT, key=len, reverse=True):
        if k in s or s in k:
            return DICT[k], s
    return None, s


def main():
    rows = list(csv.DictReader(open(ROOT / "data/raw/streettrees/streettrees_gb.csv", encoding="utf-8-sig")))
    unknown = Counter()
    out = []
    for r in rows:
        # 수종 분리: + , · / 및 공백 나열
        parts = [p for p in re.split(r"[+,·/]|\s{2,}", r.get("sttreeKnd") or "") if p.strip()]
        n_total = int(float(r.get("sttreeCo") or 0)) or len(parts)  # 본수 없으면 종수로 대체
        per = n_total / max(len(parts), 1)
        agg = Counter()
        matched = []
        for p in parts:
            d, norm = lookup(p)
            if d is None:
                unknown[norm] += 1
                continue
            matched.append(d["canonical"])
            agg["broadleaf"] += per * (d["leaf_type"] == "활엽")
            agg["conifer"] += per * (d["leaf_type"] == "침엽")
            agg["flowering"] += per * (d["flowering"] == "Y")
            agg["foliage"] += per * (d["foliage"] == "Y")
            agg["evergreen"] += per * (d["evergreen"] == "Y")
            agg["known"] += per
        out.append({
            "name": r.get("sttreeStretNm"), "sigungu": (r.get("insttNm") or "").replace("경상북도 ", ""),
            "start_lat": r.get("startLatitude"), "start_lon": r.get("startLongitude"),
            "end_lat": r.get("endLatitude"), "end_lon": r.get("endLongitude"),
            "length_m": r.get("sttreeStretLt"), "tree_count": n_total,
            "species_raw": r.get("sttreeKnd"), "species_matched": "|".join(dict.fromkeys(matched)),
            "ratio_broadleaf": round(agg["broadleaf"] / n_total, 3) if n_total else 0,
            "ratio_conifer": round(agg["conifer"] / n_total, 3) if n_total else 0,
            "ratio_flowering": round(agg["flowering"] / n_total, 3) if n_total else 0,
            "ratio_foliage": round(agg["foliage"] / n_total, 3) if n_total else 0,
            "ratio_evergreen": round(agg["evergreen"] / n_total, 3) if n_total else 0,
            "match_rate": round(agg["known"] / n_total, 3) if n_total else 0,
        })

    outp = ROOT / "data/processed/streettrees_gb_classified.csv"
    outp.parent.mkdir(parents=True, exist_ok=True)
    with open(outp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    logp = ROOT / "data/interim/unknown_species.log"
    logp.parent.mkdir(parents=True, exist_ok=True)
    logp.write_text("\n".join(f"{k}\t{v}" for k, v in unknown.most_common()), encoding="utf-8")

    n = len(out)
    full = sum(1 for o in out if o["match_rate"] >= 0.999)
    print(f"구간 {n}개 | 완전매칭 {full} ({100*full/n:.0f}%) | 미확인 수종 {len(unknown)}종")
    print("미확인 상위:", unknown.most_common(12))
    fl = sum(1 for o in out if o["ratio_flowering"] > 0.5)
    print(f"화목 우세(>50%) 구간: {fl}")


if __name__ == "__main__":
    main()
