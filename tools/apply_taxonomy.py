#!/usr/bin/env python3
"""把 `audit/taxonomy_assign/<年>.json` 的分類結果套進題庫。

108–114 年的官方檔案沒有分類欄位（只有 104／106 年的舊考卷有學會自己標的），
所以這幾年的分類是**依 104／106 的標記慣例推定的**，不是學會公告。
因此一併寫入 `category_source`，網站上要與有官方標記的年份區隔。

重跑 `parse_official.py` 會覆蓋題庫檔，這支要跟著再跑一次。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QDIR = ROOT / "data" / "questions"
ASSIGN = ROOT / "audit" / "taxonomy_assign"
TAXONOMY = ROOT / "data" / "taxonomy.json"


def main():
    codes = {c["code"] for c in json.loads(TAXONOMY.read_text("utf-8"))["categories"]}
    files = sorted(ASSIGN.glob("*.json"))
    if not files:
        print(f"找不到分類結果（{ASSIGN}）")
        return 1

    problems = []
    for path in files:
        year = int(path.stem)
        target = QDIR / f"{year}_written.json"
        if not target.exists():
            problems.append(f"{year}: 找不到題庫檔 {target.name}")
            continue

        assign = json.loads(path.read_text("utf-8"))
        bad = {k: v for k, v in assign.items() if v not in codes}
        if bad:
            problems.append(f"{year}: 有不合法的代碼 {bad}")
            continue

        data = json.loads(target.read_text("utf-8"))
        applied = 0
        missing = []
        for q in data["questions"]:
            code = assign.get(str(q["id"]))
            if code:
                q["category"] = code
                q["category_source"] = "依 104／106 年學會標記慣例推定"
                applied += 1
            else:
                missing.append(q["id"])
        target.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
        print(f"{year}: 套用 {applied} 題" + (f"，缺 {missing}" if missing else ""))
        if missing:
            problems.append(f"{year}: {len(missing)} 題沒有分類")

    if problems:
        print()
        for p in problems:
            print("  ✗", p)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
