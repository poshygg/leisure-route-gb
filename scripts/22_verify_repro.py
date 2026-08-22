# -*- coding: utf-8 -*-
"""재현성 검증 — 고정 픽스처로 두 데모를 돌려 기대값과 비교한다.

  python scripts/22_verify_repro.py            # 검증 (demos/expected.json 과 비교)
  python scripts/22_verify_repro.py --update   # 기대값 갱신

기대값이 어긋나면 코드 변경이 결과를 바꾼 것이다 — 의도한 변경이면 --update,
아니면 회귀다.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):          # Windows cp949 콘솔 대비
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "demos" / "expected.json"

DEMOS = {
    "gameunsa": ["--from", "35.7482,129.4768", "--to", "35.7444,129.4919"],
    "pohang":   ["--from", "36.0567,129.3785", "--to", "36.0335,129.3650"],
}
ROW = re.compile(
    r"(\d)위 (\d+\.\d+)km 우회 (\d+\.\d+)x 점수 (\d+\.\d+)")


def run(name: str, args: list[str]) -> list[dict]:
    p = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "20_belt_demo.py"),
         *args, "--data", str(ROOT / "demos" / "data"),
         "--out", str(ROOT / "demos" / f"belt_{name}.html")],
        capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise SystemExit(f"[{name}] 실행 실패:\n{p.stdout}\n{p.stderr}")
    rows = [{"rank": int(m[1]), "km": float(m[2]),
             "detour": float(m[3]), "score": float(m[4])}
            for m in ROW.finditer(p.stdout)]
    if not rows:
        raise SystemExit(f"[{name}] 결과 파싱 실패:\n{p.stdout}")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--tol", type=float, default=1e-3)
    args = ap.parse_args()

    got = {name: run(name, a) for name, a in DEMOS.items()}

    if args.update or not EXPECTED.exists():
        EXPECTED.write_text(json.dumps(got, indent=2), encoding="utf-8")
        print(f"기대값 저장: {EXPECTED}")
        return 0

    want = json.loads(EXPECTED.read_text(encoding="utf-8"))
    fails = []
    for name, rows in want.items():
        for w, g in zip(rows, got.get(name, [])):
            for k in ("km", "detour", "score"):
                if abs(w[k] - g[k]) > args.tol:
                    fails.append(f"{name} {w['rank']}위 {k}: 기대 {w[k]} vs 실제 {g[k]}")
        if len(want[name]) != len(got.get(name, [])):
            fails.append(f"{name}: 후보 수 {len(want[name])} vs {len(got[name])}")

    if fails:
        print("❌ 재현 실패:"); [print("  -", f) for f in fails]
        return 1
    print("✅ 재현 성공 — 두 데모 모두 기대값과 일치 (tol", args.tol, ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
