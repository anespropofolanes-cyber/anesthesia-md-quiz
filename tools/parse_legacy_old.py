#!/usr/bin/env python3
"""抽出 2004–2012 年的舊考卷（民國 93–101 年）。

這批的年代比 `parse_legacy_years.py` 那幾年更早，答案來源也各不相同——
盤點結果見 `audit/legacy_inventory.md`。可用的有五年：

  2004  答案寫在題號前面：「(B)  1. 一位產婦…」，選項是 (A)/（A）混用
  2005  題目 `1、` ＋ 選項 `A.`，答案在 Word 註解「ans:C 出處：Anesthesia 5th…」
  2010  同上版面，註解寫「答案：E」
  2011  同上版面，答案在另一個檔案，形式是「1. E  2. E …」
**2012 年不收**：題目是 .doc，Word 自動編號在任何轉檔方式下都救不回來
（txt／html／docx 都試過）。HTML 的縮排只涵蓋前 11 題，第 12 題起的
「複合題」（題幹＋5 個敘述＋5 個組合選項）縮排與題幹相同，切不開。
而該年的答案是**靠位置對應題號**的，切分只要錯一題、後面全部的答案就都錯，
這種失敗模式比缺一年嚴重得多。要收的話，請先用 Word 把
`2012_筆試題目.doc` 另存成 .docx，編號就會保留在 XML 裡。

**這些年份的命題依據是 Anesthesia 第 5 版到 Miller 第 7 版**，
現行考試已經是第十版，臨床準則差很多。資料裡標 `era: "old"`，
網站上要與 108–114 年明確區隔。
"""
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source" / "legacy_src"
OUT = ROOT / "data" / "legacy_wip"
IMGDIR = ROOT / "images"

ANNOTATION = re.compile(r"註解\s*\[[^\]]*\]:[^\n]*")
# 答案在註解裡的寫法，同一份檔案都會混用：「ans:C」「答：D」「答案(C )」「答案：E」
ANN_ANSWER = re.compile(
    r"註解\s*\[[^\]]*\]:\s*[^\n]*?(?:ans|ane|答案|答)\s*(?:[:：]\s*|[（(]\s*)?([A-Ea-e])", re.I)
ANN_REFERENCE = re.compile(r"出處\s*[:：]?\s*([^\n]{0,60})")
# 選項標號後面不一定有空白：2011 年多題寫成「A.左心室功能不全」
OPT_LINE = r"(?m)^\s*([A-Ea-e])\s*[.、]\s*"


def tidy(s):
    s = s.replace(" ", " ")
    s = re.sub(r"[ \t]*\n[ \t]*", " ", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()


def pdf_text(path):
    """順便做 NFKC 正規化。

    2004 年有整段用全形英文字母寫選項（「（Ａ）」＝U+FF21，不是半形 A），
    2007 年的「參考答案」用相容區碼位。不正規化就整批比對不到。
    """
    raw = "".join(p.get_text() for p in fitz.open(path))
    return unicodedata.normalize("NFKC", raw)


def doc_text(path):
    out = subprocess.run(["textutil", "-convert", "txt", "-stdout", str(path)],
                         capture_output=True, timeout=60)
    return unicodedata.normalize("NFKC", out.stdout.decode("utf-8", "replace"))


def split_by(text, qnum_pattern, opt_pattern):
    """依序切出題目；題號必須遞增，且區塊要有 ≥3 個選項才算數。"""
    marks = list(re.finditer(qnum_pattern, text))
    by_num = {}
    for m in marks:
        by_num.setdefault(int(m.group(1)), []).append(m)

    out = {}
    for n in range(1, 101):
        # 不用游標往前推進——某一題抽失敗時，後面的題目仍然要抽得到
        for m in by_num.get(n, []):
            nxt = next((x.start() for x in by_num.get(n + 1, []) if x.start() > m.end()), len(text))
            block = text[m.end():nxt]
            opts = list(re.finditer(opt_pattern, block))
            if len({o.group(1).upper() for o in opts}) < 3:
                continue
            stem = tidy(block[:opts[0].start()])
            # 圖片題（2005 Q63）的版面是「A.（圖）B.（圖）題幹 A. 選項…」，
            # 取第一個選項標號之前當題幹會得到空字串。只有這種情況才改取
            # 「最後一組連續選項」之前的文字，正常題目不動。
            if not stem:
                letters = [o.group(1).upper() for o in opts]
                start = next((i for i in range(len(letters) - 1, 0, -1)
                              if letters[i] <= letters[i - 1]), 0)
                opts = opts[start:]
                stem = tidy(block[:opts[0].start()])
                stem = re.sub(r"^(?:[A-E]\s*[.、]\s*)+", "", stem).strip()
            options = {}
            for i, o in enumerate(opts):
                letter = o.group(1).upper()
                end = opts[i + 1].start() if i + 1 < len(opts) else len(block)
                # 變數不能叫 text——那會蓋掉函式參數，後面的題目就全部抽不到了
                opt_text = block[o.end():end]
                # 2005 年的「參考處：Anesthesia, 5th edition, p2415 難易度：」
                # 是給命題委員看的註記，會混進選項文字裡。
                # 不能用 re.S 的 .*?——那會跨行吃掉後面整段內容。
                opt_text = re.sub(r"參考處\s*[:：][^\n]*(?:\n[^\n]*難易度[^\n]*)?", " ", opt_text)
                opt_text = re.sub(r"難易度\s*[:：]\s*", " ", opt_text)
                options.setdefault(letter, tidy(opt_text))
            out[n] = (stem, options)
            break
    return out


def answers_from_annotations(raw):
    """註解在文字層裡是依題目順序出現的，第 n 條就是第 n 題的答案。"""
    answers = [m.group(1).upper() for m in ANN_ANSWER.finditer(raw)]
    refs = []
    for m in ANNOTATION.finditer(raw):
        r = ANN_REFERENCE.search(m.group(0))
        refs.append(tidy(r.group(1)) if r else "")
    return answers, refs


# 2004 年的選項有兩種寫法，同一份卷子裡混用：
#   「(A)密切觀察…」與「A. 70% B. 10% C. 120% D. 100%」（整行擠在一起）
OPT_2004 = re.compile(r"[（(]\s*([A-E])\s*[）)]|(?<![A-Za-z])([A-E])\s*[.、]\s")


def parse_2004():
    """答案寫在題號前面：「(B)  1. 一位產婦…」。"""
    raw = pdf_text(SRC / "2004" / "2004_筆試.pdf")
    marks = list(re.finditer(r"[（(]\s*([A-E])\s*[）)]\s*(\d{1,3})\s*[.、]\s*", raw))
    by_num = {}
    for m in marks:
        by_num.setdefault(int(m.group(2)), []).append(m)

    out = {}
    for n in range(1, 101):
        for m in by_num.get(n, []):
            nxt = next((x.start() for x in by_num.get(n + 1, []) if x.start() > m.end()), len(raw))
            block = raw[m.end():nxt]
            opts = list(OPT_2004.finditer(block))
            if len({(o.group(1) or o.group(2)) for o in opts}) < 3:
                continue
            stem = tidy(block[:opts[0].start()])
            options = {}
            for j, o in enumerate(opts):
                letter = (o.group(1) or o.group(2)).upper()
                stop = opts[j + 1].start() if j + 1 < len(opts) else len(block)
                options.setdefault(letter, tidy(block[o.end():stop]))
            out[n] = (stem, options, m.group(1), "")
            break
    return out


def extract_images(path, year):
    """2005 年有幾題是心電圖判讀，圖要抓出來，否則題目看不懂。"""
    doc = fitz.open(path)
    IMGDIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for pno, page in enumerate(doc):
        rects = [fitz.Rect(i["bbox"]) for i in page.get_image_info()]
        rects = [r for r in rects if r.width >= 60 and r.height >= 30]
        merged = []
        for r in sorted(rects, key=lambda r: (r.y0, r.x0)):
            for m in merged:
                if m.intersects(r) or abs(m.y1 - r.y0) < 10:
                    m |= r
                    break
            else:
                merged.append(fitz.Rect(r))
        # 圖屬於同一頁上、位置在它前面的最後一個題號
        nums = []
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                t = "".join(x["text"] for x in line["spans"]).strip()
                m = re.match(r"^(\d{1,3})\s*[、.]", t)
                if m and 1 <= int(m.group(1)) <= 100:
                    nums.append((line["bbox"][1], int(m.group(1))))
        for i, r in enumerate(merged):
            above = [n for y, n in sorted(nums) if y <= r.y0 + 2]
            if not above:
                continue
            name = f"{year}_Q{above[-1]}_fig{i + 1}.png"
            page.get_pixmap(clip=(r + (-4, -4, 4, 4)) & page.rect, dpi=200).save(IMGDIR / name)
            out.setdefault(above[-1], []).append(name)
    return out


def parse_annotated(rel, subdir):
    """2005／2010：題目與答案在同一個 PDF，答案在 Word 註解裡。"""
    raw = pdf_text(SRC / subdir / rel)
    body = ANNOTATION.sub("", raw)
    blocks = split_by(body, r"(?m)^\s*(\d{1,3})\s*[、.]", OPT_LINE)
    answers, refs = answers_from_annotations(raw)
    out = {}
    for i, n in enumerate(sorted(blocks)):
        stem, options = blocks[n]
        out[n] = (stem, options,
                  answers[i] if i < len(answers) else "",
                  refs[i] if i < len(refs) else "")
    return out


def parse_2011():
    """題目與答案分開兩個 PDF，答案是「1. E  2. E …」。"""
    body = pdf_text(SRC / "2011" / "2011_筆試考題.pdf")
    blocks = split_by(body, r"(?m)^\s*(\d{1,3})\s*[、.]", OPT_LINE)
    atext = pdf_text(SRC / "2011" / "2011_筆試答案.pdf")
    key = {int(n): a for n, a in re.findall(r"(\d{1,3})\s*[.、]\s*([A-E])\b", atext)}
    return {n: (blocks[n][0], blocks[n][1], key.get(n, ""), "") for n in blocks}


def doc_html_paragraphs(path):
    """把 .doc 轉成 HTML，取回每段的「左縮排」。

    2012 年的題號與選項標號是 Word 自動編號，轉純文字時整個丟失，
    純靠段落順序切分會錯位（試過「每 6 段一題」，切出來的題幹其實是選項）。
    但 HTML 保留了縮排：**題幹的 margin-left 是 0，選項縮排 42.5px**，
    這才是可靠的切分依據。
    """
    out = subprocess.run(["textutil", "-convert", "html", "-stdout", str(path)],
                         capture_output=True, timeout=60)
    html = out.stdout.decode("utf-8", "replace")
    styles = {}
    for name, body in re.findall(r"p\.(p\d+)\s*\{([^}]*)\}", html):
        # CSS 的 margin 簡寫是「上 右 下 左」，要的是第四個值（左邊距）
        m = re.search(r"margin:\s*([-\d.]+)px\s+([-\d.]+)px\s+([-\d.]+)px\s+([-\d.]+)px", body)
        left = float(m.group(4)) if m else 0.0
        m2 = re.search(r"margin-left:\s*([-\d.]+)px", body)
        if m2:
            left = float(m2.group(1))
        styles[name] = left

    paras = []
    for cls, raw in re.findall(r'<p class="(p\d+)"[^>]*>(.*?)</p>', html, re.S):
        text = unicodedata.normalize("NFKC", re.sub(r"<[^>]+>", "", raw)).strip()
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        if text:
            paras.append((styles.get(cls, 0.0), text))
    return paras


def parse_2012():
    """題目 .doc（靠縮排切分）＋ 答案 .doc（依序排列，每題附 Miller 7th 頁碼）。"""
    atext = doc_text(SRC / "2012" / "2012_筆試答案.doc")
    answers = re.findall(r"(?m)^\s*答案\s*[:：]\s*([A-E])", atext)
    refs = [tidy(r) for r in re.findall(
        r"(?m)^\s*答案\s*[:：]\s*[A-E]\s*(?:出處\s*[:：]\s*)?([^\n]*)", atext)]

    paras = doc_html_paragraphs(SRC / "2012" / "2012_筆試題目.doc")
    groups, current = [], None
    for indent, text in paras:
        if indent < 10:                      # 沒縮排＝題幹（或題幹的續行）
            if current and current["options"]:
                groups.append(current)
                current = None
            if current is None:
                current = {"stem": [text], "options": []}
            else:
                current["stem"].append(text)
        elif current is not None:
            current["options"].append(text)
    if current and current["options"]:
        groups.append(current)

    # 第一組是卷首標題，沒有選項，前面已經被濾掉
    out = {}
    for i, g in enumerate(groups[:len(answers)]):
        opts = g["options"][:5]
        out[i + 1] = (tidy(" ".join(g["stem"])),
                      {L: tidy(o) for L, o in zip("ABCDE", opts)},
                      answers[i],
                      refs[i] if i < len(refs) else "")
    return out


PARSERS = {
    2004: parse_2004,
    2005: lambda: parse_annotated("2005_筆試.pdf", "2005"),
    2010: lambda: parse_annotated("2010_筆試.pdf", "2010"),
    2011: parse_2011,
    # 2012 見檔頭說明，暫不收
}

ROC = {2004: 93, 2005: 94, 2010: 99, 2011: 100}
EDITION = {2004: "", 2005: "Anesthesia 第 5 版", 2010: "Miller 第 7 版", 2011: ""}


IMAGE_YEARS = {2005: ("2005/2005_筆試.pdf", 94)}


def build(year):
    parsed = PARSERS[year]()
    figures = {}
    if year in IMAGE_YEARS:
        rel, roc = IMAGE_YEARS[year]
        figures = extract_images(SRC / rel, roc)
    questions, problems = [], []
    for n in range(1, 101):
        if n not in parsed:
            problems.append(f"Q{n} 未抽到")
            continue
        stem, options, answer, ref = parsed[n]
        if len(options) < 4:
            problems.append(f"Q{n} 只抽到 {len(options)} 個選項")
        if not answer:
            problems.append(f"Q{n} 無答案")
        elif answer not in options:
            problems.append(f"Q{n} 答案 {answer} 無對應選項")

        # 原檔本來就缺的東西要標出來，不能讓它變成「答錯」
        incomplete = []
        if not answer:
            incomplete.append("原檔沒有這一題的答案")
        if len(options) < 4:
            incomplete.append(f"原檔只抽到 {len(options)} 個選項")
        if answer and answer not in options:
            incomplete.append(f"答案 {answer} 在選項裡找不到")

        q = {
            "id": n,
            "year": ROC[year],
            "western_year": year,
            "era": "old",
            "question": stem,
            "options": options,
            "answer": answer,
            "scoring": "exact",
            "answer_source": "答案隨學會發出的考卷檔案一併附上，但學會網站沒有對應的公開公告可交叉核對",
            "answer_tier": "exam_file",
            "source": f"{ROC[year]}_written_Q{n}",
        }
        if ref:
            q["reference"] = ref
        if EDITION[year]:
            q["textbook_era"] = EDITION[year]
        if n in figures:
            q["images"] = figures[n]
        if incomplete:
            q["incomplete"] = incomplete
            q["scoring"] = "unscored"      # 不判分，只當閱讀資料
        questions.append(q)

    data = {
        "meta": {
            "year": ROC[year],
            "western_year": year,
            "role": "doctor",
            "subject": "written",
            "subject_name": "筆試",
            "total": len(questions),
            "era": "old",
            "textbook_era": EDITION[year],
            "source": "台灣麻醉醫學會歷年甄審筆試考卷（無官方答案卡公告）",
            "verified": False,
            "extracted_by": "tools/parse_legacy_old.py",
        },
        "questions": questions,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{ROC[year]}_legacy.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    return len(questions), problems


def main():
    years = [int(a) for a in sys.argv[1:]] or sorted(PARSERS)
    for year in years:
        count, problems = build(year)
        print(f"{year}（民國 {ROC[year]}）：抽出 {count} 題，問題 {len(problems)} 項")
        for p in problems[:8]:
            print(f"    - {p}")
        if len(problems) > 8:
            print(f"    …另有 {len(problems) - 8} 項")


if __name__ == "__main__":
    sys.exit(main())
