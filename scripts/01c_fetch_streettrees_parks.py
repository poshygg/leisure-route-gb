"""가로수길·도시공원 표준데이터 전국 다운로드 → 경북 필터.

키: .env의 DATA_GO_KR_KEY_ENC (Encoding 키 원문 그대로 URL 삽입 — 재인코딩 금지)
출력: data/raw/streettrees/sttree_all.csv, data/raw/parks/parks_all.csv (+경북 필터본)
"""
import csv
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = next(l.split("=", 1)[1].strip() for l in open(ROOT / ".env", encoding="utf-8")
           if l.startswith("DATA_GO_KR_KEY_ENC="))

APIS = {
    "streettrees": ("https://api.data.go.kr/openapi/tn_pubr_public_sttree_stret_api", "sttree"),
    "parks": ("https://api.data.go.kr/openapi/tn_pubr_public_cty_park_info_api", "parks"),
}


def fetch_all(base):
    rows, page = [], 1
    while True:
        url = f"{base}?serviceKey={KEY}&pageNo={page}&numOfRows=1000&type=json"
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    doc = json.loads(r.read().decode("utf-8"))
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2)
        body = doc.get("body") or (doc.get("response") or {}).get("body") or {}
        items = ((body.get("items") or {}).get("item")) or []
        if isinstance(items, dict):
            items = [items]
        rows.extend(items)
        total = int(body.get("totalCount", 0))
        print(f"  page {page}: {len(rows)}/{total}", flush=True)
        if len(rows) >= total or not items:
            return rows
        page += 1


def save(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted({k for r in rows for k in r})
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f"saved {len(rows)} -> {path}")


def main():
    for name, (base, _) in APIS.items():
        print(f"[{name}]")
        rows = fetch_all(base)
        save(rows, ROOT / f"data/raw/{name}/{name}_all.csv")
        gb = [r for r in rows if "경상북도" in (r.get("insttNm") or "") or
              "경상북도" in (r.get("institutionNm") or "") or
              (r.get("lnmadr") or "").startswith("경상북도") or
              (r.get("rdnmadr") or "").startswith("경상북도")]
        save(gb, ROOT / f"data/raw/{name}/{name}_gb.csv")


if __name__ == "__main__":
    main()
