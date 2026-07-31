#!/usr/bin/env python3
"""從官方口試檔案抽出情境、子題配分與參考答案。

這些是**命題委員自己的參考答案指引**——除了標準答案，還有給口試委員的追問提示
（「若考生堅持…請直接 challenge 考生…」）與加分選項。內容一律照抄原檔，
不重寫、不補充。

## 為什麼用事件流而不是純文字比對

108 年第二題的參考答案**主要是圖**（困難插管流程圖、Miller Fig 101-2），
純文字只有寥寥數行。所以解析要能把圖也歸給對應的子題，作法是逐頁把
「子題標題」「內文」「圖」依垂直位置排成一串事件再依序歸屬——與
`extract_images.py` 抽考題圖是同一套方法。

## 版面

只有 8 份檔案，但每年排版都不同，自動判斷會誤判（110 年明明沒有參考答案，
卻被切出兩則）。官方參考答案切錯位置比沒有更糟，所以逐檔明確指定：

  list    子題清單在前，參考答案在後，標題重複出現一次
  inline  每個子題標題後面直接接該題的參考答案
  answers 子題列完，最後用「解答:」帶出整段參考答案（不細分）
  none    只公布題目，沒有參考答案
"""
import json
import re
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source"
OUT = ROOT / "data" / "oral"
IMGDIR = ROOT / "images"

WEIGHT = re.compile(r"[（(]\s*(\d{1,3})\s*%\s*[）)]")
NUMBERED = re.compile(r"^\s*(?:子題\s*)?[一二三四五六七八九十\d]+\s*[.、)]\s*")
ANSWER_HEAD = re.compile(r"(?m)^\s*(?:參考)?解答\s*[:：]")
PAGE_REF = re.compile(r"[（(]\s*p+\.?\s*[\d,\s\-–]+[）)]", re.I)

# 原檔的圖常被切成多條橫帶（108 年第二題有一張圖被切成 9 條 271×50），
# 所以最小尺寸不能訂太大，且要把上下相鄰的帶子併回一張。
MIN_IMG = 24
MERGE_GAP = 14
DPI = 200

# 配分標記那一行本身若已經有文字，標題就到此為止，不再往回併——否則在參考答案區
# 會把上一題答案的最後一行誤當成標題。門檻要低，中文標題可以很短（「麻醉評估」）。
MIN_INLINE_TITLE = 3
# 真的需要往回時（標題換行，配分標記自成一行）最多併兩行，再多會把題幹的
# 病史清單（「3. Coronary artery disease…」）吃進來，那些也是帶編號的行。
MAX_TITLE_LINES = 4


def tidy(s):
    s = s.replace(" ", " ")
    s = re.sub(r"[ \t]*\n[ \t]*", "\n", s)
    # PDF 常把「1.」和內容拆成兩行，接回去才讀得像清單
    s = re.sub(r"(?m)^([一二三四五六七八九十\d]{1,3}\s*[.、)])\s*\n\s*", r"\1 ", s)
    s = re.sub(r"(?m)^([IVXivx]{1,4}\s*[.、)])\s*\n\s*", r"\1 ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


def merged_image_rects(page):
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
    return merged


def events(path):
    """整份檔案依閱讀順序排成事件串：('line', 文字) 或 ('img', (page, rect))。"""
    out = []
    for page in fitz.open(path):
        items = []
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                text = "".join(s["text"] for s in line["spans"]).rstrip()
                if text.strip():
                    items.append((line["bbox"][1], "line", text))
        for rect in merged_image_rects(page):
            items.append((rect.y0, "img", (page, rect)))
        out += [(k, v) for _, k, v in sorted(items, key=lambda x: x[0])]
    return out


def collect(path):
    """把事件串整理成 (前言, [子題])，子題以配分標記認定。

    標題可能跨行（112 年有「…需考慮那些可能原因?\\n(20%)」），
    所以碰到配分標記時，往回把尚未歸屬的文字行併進標題。
    """
    heads, pending, preamble = [], [], []

    def sink():
        return heads[-1]["body"] if heads else preamble

    for kind, value in events(path):
        if kind == "img":
            sink().append(("img", value))
            continue
        m = WEIGHT.search(value)
        if not m:
            pending.append(value)
            continue
        head_line = value[:m.start()].strip()
        # 只數實際文字，空白與標點不算——否則「量 ?」會被誤判成完整標題
        head_len = len(re.sub(r"[\s?？。，,.、!！:：]", "", NUMBERED.sub("", head_line)))
        parts = []
        if head_len < MIN_INLINE_TITLE:
            for ln in reversed(pending):
                if len(parts) >= MAX_TITLE_LINES:
                    break
                parts.insert(0, ln)
                if NUMBERED.match(ln):
                    break
        leftover = pending[:len(pending) - len(parts)]
        sink().extend(("text", x) for x in leftover)
        title = tidy(" ".join(parts + [value[:m.start()]]))
        title = PAGE_REF.sub("", NUMBERED.sub("", title)).strip()
        heads.append({"title": title, "weight": int(m.group(1)), "body": []})
        tail = value[m.end():].strip()
        if tail:
            heads[-1]["body"].append(("text", tail))
        pending = []

    sink().extend(("text", x) for x in pending)
    return preamble, heads


def key_of(title, n=16):
    return re.sub(r"\s+", "", title)[:n]


def body_to_parts(body, prefix, counter):
    """把內容事件拆成文字與圖檔名。"""
    text = tidy("\n".join(v for k, v in body if k == "text"))
    images = []
    IMGDIR.mkdir(parents=True, exist_ok=True)
    for k, v in body:
        if k != "img":
            continue
        page, rect = v
        counter[0] += 1
        name = f"{prefix}_{counter[0]}.png"
        clip = (rect + (-4, -4, 4, 4)) & page.rect
        page.get_pixmap(clip=clip, dpi=DPI).save(IMGDIR / name)
        images.append(name)
    return text, images


def trim_to_full_marks(subs):
    """配分加總到 100% 就停——超過表示抓進參考答案區裡重複的標題。"""
    total, out = 0, []
    for s in subs:
        if total >= 100:
            break
        out.append(s)
        total += s["weight"]
    return out


def build(rel, year, qid, title, prefix, layout):
    path = SRC / rel
    preamble, heads = collect(path)
    counter = [0]
    whole = ""

    if layout == "list":
        first, repeats, seen = [], [], set()
        for h in heads:
            k = key_of(h["title"])
            (repeats if k in seen else first).append(h)
            seen.add(k)
        by_key = {key_of(a["title"]): a for a in repeats}
        subs = []
        for i, s in enumerate(trim_to_full_marks(first)):
            a = by_key.get(key_of(s["title"]))
            text, images = body_to_parts(a["body"], f"{prefix}_a{i+1}", counter) if a else ("", [])
            subs.append({"title": s["title"], "weight": s["weight"],
                         "reference": text, "reference_images": images})

    elif layout == "inline":
        subs = []
        for i, h in enumerate(trim_to_full_marks(heads)):
            text, images = body_to_parts(h["body"], f"{prefix}_a{i+1}", counter)
            subs.append({"title": h["title"], "weight": h["weight"],
                         "reference": text, "reference_images": images})

    else:   # answers / none
        subs = [{"title": h["title"], "weight": h["weight"],
                 "reference": "", "reference_images": []}
                for h in trim_to_full_marks(heads)]
        if layout == "answers":
            raw = "".join(p.get_text() for p in fitz.open(path))
            m = ANSWER_HEAD.search(raw)
            whole = tidy(raw[m.end():]) if m else ""

    scenario, scenario_images = body_to_parts(preamble, f"{prefix}_s", counter)
    return {
        "id": qid,
        "year": year,
        "type": "oral",
        "title": title,
        "scenario": scenario,
        "scenario_images": scenario_images,
        "subquestions": subs,
        "reference_text": whole,
        "has_reference": bool(whole) or any(s["reference"] or s["reference_images"] for s in subs),
        "source_file": rel,
    }


ORAL = [
    (108, 1, "口試第一題", "oral/108_口試1_含參考答案.pdf", "list"),
    (108, 2, "口試第二題", "oral/108_口試2_含參考答案.pdf", "list"),
    (110, 1, "口試第一題", "oral/110_口試1.pdf", "none"),
    (110, 2, "口試第二題", "oral/110_口試2.pdf", "none"),
    (111, 1, "口試第一題", "oral/111_口試1.pdf", "answers"),
    (111, 2, "口試第二題", "oral/111_口試2.pdf", "answers"),
    (112, 1, "口試第一題", "oral/112_口試1.pdf", "inline"),
    (112, 2, "口試第二題", "oral/112_口試2.pdf", "inline"),
]


def main():
    by_year = {}
    for year, qid, title, rel, layout in ORAL:
        item = build(rel, year, qid, title, f"{year}_oral{qid}", layout)
        by_year.setdefault(year, []).append(item)
        w = sum(s["weight"] for s in item["subquestions"])
        nref = sum(1 for s in item["subquestions"] if s["reference"] or s["reference_images"])
        nimg = len(item["scenario_images"]) + sum(len(s["reference_images"]) for s in item["subquestions"])
        extra = "、另有整段解答" if item["reference_text"] else ""
        print(f"{year} 口試{qid}（{layout}）：子題 {len(item['subquestions'])}、配分 {w}%、"
              f"有參考答案 {nref}、圖 {nimg}{extra}")

    OUT.mkdir(parents=True, exist_ok=True)
    for year, items in by_year.items():
        (OUT / f"{year}_oral.json").write_text(json.dumps(
            {"meta": {"year": year, "type": "oral", "subject_name": "口試",
                      "source": "台灣麻醉醫學會口試試題與評分表"},
             "questions": items}, ensure_ascii=False, indent=1), "utf-8")


if __name__ == "__main__":
    sys.exit(main())
