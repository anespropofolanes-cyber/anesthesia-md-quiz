#!/usr/bin/env python3
"""從台灣麻醉醫學會公告的官方考卷抽出題目，輸出 data/questions/<year>_written.json。

題幹與選項一律以官方原卷為準，答案取自 source/answer_keys/answer_key_<year>.json
（由官方公告的答案卡建立）。本腳本不產生解析。
"""
import html
import json
import re
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source"
OUT = ROOT / "data" / "questions"

YEARS = [108, 109, 110, 111, 112, 113, 114]
OPTION_LETTERS = "ABCDE"

# 頁首／頁尾等非題目文字
NOISE = re.compile(
    r"^\s*(?:第\s*\d+\s*頁|共\s*\d+\s*頁|"
    r"台灣麻醉醫學會.*|1\d{2}\s*年.*甄審.*|.*作答時間.*|.*請以2B鉛筆.*)\s*$"
)
# 純數字行只有出現在頁首／頁尾才是頁碼——108 年 Q77 的選項就是 58/55/43/48/70
PAGE_NO = re.compile(r"^\s*\d{1,3}\s*$")
EDGE_LINES = 2
# 卷末的答案對照表（108 年印在同一份 PDF 裡），題目抽到這裡就該停
ANSWER_TABLE = re.compile(r"答案列印|答案\s*表|標準答案")


def pdf_text(path):
    """逐頁取文字，順便把該頁的頁首頁尾雜訊去掉。

    整頁重複的頁面直接跳過：110 年官方 PDF 的第 2、3 頁內容一模一樣，
    Q5 的區塊會一路吃到重複頁的頁首與第 1 題題幹，選項 D 尾巴多出一整串雜訊。
    """
    pages = []
    seen = set()
    for page in fitz.open(path):
        digest = re.sub(r"\s+", "", page.get_text())
        if digest and digest in seen:
            continue
        seen.add(digest)
        lines = [ln.replace("\u00a0", " ").rstrip() for ln in page.get_text().splitlines()]
        keep = []
        idx = [i for i, ln in enumerate(lines) if ln.strip()]
        edge = set(idx[:EDGE_LINES] + idx[-EDGE_LINES:]) if idx else set()
        for i, ln in enumerate(lines):
            if NOISE.match(ln):
                continue
            if PAGE_NO.match(ln) and i in edge:
                continue
            keep.append(ln)
        pages.append("\n".join(keep))
    return "\n".join(pages)


def docx_paragraphs(path):
    """114 年官方檔為 docx，題號與選項標記都是 Word 自動編號，文字層看不到。

    回傳 (是否為題幹, 文字)。題幹是清單 numId=1 的第 0 層（恰好 100 段），
    其餘段落都算前一題的選項——原卷有幾題的選項被 Word 拆到別的清單編號去了。
    """
    import zipfile

    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")

    out = []
    for para in re.split(r"</w:p>", xml):
        text = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", para))
        # XML 實體要還原，否則 ">" 會留成 "&gt;"（114 年有 6 處）
        text = html.unescape(text).replace("\u00a0", " ").strip()
        if not text:
            continue
        num_id = re.search(r'<w:numId w:val="(\d+)"', para)
        ilvl = re.search(r'<w:ilvl w:val="(\d+)"', para)
        is_stem = bool(num_id and num_id.group(1) == "1" and ilvl and ilvl.group(1) == "0")
        out.append((is_stem, text))
    return out


def clean(text):
    lines = []
    for line in text.splitlines():
        line = line.replace(" ", " ").rstrip()
        if NOISE.match(line):
            continue
        lines.append(line)
    return "\n".join(lines)


def split_questions(text):
    """切出 1.–100. 的題目區塊。

    題號必須依序遞增，且區塊內要有 (A)(B) 兩個以上選項才算數——否則會誤抓
    試場注意事項的編號清單（113 年），或選項內文的「1. …2. …」編號（109 年圖片題）。
    """
    marks = list(re.finditer(r"(?m)^\s*(\d{1,3})\.\s", text))
    by_num = {}
    for m in marks:
        by_num.setdefault(int(m.group(1)), []).append(m)

    blocks = {}
    cursor = 0
    for n in range(1, 101):
        for m in by_num.get(n, []):
            if m.start() < cursor:
                continue
            nxt = next(
                (x.start() for x in by_num.get(n + 1, []) if x.start() > m.end()),
                len(text),
            )
            block = text[m.end():nxt]
            if "(A)" in block and "(B)" in block:
                blocks[n] = block
                cursor = m.end()
                break
    return blocks


def split_options(block):
    """把題目區塊拆成題幹與選項 dict。

    選項標號**必須在行首**。原本沒有這個限制，只要文字裡出現 (A)–(E) 就當成
    新選項的起點，於是選項內文引用其他選項時會被就地切斷：
    113 Q13 的四個選項「Panel (A) 代表 Synergic」全被截成「Panel」，
    113 Q65 的「承(A)，若病童…」只剩一個「承」字，108 Q93 的 (D) 同理。
    """
    marks = list(re.finditer(r"(?m)^[ \t　]*\(([A-E])\)", block))
    if not marks:
        return tidy(block), {}
    stem = tidy(block[: marks[0].start()])
    options = {}
    for i, m in enumerate(marks):
        letter = m.group(1)
        end = marks[i + 1].start() if i + 1 < len(marks) else len(block)
        if letter in options:  # 選項字母重複出現時以第一次為準
            continue
        options[letter] = tidy(block[m.end():end])
    return stem, options


def tidy(s):
    """PDF 抽出的文字常有換行造成的空隙，壓成單行但保留中英文之間的空格。"""
    s = re.sub(r"[ \t]*\n[ \t]*", " ", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip(" 　")


def parse_pdf_year(year):
    text = clean(pdf_text(SRC / "official" / f"{year}_筆試_官方.pdf"))
    # 108 年的答案表就印在同一份 PDF 的末頁。最後一題的區塊沒有下一個題號可停，
    # 會一路吃到文件結尾——Q100 的選項 E 因此串進整份答案表，等於把答案印在題目裡。
    cut = ANSWER_TABLE.search(text)
    if cut:
        text = text[: cut.start()]
    return split_questions(text)


def parse_docx_year(year):
    """114 年：題幹是清單第 0 層，兩個題幹之間的段落依序就是 (A)(B)(C)(D)。"""
    blocks = {}
    qno = 0
    current = None
    for is_stem, text in docx_paragraphs(SRC / "official" / f"{year}_筆試_官方.docx"):
        if is_stem:
            qno += 1
            if qno > 100:
                break
            current = {"stem": text, "options": {}}
            blocks[qno] = current
        elif current is not None:
            # 原卷少數選項自己帶了 (C) 之類的標記，去掉以免重複
            text = re.sub(r"^\(([A-E])\)\s*", "", text)
            idx = len(current["options"])
            if idx < len(OPTION_LETTERS):
                current["options"][OPTION_LETTERS[idx]] = text
    return blocks


def load_key(year):
    raw = json.loads((SRC / "answer_keys" / f"answer_key_{year}.json").read_text("utf-8"))
    return {int(k): v for k, v in raw.items()}


def build(year):
    key = load_key(year)
    questions = []
    problems = []

    if year == 114:
        blocks = parse_docx_year(year)
        get = lambda n: (blocks[n]["stem"], blocks[n]["options"]) if n in blocks else (None, None)
    else:
        raw = parse_pdf_year(year)
        get = lambda n: split_options(raw[n]) if n in raw else (None, None)

    for n in range(1, 101):
        stem, options = get(n)
        if stem is None:
            problems.append(f"Q{n} 未抽到題目")
            continue
        answer = key.get(n, "")
        if not options:
            problems.append(f"Q{n} 未抽到選項")
        elif answer != "送分":
            missing = [c for c in answer if c not in options]
            if missing:
                problems.append(f"Q{n} 答案 {answer} 有選項未抽到：{missing}")
        questions.append(
            {
                "id": n,
                "year": year,
                "question": stem,
                "options": options,
                "answer": answer,
                "scoring": (
                    "free" if answer == "送分" else "any" if len(answer) > 1 else "exact"
                ),
                "source": f"{year}_written_Q{n}",
            }
        )

    data = {
        "meta": {
            "year": year,
            "role": "doctor",
            "subject": "written",
            "subject_name": "筆試",
            "total": len(questions),
            "source": "台灣麻醉醫學會公告之官方試題與答案",
            "extracted_by": "tools/parse_official.py",
        },
        "questions": questions,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{year}_written.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), "utf-8"
    )
    return len(questions), problems


def main():
    years = [int(a) for a in sys.argv[1:]] or YEARS
    total_problems = 0
    for year in years:
        count, problems = build(year)
        total_problems += len(problems)
        print(f"{year}: 抽出 {count} 題，問題 {len(problems)} 項")
        for p in problems[:12]:
            print(f"    - {p}")
        if len(problems) > 12:
            print(f"    …另有 {len(problems) - 12} 項")
    return 1 if total_problems else 0


if __name__ == "__main__":
    sys.exit(main())
