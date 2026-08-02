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
    notes = []
    data = json.loads(path.read_text("utf-8"))
    year = data["meta"]["year"]
    questions = data["questions"]

    if data["meta"].get("verified") is not False:
        errors.append(f"{year}: meta.verified 必須是 false（無官方答案卡可核對）")
    if len(questions) != 100:
        errors.append(f"{year}: 題數 {len(questions)}，應為 100")

    seen = set()
    seen_whole = {}
    for q in questions:
        n = q["id"]
        tag = f"{year} Q{n}"
        if n in seen:
            errors.append(f"{tag}: 題號重複")
        seen.add(n)

        if not q["question"].strip():
            errors.append(f"{tag}: 題幹是空的")
        for name in q.get("images", []):
            if not (ROOT / "images" / name).exists():
                errors.append(f"{tag}: 找不到圖檔 {name}")

        # 原檔本身就缺答案或選項的題目，標成 unscored 只供閱讀，不套用完整性檢查
        incomplete = q.get("incomplete")
        options = q["options"]
        if not incomplete and list(options) not in (list("ABCD"), list("ABCDE")):
            errors.append(f"{tag}: 選項標號異常 {list(options)}")

        images = q.get("option_images", {})
        for letter, text in options.items():
            if not text.strip() and letter not in images:
                warnings.append(f"{tag}: 選項 {letter} 沒有文字也沒有圖（可能是圖片題）")

        # 整題（題幹＋選項）與另一題完全相同，多半是切分器把某一題重複抓了兩次
        # ——100 年的 Q100 一度是第 1 題的複本，真正的第 100 題整題遺失。
        whole = q["question"].strip() + "||" + "|".join(options.values())
        if whole in seen_whole:
            errors.append(f"{tag}: 與 Q{seen_whole[whole]} 整題完全相同")
        seen_whole[whole] = n

        answer = q["answer"]
        # 題幹自己寫「本題送分」的，判分必須是 free，否則作答的人會被判錯
        if re.search(r"送\s*分", q["question"]) and q.get("scoring") != "free":
            errors.append(f"{tag}: 題幹寫明送分，scoring 應為 'free'，實際 {q.get('scoring')!r}")

        # 複合題（選項是「1+2+3」這種組合）的題幹必須有對應編號的敘述，
        # 否則讀者無從得知哪一句是 1、哪一句是 2，題目根本無法作答
        combo = [t for t in options.values() if re.fullmatch(r"\s*(?:僅\s*)?\d(?:\s*\+\s*\d)+\s*", t)]
        if combo:
            # 編號寫法各年不同：101 年是「1. 」、102／103 年是「(1)」後面直接接內文
            listed = [int(a or b) for a, b in
                      re.findall(r"(?:^|\s)(?:\((\d)\)|(\d)[.、]\s)", q["question"])]
            used = {int(d) for t in combo for d in re.findall(r"\d", t)}
            if not listed:
                errors.append(f"{tag}: 選項是數字組合，但題幹沒有編號敘述")
            elif used and max(used) > max(listed):
                errors.append(
                    f"{tag}: 選項用到編號 {max(used)}，題幹只有 {max(listed)} 個敘述")

        if incomplete:
            if q.get("scoring") != "unscored":
                errors.append(f"{tag}: 原檔不完整，scoring 應為 'unscored'")
            warnings.append(f"{tag}: {'；'.join(incomplete)}（不計分）")
        elif q.get("scoring") == "free":
            if answer != "送分":
                errors.append(f"{tag}: 送分題的 answer 應為 '送分'，實際 {answer!r}")
        else:
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

    # 分官方與推定：104／106 年是學會自己標的，其餘是依其慣例推定（有 category_source）
    official = sum(1 for q in questions if q.get("category") and not q.get("category_source"))
    guessed = sum(1 for q in questions if q.get("category") and q.get("category_source"))
    tier = questions[0].get("answer_tier") if questions else None
    return year, len(questions), official, guessed, tier, errors, warnings


def main():
    codes = {c["code"] for c in json.loads(TAXONOMY.read_text("utf-8"))["categories"]}
    files = sorted(QDIR.glob("*_legacy.json"), key=lambda p: int(p.name.split("_")[0]))
    if not files:
        print("找不到舊考題檔案")
        return 1

    total = 0
    total_cat = 0
    all_errors = []
    all_warnings = []
    for path in files:
        year, count, official, guessed, tier, errors, warnings = check(path, codes)
        total += count
        total_cat += official + guessed
        all_errors += errors
        all_warnings += warnings
        status = "OK" if not errors else f"{len(errors)} 項問題"
        bits = []
        if official:
            bits.append(f"官方分類 {official} 題")
        if guessed:
            bits.append(f"推定分類 {guessed} 題")
        bits.append("答案來自命題端檔案" if tier == "examiner" else "答案取自考卷檔案")
        print(f"民國 {year}：{count} 題 — {status}（{'、'.join(bits)}）")
        for e in errors[:10]:
            print(f"    ✗ {e}")
        for w in warnings[:5]:
            print(f"    ! {w}")

    print()
    print(f"共 {total} 題，其中 {total_cat} 題有分類代碼"
          f"（沒有分類的題目進不了分類練習）。")
    print("**這些年份學會網站沒有公開公告的答案卡可交叉核對。**")
    print("答案本身是隨學會發出的考卷檔案一併附上的；104／106 年的檔案還附了教科書出處。")
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
