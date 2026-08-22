"""경북 국가유산 전건 다운로드 (국가유산청 Open API, 키 불필요).

목록 API로 전건 수집 후 상세 API에서 4단 분류체계를 붙인다.
출력: data/raw/heritage/heritage_gb.csv
"""
import csv
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = "https://www.cha.go.kr/cha"
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "heritage"
OUT_DIR.mkdir(parents=True, exist_ok=True)

LIST_FIELDS = ["ccmaName", "ccbaMnm1", "ccbaCtcdNm", "ccsiName", "ccbaAdmin",
               "ccbaKdcd", "ccbaCtcd", "ccbaAsno", "ccbaCncl", "ccbaCpno",
               "longitude", "latitude"]
DT_FIELDS = ["gcodeName", "bcodeName", "mcodeName", "scodeName", "ccbaLcad", "ccceName"]


def fetch(url, retries=3):
    for i in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(1.5 * (i + 1))


def parse_items(xml, fields):
    items = []
    for m in re.finditer(r"<item>(.*?)</item>", xml, re.S):
        block = m.group(1)
        row = {}
        for f in fields:
            fm = re.search(rf"<{f}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{f}>", block, re.S)
            row[f] = fm.group(1).strip() if fm else ""
        items.append(row)
    return items


def parse_detail(xml):
    row = {}
    for f in DT_FIELDS:
        fm = re.search(rf"<{f}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{f}>", xml, re.S)
        row[f] = fm.group(1).strip() if fm else ""
    return row


def main():
    # 1) 목록 전건 (경북 ccbaCtcd=37)
    all_items = []
    page = 1
    while True:
        xml = fetch(f"{BASE}/SearchKindOpenapiList.do?ccbaCtcd=37&pageUnit=500&pageIndex={page}")
        total = int(re.search(r"<totalCnt>(\d+)</totalCnt>", xml).group(1))
        items = parse_items(xml, LIST_FIELDS)
        if not items:
            break
        all_items.extend(items)
        print(f"list page {page}: +{len(items)} (total {len(all_items)}/{total})", flush=True)
        if len(all_items) >= total:
            break
        page += 1

    # 2) 상세 병렬 수집 (분류체계 4단)
    def get_detail(it):
        url = (f"{BASE}/SearchKindOpenapiDt.do?ccbaKdcd={it['ccbaKdcd']}"
               f"&ccbaAsno={it['ccbaAsno']}&ccbaCtcd={it['ccbaCtcd']}")
        it.update(parse_detail(fetch(url)))
        return it

    done = 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = [ex.submit(get_detail, it) for it in all_items]
        for _ in as_completed(futs):
            done += 1
            if done % 250 == 0:
                print(f"detail {done}/{len(all_items)}", flush=True)

    # 3) 저장
    out = OUT_DIR / "heritage_gb.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=LIST_FIELDS + DT_FIELDS)
        w.writeheader()
        w.writerows(all_items)
    print(f"saved {len(all_items)} rows -> {out}")


if __name__ == "__main__":
    main()
