#!/usr/bin/env python3
"""抽出 2004–2006 年的舊考卷。

這三年沒有官方答案卡公告，答案是夾在考卷檔案裡的：

  2004：每題題號前有答案前綴，形如「(B)  1. 一位產婦…」
  2005：Word 追蹤註解，形如「註解 [S91]: MM.Ans: C 出題參考處：Anesthesia, 5th…」
  2006：同樣是註解，形如「註解 [x]: 答案C   p1668」

註解在 PDF 文字層裡是整頁的題目之後才一次出現（Word 把註解印在頁尾側欄），
所以採「逐頁按順序配對」：這一頁有幾題，就依序配這一頁的幾則註解。

輸出 `data/questions/<年>_legacy.json`。這些年份的答案沒有官方公告可核對，
因此另外標記 `answer_source`，網站上要顯示成與 109–114 不同的可信度。
"""
import json
import re
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source" / "legacy"
OUT = ROOT / "data" / "legacy_wip"   # 尚未達到可上線品質，與已驗證題庫分開放

ANN = re.compile(r"註解\s*\[[^\]]*\]:\s*([^\n]*)")
ANSWER_IN_ANN = re.compile(r"(?:ans|ane|答案)\s*[:：]?\s*([A-Ea-e])")


def tidy(s):
    s = re.sub(r"[ \t]*\n[ \t]*", " ", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip(" 　")


def split_options(block, pattern):
    marks = list(re.finditer(pattern, block))
    if not marks:
        return tidy(block), {}
    stem = tidy(block[: marks[0].start()])
    options = {}
    for i, m in enumerate(marks):
        letter = m.group(1).upper()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(block)
        if letter not in options:
            options[letter] = tidy(block[m.end():end])
    return stem, options


def parse_2004(path):
    """答案就寫在題號前面：「(B)  1. …」"""
    text = "".join(p.get_text() for p in fitz.open(path))
    marks = list(re.finditer(r"[（(]\s*([A-E])\s*[）)]\s*(\d{1,3})\.\s*", text))
    out = {}
    expect = 1
    for i, m in enumerate(marks):
        n = int(m.group(2))
        if n != expect:
            continue
        end = len(text)
        for later in marks[i + 1:]:
            if int(later.group(2)) == n + 1:
                end = later.start()
                break
        stem, options = split_options(text[m.end():end], r"[（(]\s*([A-E])\s*[）)]")
        out[n] = (stem, options, m.group(1), None)
        expect += 1
    return out


def parse_annotated(path, qnum_pattern, opt_pattern):
    """2005／2006：逐頁把題目與註解按順序配對。"""
    doc = fitz.open(path)
    out = {}
    expect = 1
    for page in doc:
        text = page.get_text()
        body = ANN.sub("", text)       # 把註解整段抽掉，剩下的才是題目
        annotations = ANN.findall(text)

        marks = [m for m in re.finditer(qnum_pattern, body) if 1 <= int(m.group(1)) <= 100]
        picked = []
        for i, m in enumerate(marks):
            n = int(m.group(1))
            if n != expect:
                continue
            end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
            stem, options = split_options(body[m.end():end], opt_pattern)
            # 卷首的「1. 請將試卷…2. 請至一樓…」也是編號清單，用選項數擋掉
            if len(options) < 2 and n <= 3:
                continue
            picked.append((n, stem, options))
            expect += 1

        for idx, (n, stem, options) in enumerate(picked):
            note = annotations[idx] if idx < len(annotations) else ""
            m = ANSWER_IN_ANN.search(note)
            out[n] = (stem, options, m.group(1).upper() if m else "", tidy(note))
    return out


PARSERS = {
    2004: lambda: parse_2004(SRC / "2004_筆試.pdf"),
    2005: lambda: parse_annotated(SRC / "2005_筆試.pdf", r"(?m)^\s*(\d{1,3})[、.]\s", r"(?m)^\s*([A-Ea-e])[.、]\s"),
    2006: lambda: parse_annotated(SRC / "2006_筆試.pdf", r"(?m)^\s*(\d{1,3})[、.]\s", r"(?m)^\s*([A-Ea-e])[.、]\s"),
}


def build(year):
    parsed = PARSERS[year]()
    questions = []
    problems = []
    for n in range(1, 101):
        if n not in parsed:
            problems.append(f"Q{n} 未抽到")
            continue
        stem, options, answer, note = parsed[n]
        if len(options) < 4:
            problems.append(f"Q{n} 只抽到 {len(options)} 個選項")
        if not answer:
            problems.append(f"Q{n} 無答案")
        elif answer not in options:
            problems.append(f"Q{n} 答案 {answer} 無對應選項")
        q = {
            "id": n,
            "year": year,
            "question": stem,
            "options": options,
            "answer": answer,
            "answer_source": "考卷內附（非學會公告答案卡）",
            "source": f"{year}_written_Q{n}",
        }
        if note:
            q["answer_note"] = note
        questions.append(q)

    data = {
        "meta": {
            "year": year,
            "role": "doctor",
            "subject": "written",
            "subject_name": "筆試",
            "total": len(questions),
            "source": "台灣麻醉醫學會歷年甄審筆試考卷（無官方答案卡公告）",
            "verified": False,
            "extracted_by": "tools/parse_legacy.py",
        },
        "questions": questions,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{year}_legacy.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), "utf-8"
    )
    return len(questions), problems


def main():
    years = [int(a) for a in sys.argv[1:]] or sorted(PARSERS)
    for year in years:
        count, problems = build(year)
        print(f"{year}: 抽出 {count} 題，問題 {len(problems)} 項")
        for p in problems[:10]:
            print(f"    - {p}")
        if len(problems) > 10:
            print(f"    …另有 {len(problems) - 10} 項")


if __name__ == "__main__":
    main()
