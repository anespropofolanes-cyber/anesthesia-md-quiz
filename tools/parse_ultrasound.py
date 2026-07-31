#!/usr/bin/env python3
"""抽出 108 年超音波實作測驗（OSCE 形式）。

三站的檔案結構一致，都是三段：

    台灣麻醉醫學會108 年…超音波試題        ← 情境與任務清單
      情境1：50 歲男性接受右肝切除手術…
      任務：穿刺前以超音波評估右側頸靜脈 IJV
      1. 選擇合適超音波探頭  2. 病人頭頸擺位…

    台灣麻醉醫學會108 年…超音波評分表      ← 評分表（總評與五級分標準）
      五級分評分：極優＝8 項全有、優＝7 項…

    項目 / 參考答案                        ← 逐項評分標準，這就是官方參考答案
      1. 選擇 linear 超音波探頭
      2. 病人頭頸擺位 supine with head turned for exposure…

與口試不同，這裡不硬把「任務」和「評分標準」逐條對齊——第一站有兩個情境、
任務各自從 1 編號，評分表卻是 1–8 連續編號，硬對會錯位。三段各自完整保留，
讓讀者自己對照，這樣不會失真。
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source" / "ultrasound"
OUT = ROOT / "data" / "oral"
IMGDIR = ROOT / "images"

# 108 年第二題的「參考答案」用的是相容區碼位（參＝U+F96B 而非 U+53C3），
# 直接比對會找不到，所以整份先做 NFKC 正規化。
SHEET_HEAD = re.compile(r"台灣麻醉醫學會.{0,20}超音波評分表")
GRADE_HEAD = re.compile(r"五級分評分")
ITEM_HEAD = re.compile(r"(?m)^\s*(?:項目|參考答案)\s*[:：]?\s*$")

MIN_IMG = 24
MERGE_GAP = 14
DPI = 200


def normalize(s):
    return unicodedata.normalize("NFKC", s)


def tidy(s):
    s = s.replace(" ", " ")
    s = re.sub(r"[ \t]*\n[ \t]*", "\n", s)
    # PDF 常把「1.」和內容拆成兩行，接回去才讀得像清單
    s = re.sub(r"(?m)^([一二三四五六七八九十\d]{1,3}\s*[.、)])\s*\n\s*", r"\1 ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


def extract_images(path, prefix):
    names = []
    IMGDIR.mkdir(parents=True, exist_ok=True)
    for pno, page in enumerate(fitz.open(path)):
        rects = [fitz.Rect(i["bbox"]) for i in page.get_image_info()]
        rects = [r for r in rects if r.width >= MIN_IMG and r.height >= MIN_IMG]
        merged = []
        for r in sorted(rects, key=lambda r: (r.y0, r.x0)):
            for m in merged:
                if m.intersects(r) or abs(m.y1 - r.y0) < MERGE_GAP:
                    m |= r
                    break
            else:
                merged.append(fitz.Rect(r))
        for i, r in enumerate(merged):
            name = f"{prefix}_p{pno + 1}_{i + 1}.png"
            page.get_pixmap(clip=(r + (-4, -4, 4, 4)) & page.rect, dpi=DPI).save(IMGDIR / name)
            names.append(name)
    return names


def split_sections(text):
    """切成 (題目, 評分標準, 逐項參考答案)。"""
    m_sheet = SHEET_HEAD.search(text)
    task = text[:m_sheet.start()] if m_sheet else text
    rest = text[m_sheet.end():] if m_sheet else ""

    m_item = ITEM_HEAD.search(rest)
    if m_item:
        grading, items = rest[:m_item.start()], rest[m_item.end():]
    else:
        # 有些站的逐項標準直接接在五級分表格後面
        m_grade = GRADE_HEAD.search(rest)
        grading, items = (rest[:m_grade.start()], rest[m_grade.start():]) if m_grade else (rest, "")
    return tidy(task), tidy(grading), tidy(items)


STATIONS = [
    (1, "第一題　血管超音波", "108_超音波1_血管.pdf"),
    (2, "第二題　經食道心臟超音波", "108_超音波2_TEE.pdf"),
    (3, "第三題　周邊神經超音波", "108_超音波3_周邊神經.pdf"),
]


def main():
    out = []
    for sid, title, rel in STATIONS:
        path = SRC / rel
        text = normalize("".join(p.get_text() for p in fitz.open(path)))
        task, grading, items = split_sections(text)
        images = extract_images(path, f"108_us{sid}")
        out.append({
            "id": sid,
            "year": 108,
            "type": "ultrasound",
            "title": title,
            "task": task,
            "grading": grading,
            "criteria": items,
            "images": images,
            "has_reference": bool(items),
            "source_file": f"ultrasound/{rel}",
        })
        print(f"108 超音波{sid}：題目 {len(task)} 字、評分標準 {len(grading)} 字、"
              f"逐項參考答案 {len(items)} 字、圖 {len(images)}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "108_ultrasound.json").write_text(json.dumps(
        {"meta": {"year": 108, "type": "ultrasound", "subject_name": "超音波實作",
                  "source": "台灣麻醉醫學會 108 年超音波試題評分表與參考答案"},
         "questions": out}, ensure_ascii=False, indent=1), "utf-8")


if __name__ == "__main__":
    sys.exit(main())
