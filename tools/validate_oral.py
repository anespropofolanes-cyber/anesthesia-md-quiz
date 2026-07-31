#!/usr/bin/env python3
"""驗證口試與超音波資料。

這些內容是照抄學會原檔的官方參考答案，不是自己寫的，所以檢查重點在
「有沒有抄漏、有沒有錯位」：子題配分要剛好 100%、圖檔要指得到、
標題不能是從內文誤切出來的碎片。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QDIR = ROOT / "data" / "oral"
IMGDIR = ROOT / "images"

# 學會確實沒有公布參考答案的年份，不該被當成抽取失敗。
# 這幾年的原檔通篇找不到「解答」或「參考答案」字樣，只有題目與配分。
NO_OFFICIAL_ANSWER = {110, 113, 114}


def check_oral(path):
    errors, notes = [], []
    data = json.loads(path.read_text("utf-8"))
    year = data["meta"]["year"]

    for q in data["questions"]:
        tag = f"{year} {q['title']}"
        if not q["scenario"].strip():
            errors.append(f"{tag}: 情境是空的")

        subs = q["subquestions"]
        if not subs:
            errors.append(f"{tag}: 沒有子題")
            continue

        total = sum(s["weight"] for s in subs)
        if total != 100:
            errors.append(f"{tag}: 配分合計 {total}%，應為 100%")

        for i, s in enumerate(subs, 1):
            if len(s["title"].strip()) < 4:
                errors.append(f"{tag} 子題{i}: 標題過短「{s['title']}」，可能切錯")
            if re.match(r"^[IVX]+\.|^\d+\.\s*[A-Za-z]{0,3}$", s["title"].strip()):
                errors.append(f"{tag} 子題{i}: 標題像是內文碎片「{s['title'][:20]}」")

        for name in [n for s in subs for n in s.get("reference_images", [])] + q.get("scenario_images", []):
            if not (IMGDIR / name).exists():
                errors.append(f"{tag}: 找不到圖檔 {name}")

        if not q["has_reference"] and year not in NO_OFFICIAL_ANSWER:
            errors.append(f"{tag}: 完全沒抽到參考答案（該年應該有）")
        if not q["has_reference"] and year in NO_OFFICIAL_ANSWER:
            notes.append(f"{tag}: 學會未公布參考答案")

    return year, len(data["questions"]), errors, notes


def check_ultrasound(path):
    errors = []
    data = json.loads(path.read_text("utf-8"))
    for q in data["questions"]:
        tag = f"108 {q['title']}"
        for field, label in [("task", "題目"), ("grading", "評分標準"), ("criteria", "逐項參考答案")]:
            if not q[field].strip():
                errors.append(f"{tag}: {label}是空的")
        for name in q.get("images", []):
            if not (IMGDIR / name).exists():
                errors.append(f"{tag}: 找不到圖檔 {name}")
    return len(data["questions"]), errors


def main():
    all_errors, all_notes, total = [], [], 0

    for path in sorted(QDIR.glob("*_oral.json")):
        year, n, errors, notes = check_oral(path)
        total += n
        all_errors += errors
        all_notes += notes
        print(f"{year} 口試：{n} 題 — {'OK' if not errors else f'{len(errors)} 項問題'}")
        for e in errors:
            print(f"    ✗ {e}")

    us_path = QDIR / "108_ultrasound.json"
    if us_path.exists():
        n, errors = check_ultrasound(us_path)
        total += n
        all_errors += errors
        print(f"108 超音波：{n} 站 — {'OK' if not errors else f'{len(errors)} 項問題'}")
        for e in errors:
            print(f"    ✗ {e}")

    print()
    for note in all_notes:
        print(f"  · {note}")
    if all_errors:
        print(f"共 {total} 題，發現 {len(all_errors)} 項問題。")
        return 1
    print(f"共 {total} 題，全部通過。內容照抄學會原檔，未經改寫。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
