#!/usr/bin/env python3
"""驗證 `data/legacy_wip/` 的舊考題。

這些年份**沒有學會公告的答案卡**，答案取自考卷檔案本身，所以無法像
`validate_questions.py` 那樣逐題核對官方答案。這支只能檢查結構自洽，
以及分類代碼是否落在 `data/taxonomy.json` 裡。

因此舊考題在網站上必須與 108–114 明確區隔，不能混為一談。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QDIR = ROOT / "data" / "legacy_wip"
TAXONOMY = ROOT / "data" / "taxonomy.json"


def check(path, codes):
    errors = []
    warnings = []
    data = json.loads(path.read_text("utf-8"))
    year = data["meta"]["year"]
    questions = data["questions"]

    if data["meta"].get("verified") is not False:
        errors.append(f"{year}: meta.verified 必須是 false（無官方答案卡可核對）")
    if len(questions) != 100:
        errors.append(f"{year}: 題數 {len(questions)}，應為 100")

    seen = set()
    for q in questions:
        n = q["id"]
        tag = f"{year} Q{n}"
        if n in seen:
            errors.append(f"{tag}: 題號重複")
        seen.add(n)

        if not q["question"].strip():
            errors.append(f"{tag}: 題幹是空的")

        options = q["options"]
        if list(options) not in (list("ABCD"), list("ABCDE")):
            errors.append(f"{tag}: 選項標號異常 {list(options)}")

        images = q.get("option_images", {})
        for letter, text in options.items():
            if not text.strip() and letter not in images:
                warnings.append(f"{tag}: 選項 {letter} 沒有文字也沒有圖（可能是圖片題）")

        answer = q["answer"]
        if not re.fullmatch(r"[A-E]", answer or ""):
            errors.append(f"{tag}: 答案格式異常 {answer!r}")
        elif answer not in options:
            errors.append(f"{tag}: 答案 {answer} 無對應選項")

        if q.get("scoring") != "exact":
            errors.append(f"{tag}: scoring 應為 'exact'，實際 {q.get('scoring')!r}")
        if not q.get("answer_source"):
            errors.append(f"{tag}: 缺 answer_source（答案來源必須標明）")
        if q.get("answer_tier") not in ("examiner", "exam_file"):
            errors.append(f"{tag}: answer_tier 應為 examiner 或 exam_file，實際 {q.get('answer_tier')!r}")

        category = q.get("category")
        if category and category not in codes:
            errors.append(f"{tag}: 分類代碼 {category!r} 不在 taxonomy.json 裡")

    labelled = sum(1 for q in questions if q.get("category"))
    tier = questions[0].get("answer_tier") if questions else None
    return year, len(questions), labelled, tier, errors, warnings


def main():
    codes = {c["code"] for c in json.loads(TAXONOMY.read_text("utf-8"))["categories"]}
    files = sorted(QDIR.glob("*_legacy.json"), key=lambda p: int(p.name.split("_")[0]))
    if not files:
        print("找不到舊考題檔案")
        return 1

    total = 0
    all_errors = []
    all_warnings = []
    for path in files:
        year, count, labelled, tier, errors, warnings = check(path, codes)
        total += count
        all_errors += errors
        all_warnings += warnings
        status = "OK" if not errors else f"{len(errors)} 項問題"
        bits = []
        if labelled:
            bits.append(f"有官方分類 {labelled} 題")
        bits.append("答案來自命題端檔案" if tier == "examiner" else "答案取自考卷檔案")
        print(f"民國 {year}：{count} 題 — {status}（{'、'.join(bits)}）")
        for e in errors[:10]:
            print(f"    ✗ {e}")
        for w in warnings[:5]:
            print(f"    ! {w}")

    print()
    print(f"共 {total} 題。**這些年份沒有學會公開公告的答案卡。**")
    print("104／106 年的答案來自命題端檔案（附教科書出處）；其餘取自考卷檔案本身。")
    print("跨年重複題的交叉驗證請跑 tools/crosscheck_legacy.py。")
    if all_errors:
        print(f"發現 {len(all_errors)} 項結構問題。")
        return 1
    if all_warnings:
        print(f"結構全部通過，另有 {len(all_warnings)} 項待確認（多為圖片題）。")
        return 0
    print("結構全部通過。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
