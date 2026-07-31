#!/usr/bin/env python3
"""抽出 2013–2018 年的舊考卷（民國 102／103／104／106／107 年）。

這四年都有獨立的答案來源，格式又比 2003–2006 規整，所以先做這幾年。

  2013／2014／2015／2017：同一套出題系統匯出的 PDF，版面是

      QUESTION 12
      <題幹>
      A. <選項>
      B. <選項>
      Correct Answer: B
      Explanation
      Explanation/Reference: 出處：Miller 8ed, 14:323-324  難易度：A  分類：B1麻醉生理

    題目檔與答案檔的題幹相同，答案檔多了 `Correct Answer` 與出處／難易度／分類。
    2014 年題目與答案在同一個檔案裡。

  2018：docx，題號與選項都是 Word 自動編號（同 114 年），答案另一個 docx，
    內容是「答案列印 1. B 2. A …」。

輸出 `data/legacy_wip/<年>_legacy.json`。**這些年份沒有學會公告的答案卡可核對**，
答案來自考卷檔案本身，因此 meta 標 `verified: false`，網站上要與 108–114 區隔。
"""
import json
import re
import sys
import zipfile
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source" / "legacy_src"
OUT = ROOT / "data" / "legacy_wip"

OPTION_LETTERS = "ABCDE"
QUESTION = re.compile(r"QUESTION\s+(\d{1,3})\b")
CORRECT = re.compile(r"Correct\s*Answer\s*[:：]\s*([A-E])", re.I)
# 出處／難易度／分類是各自獨立的一行，不是接在 Explanation/Reference 後面
META_FIELDS = {
    "reference": re.compile(r"出處\s*[:：]\s*([^\n]+)"),
    "difficulty": re.compile(r"難易度\s*[:：]\s*([^\n]+)"),
    "category": re.compile(r"分類\s*[:：]\s*([^\n]+)"),
}


def tidy(s):
    s = re.sub(r"[ \t]*\n[ \t]*", " ", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip(" 　")


def docx_paragraphs(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    out = []
    for para in re.split(r"</w:p>", xml):
        text = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", para))
        text = re.sub(r"&lt;", "<", re.sub(r"&gt;", ">", re.sub(r"&amp;", "&", text)))
        text = text.replace(" ", " ").strip()
        if not text:
            continue
        num_id = re.search(r'<w:numId w:val="(\d+)"', para)
        ilvl = re.search(r'<w:ilvl w:val="(\d+)"', para)
        is_stem = bool(num_id and ilvl and ilvl.group(1) == "0")
        out.append((is_stem, text))
    return out


def parse_question_n(path):
    """2014／2015／2017 的 `QUESTION N` 版面。"""
    text = "".join(p.get_text() for p in fitz.open(path))
    marks = list(QUESTION.finditer(text))
    parsed = {}
    for i, m in enumerate(marks):
        n = int(m.group(1))
        if not 1 <= n <= 100 or n in parsed:
            continue
        block = text[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        # 同一個題號可能出現兩次（2017 年 Q47 有一段只有「分類：B1」的殘留），
        # 真正的題目那次才會有選項
        if not re.search(r"(?m)^\s*[A-E][.、]\s", block):
            continue

        answer_match = CORRECT.search(block)
        answer = answer_match.group(1).upper() if answer_match else ""

        # Correct Answer 之後是解析與出處，不屬於題目本體
        body = block[: answer_match.start()] if answer_match else block
        extra = block[answer_match.end():] if answer_match else ""

        opt_marks = [
            om for om in re.finditer(r"(?m)^\s*([A-E])[.、]\s", body)
        ]
        if opt_marks:
            stem = tidy(body[: opt_marks[0].start()])
            options = {}
            for j, om in enumerate(opt_marks):
                letter = om.group(1)
                end = opt_marks[j + 1].start() if j + 1 < len(opt_marks) else len(body)
                if letter not in options:
                    options[letter] = tidy(body[om.end():end])
        else:
            stem, options = tidy(body), {}

        meta = {}
        for key, pattern in META_FIELDS.items():
            hit = pattern.search(extra)
            if hit:
                meta[key] = tidy(hit.group(1))
        parsed[n] = (stem, options, answer, meta)
    return parsed


def parse_2018():
    """題目 docx（Word 自動編號）＋ 答案 docx（答案列印清單）。"""
    paragraphs = docx_paragraphs(SRC / "2018" / "2018_筆試題目.docx")
    parsed = {}
    qno = 0
    current = None
    for is_stem, text in paragraphs:
        if is_stem:
            qno += 1
            if qno > 100:
                break
            current = {"stem": text, "options": {}}
            parsed[qno] = current
        elif current is not None:
            text = re.sub(r"^\(?([A-E])\)?[.、]\s*", "", text)
            idx = len(current["options"])
            if idx < len(OPTION_LETTERS):
                current["options"][OPTION_LETTERS[idx]] = text

    answer_text = " ".join(t for _, t in docx_paragraphs(SRC / "2018" / "2018_筆試答案.docx"))
    key = {int(n): a for n, a in re.findall(r"(\d{1,3})\.\s*([A-E])", answer_text)}

    return {
        n: (v["stem"], v["options"], key.get(n, ""), {})
        for n, v in parsed.items()
    }


PARSERS = {
    2013: lambda: parse_question_n(SRC / "2013" / "2013_筆試.pdf"),
    2014: lambda: parse_question_n(SRC / "2014" / "2014_board_exam_answer.pdf"),
    2015: lambda: parse_question_n(SRC / "2015" / "104年專甄考古題(筆試題目-解答).pdf"),
    2017: lambda: parse_question_n(SRC / "2017" / "2017_written_ans.pdf"),
    2018: parse_2018,
}

ROC = {2013: 102, 2014: 103, 2015: 104, 2017: 106, 2018: 107}

# 答案的可信度分兩級。104／106 的檔案每題都附教科書出處、難易度與分類代碼——
# 那是命題委員自己的文件，不是考生回憶重建的；其餘三年只有答案本身。
# 兩者都不是學會的公開公告，但讀者有權知道差別在哪。
ANSWER_SOURCE = {
    104: "命題端檔案（每題附教科書出處、難易度與分類代碼），非學會公開公告",
    106: "命題端檔案（每題附教科書出處、難易度與分類代碼），非學會公開公告",
}
ANSWER_SOURCE_DEFAULT = "考卷檔案內附，無學會公開公告可核對"


def build(year):
    parsed = PARSERS[year]()
    questions = []
    problems = []
    for n in range(1, 101):
        if n not in parsed:
            problems.append(f"Q{n} 未抽到")
            continue
        stem, options, answer, meta = parsed[n]
        if len(options) < 4:
            problems.append(f"Q{n} 只抽到 {len(options)} 個選項")
        if not answer:
            problems.append(f"Q{n} 無答案")
        elif answer not in options:
            problems.append(f"Q{n} 答案 {answer} 無對應選項")

        q = {
            "id": n,
            "year": ROC[year],
            "western_year": year,
            "question": stem,
            "options": options,
            "answer": answer,
            "scoring": "exact",
            "answer_source": ANSWER_SOURCE.get(ROC[year], ANSWER_SOURCE_DEFAULT),
            "answer_tier": "examiner" if ROC[year] in ANSWER_SOURCE else "exam_file",
            "source": f"{ROC[year]}_written_Q{n}",
        }
        # 分類欄位在 104 年是完整名稱、106 年是代碼，統一成 taxonomy.json 的代碼
        raw = meta.pop("category", "")
        if raw:
            q["category_raw"] = raw
            codes = re.findall(r"(?<![A-Za-z0-9])([ABC]\d{1,2})(?!\d)", raw)
            if codes:
                q["category"] = codes[0]
                if len(codes) > 1:
                    q["category_secondary"] = codes[1:]
        q.update({k: v for k, v in meta.items() if v})
        questions.append(q)

    data = {
        "meta": {
            "year": ROC[year],
            "western_year": year,
            "role": "doctor",
            "subject": "written",
            "subject_name": "筆試",
            "total": len(questions),
            "source": "台灣麻醉醫學會歷年甄審筆試考卷（無官方答案卡公告）",
            "verified": False,
            "extracted_by": "tools/parse_legacy_years.py",
        },
        "questions": questions,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{ROC[year]}_legacy.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), "utf-8"
    )
    return len(questions), problems


def main():
    years = [int(a) for a in sys.argv[1:]] or sorted(PARSERS)
    for year in years:
        count, problems = build(year)
        print(f"{year}（民國 {ROC[year]}）：抽出 {count} 題，問題 {len(problems)} 項")
        for p in problems[:10]:
            print(f"    - {p}")
        if len(problems) > 10:
            print(f"    …另有 {len(problems) - 10} 項")


if __name__ == "__main__":
    main()
