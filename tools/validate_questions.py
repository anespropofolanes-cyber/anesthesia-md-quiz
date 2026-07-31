#!/usr/bin/env python3
"""結構驗證 + 答案與官方答案卡逐題核對。

任何改動題庫的動作之後都要跑這支，全部通過才可以部署。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QDIR = ROOT / "data" / "questions"
KDIR = ROOT / "source" / "answer_keys"


def check_year(path):
    errors = []
    data = json.loads(path.read_text("utf-8"))
    year = data["meta"]["year"]
    questions = data["questions"]

    key_path = KDIR / f"answer_key_{year}.json"
    key = {int(k): v for k, v in json.loads(key_path.read_text("utf-8")).items()}

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
        letters = list(options)
        if letters not in (list("ABCD"), list("ABCDE")):
            errors.append(f"{tag}: 選項標號異常 {letters}")
        option_images = q.get("option_images", {})
        for letter, text in options.items():
            # 選項本身是圖的題目（波形圖辨識）文字會是空的，此時必須有對應圖檔
            if not text.strip() and letter not in option_images:
                errors.append(f"{tag}: 選項 {letter} 沒有文字也沒有圖")

        for name in list(q.get("images", [])) + list(option_images.values()):
            if not (ROOT / "images" / name).exists():
                errors.append(f"{tag}: 找不到圖檔 {name}")

        answer = q["answer"]
        # scoring 決定 PWA 怎麼判分，必須與 answer 的形狀一致
        scoring = q.get("scoring")
        expected_scoring = (
            "free" if answer == "送分" else "any" if len(answer or "") > 1 else "exact"
        )
        if scoring != expected_scoring:
            errors.append(f"{tag}: scoring 應為 {expected_scoring!r}，實際 {scoring!r}")
        if scoring == "any" and not q.get("answer_note"):
            errors.append(f"{tag}: 多答案題缺 answer_note（要記錄公告怎麼寫）")

        official = key.get(n)
        if official is None:
            errors.append(f"{tag}: 官方答案卡查無此題")
        elif answer != official:
            errors.append(f"{tag}: 答案 {answer!r} 與官方 {official!r} 不一致")

        if answer != "送分":
            if not re.fullmatch(r"[A-E]+", answer or ""):
                errors.append(f"{tag}: 答案格式異常 {answer!r}")
            elif list(answer) != sorted(answer):
                errors.append(f"{tag}: 複選答案未遞增排序 {answer!r}")
            else:
                for letter in answer:
                    if letter not in options:
                        errors.append(f"{tag}: 答案 {letter} 無對應選項")
    return year, len(questions), errors


def main():
    files = sorted(QDIR.glob("*_written.json"))
    if not files:
        print("找不到題庫檔案")
        return 1

    all_errors = []
    total = 0
    for path in files:
        year, count, errors = check_year(path)
        total += count
        all_errors += errors
        status = "OK" if not errors else f"{len(errors)} 項問題"
        print(f"{year} 筆試：{count} 題 — {status}")
        for e in errors[:15]:
            print(f"    - {e}")
        if len(errors) > 15:
            print(f"    …另有 {len(errors) - 15} 項")

    print()
    if all_errors:
        print(f"共 {total} 題，發現 {len(all_errors)} 項問題。")
        return 1
    print(f"共 {total} 題，結構全部通過，答案全部與官方公告一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
