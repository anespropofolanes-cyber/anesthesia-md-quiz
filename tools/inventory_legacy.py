#!/usr/bin/env python3
"""盤點 2003–2012 年舊考卷的答案來源。

決定「哪幾年可以收進題庫」之前，得先知道每一年的答案**是不是真的存在、
存在哪裡**。這支只讀不寫，輸出報告到 audit/legacy_inventory.md。

答案可能藏在四種地方：

  獨立答案檔   2011、2012 年有 `*_筆試答案.*`
  題號前綴     2004 年是「(B)  1. 一位產婦…」
  Word 註解    2005、2006 年是「註解 [S91]: MM.Ans: C 出處：Anesthesia 5th…」
  逐題標註     2013 年之後那套出題系統的「Correct Answer: B」

`.doc` 是 Word 97 二進位格式，PyMuPDF 讀不了，用 macOS 內建的 textutil 轉純文字。
"""
import re
import subprocess
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source" / "legacy_src"
REPORT = ROOT / "audit" / "legacy_inventory.md"

YEARS = range(2003, 2013)

# 題號寫法各年不同：「1.」「1、」「(B) 1.」，且不一定有空白
QNUM = re.compile(r"(?m)^\s*(?:[（(][A-E][）)]\s*)?(\d{1,3})\s*[.、]")
# 2006/2008/2009/2012 的題號與選項是 Word 自動編號，textutil 轉檔時整個丟掉，
# 純文字裡完全看不到編號。這幾年只能靠「答案的順序」對應題號。
ORDERED_ANS = re.compile(r"(?m)^\s*答案\s*[:：]\s*([A-E])")
PREFIX_ANS = re.compile(r"[（(]\s*([A-E])\s*[）)]\s*\d{1,3}\s*[.、]")
CORRECT = re.compile(r"Correct\s*Answer\s*[:：]\s*([A-E])", re.I)
# 答案的寫法各年不同，連同一份檔案裡都會混用：
#   2005「ans:C」／2007「答：D」與「答案(C )」／2010「答案：E」
COMMENT_ANS = re.compile(
    r"註解\s*\[[^\]]*\]:\s*[^\n]*?(?:ans|ane|答案|答)\s*"
    r"(?:[:：]\s*|[（(]\s*)?([A-Ea-e])", re.I)
ANSWER_LIST = re.compile(r"(\d{1,3})\s*[.、]\s*([A-E])\b")
MILLER_ED = re.compile(r"(?:Miller|Anesthesia)[^\n]{0,20}?(\d)\s*(?:th|rd|nd|st)?\s*(?:ed|edition)", re.I)


def read_text(path):
    """PDF 用 PyMuPDF；.doc 是 Word 97 二進位格式，用 macOS 內建 textutil 轉。"""
    if path.suffix.lower() == ".pdf":
        return "".join(p.get_text() for p in fitz.open(path))
    if path.suffix.lower() in (".doc", ".docx", ".rtf"):
        try:
            out = subprocess.run(
                ["textutil", "-convert", "txt", "-stdout", str(path)],
                capture_output=True, timeout=60)
            return out.stdout.decode("utf-8", "replace")
        except Exception as e:
            return f"__READ_ERROR__ {e}"
    return ""


def analyse(text):
    """回答：題目有幾題、答案用哪種形式、有幾題找得到答案。"""
    qnums = {int(m.group(1)) for m in QNUM.finditer(text) if 1 <= int(m.group(1)) <= 120}
    kinds = {
        "題號前綴": {int(m.group(0).split(")")[-1].strip(" .、")) for m in PREFIX_ANS.finditer(text)
                     if m.group(0).split(")")[-1].strip(" .、").isdigit()},
        "Correct Answer": set(range(len(CORRECT.findall(text)))),
        "Word 註解": set(range(len(COMMENT_ANS.findall(text)))),
    }
    counts = {k: len(v) for k, v in kinds.items() if v}
    return len(qnums), counts


def answer_list_count(text):
    """獨立答案檔有兩種寫法。

    2011 年是「1. E  2. E …」帶題號；
    2012 年是「答案: D 出處:Miller7, P.622-626」不帶題號，靠出現順序對應題號。
    """
    pairs = {int(n): a for n, a in ANSWER_LIST.findall(text) if 1 <= int(n) <= 120}
    ordered = ORDERED_ANS.findall(text)
    return max(len(pairs), len(ordered))


def source_edition(text):
    """答案檔常註明出處的教科書版本，這決定了題目過不過時。"""
    m = re.search(r"Miller\s*(\d)", text)
    return f"Miller {m.group(1)}th" if m else None


def main():
    lines = ["# 2003–2012 舊考卷答案來源盤點", "",
             "由 `tools/inventory_legacy.py` 產生，只讀不寫。", "",
             "| 年 | 筆試檔 | 題數 | 答案來源 | 可判分題數 | 教科書版本 |",
             "|---|---|---|---|---|---|"]
    summary = []

    for year in YEARS:
        d = SRC / str(year)
        if not d.exists():
            continue
        written = [p for p in sorted(d.iterdir())
                   if "筆試" in p.name and "答案" not in p.name]
        answers = [p for p in sorted(d.iterdir()) if "筆試答案" in p.name]

        for wp in written:
            text = read_text(wp)
            if text.startswith("__READ_ERROR__"):
                lines.append(f"| {year} | {wp.name} | — | **讀取失敗** | — | — |")
                summary.append((year, wp.name, 0, "讀取失敗", 0))
                continue

            nq, kinds = analyse(text)
            edition = source_edition(text) or "—"

            scorable, source = 0, "**無**"
            if answers:
                atext = read_text(answers[0])
                scorable = answer_list_count(atext)
                source = f"獨立答案檔 `{answers[0].name}`"
                edition = source_edition(atext) or edition
            elif kinds:
                source, scorable = max(kinds.items(), key=lambda kv: kv[1])
                scorable = kinds[source]
                source = f"{source}（同一檔內）"

            lines.append(f"| {year} | {wp.name} | {nq} | {source} | {scorable} | {edition} |")
            summary.append((year, wp.name, nq, source, scorable))

    lines += ["", "> 題數為 0 或極少的年份，是因為題號與選項標號是 Word 自動編號，",
              "> `textutil` 轉純文字時整個丟失（轉 docx／html 也一樣救不回來）。",
              "> 這幾年若要收，得靠答案的順序對應題號，或改用 Word／LibreOffice 另存。",
              "", "## 判讀", ""]
    usable = [s for s in summary if s[4] >= 80]
    partial = [s for s in summary if 0 < s[4] < 80]
    none = [s for s in summary if s[4] == 0]
    lines.append(f"- **可用（答案涵蓋 ≥80 題）**：{'、'.join(str(s[0]) for s in usable) or '無'}")
    lines.append(f"- **部分**：{'、'.join(f'{s[0]}（{s[4]} 題）' for s in partial) or '無'}")
    lines.append(f"- **無答案**：{'、'.join(str(s[0]) for s in none) or '無'}")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", "utf-8")
    print("\n".join(lines))
    print(f"\n報告：{REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
