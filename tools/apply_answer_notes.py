#!/usr/bin/env python3
"""替多答案題補上公告出處。

答案卡上有兩個字母的題目，全部來自事後申覆或委員會決議，不是複選題
（有卷首說明的年份都寫「單選題」，113 年還寫明 Single Best Answer）。
判分方式因此是「選其中任一個字母都算對」（`scoring: "any"`）。

重跑 `parse_official.py` 會覆蓋題庫檔，所以這支要跟著再跑一次。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QDIR = ROOT / "data" / "questions"

APPEAL = "110 年公告標題註明「經申覆會議討論決議」"
APPEAL111 = "111 年公告標題註明「經申覆會議討論決議」"
COMMITTEE112 = "112 年 10/25 經專甄暨筆試委員會決議更新答案（答案卡紅字）"
COMMITTEE113 = "113 年 10/21 經專甄暨筆試委員會決議更新第 23、24、74 題答案，答案卡寫「A B」"

NOTES = {
    (110, 83): f"{APPEAL}，答案卡寫 C/D",
    (111, 40): f"{APPEAL111}，答案卡寫 BE",
    (111, 53): f"{APPEAL111}，答案卡寫 AD",
    (112, 7): COMMITTEE112,
    (112, 18): COMMITTEE112,
    (112, 40): COMMITTEE112,
    (112, 67): COMMITTEE112,
    (112, 92): COMMITTEE112,
    (112, 100): COMMITTEE112,
    (113, 74): COMMITTEE113,
}


def main():
    for path in sorted(QDIR.glob("*_written.json")):
        data = json.loads(path.read_text("utf-8"))
        year = data["meta"]["year"]
        applied = 0
        missing = []
        for q in data["questions"]:
            note = NOTES.get((year, q["id"]))
            if note:
                q["answer_note"] = note
                q["multi_answer_origin"] = "appeal"
                applied += 1
            elif q.get("scoring") == "any":
                missing.append(q["id"])
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
        print(f"{year}: 補上 {applied} 則出處" + (f"，⚠️ 未登錄的多答案題 {missing}" if missing else ""))


if __name__ == "__main__":
    main()
