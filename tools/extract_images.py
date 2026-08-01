#!/usr/bin/env python3
"""從官方考卷 PDF 抽出圖片題的圖，並把檔名寫回題庫。

各年度的排版不一致：有的把選項標號放在圖的上面（111 年），有的放在下面
（112、113 年），還有整題只有一張題幹圖的（109 年）。因此先把每一題的
「選項標號」與「圖」依閱讀順序排成一串，再看兩者數量是否相等來判斷排版方向：

  數量相等且圖在標號後 → 標號在上，圖是該選項的圖
  數量相等且圖在標號前 → 標號在下，圖是該選項的圖
  數量不等             → 圖是題幹的附圖

圖片以 300 dpi 從頁面裁切算繪，而不是抽原始嵌入物件，因為有些圖是由多個
物件併排組成的（例如 111 年 Q93 的 (C) 由兩張波形圖並排）。
"""
import json
import re
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source" / "official"
QDIR = ROOT / "data" / "questions"
IMGDIR = ROOT / "images"

# 舊考題是另一套版面（`QUESTION 22` 而不是 `22.`），檔案位置與命名也不同。
# 102–104、106 是同一套出題系統的版面，切法完全一樣，只是檔案位置不同。
_QNUM = re.compile(r"^QUESTION\s+(\d{1,3})\b")
_OPT = re.compile(r"^([A-E])[.、]")


def _legacy(year, pdf):
    return {
        "pdf": ROOT / "source" / "legacy_src" / pdf,
        "json": ROOT / "data" / "legacy_wip" / f"{year}_legacy.json",
        "qnum": _QNUM,
        "opt": _OPT,
    }


LEGACY = {
    106: _legacy(106, "2017/2017_written_ans.pdf"),
    104: _legacy(104, "2015/104年專甄考古題(筆試題目).pdf"),
    103: _legacy(103, "2014/2014_board_exam_answer.pdf"),
    102: _legacy(102, "2013/2013_筆試.pdf"),
}
OFFICIAL_QNUM = re.compile(r"^(\d{1,3})\.(?:\s|$)")
OFFICIAL_OPT = re.compile(r"^\(([A-E])\)")

DPI = 300
MIN_SIZE = 40   # 小於這個尺寸的多半是符號或線條，不是圖
PAD = 4         # 裁切時往外留一點邊


def page_events(page, expect, qnum=OFFICIAL_QNUM, opt=OFFICIAL_OPT):
    """把一頁上的題號、選項標號與圖片依閱讀順序排成事件串。

    題號只接受「剛好等於下一題」的那一個，否則會被選項內文的編號騙走
    （109 年 Q94 的選項就是「1. Posterior wall…2. Carina…」）。
    """
    events = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            text = "".join(s["text"] for s in line["spans"]).strip()
            if not text:
                continue
            y = line["bbox"][1]
            m = qnum.match(text)
            if m and int(m.group(1)) == expect[0]:
                events.append((y, "q", int(m.group(1))))
                expect[0] += 1
                continue
            m = opt.match(text)
            if m:
                events.append((y, "opt", m.group(1)))

    label_ys = [y for y, kind, _ in events if kind == "opt"]
    for rect in merged_image_rects(page, label_ys):
        events.append((rect.y0, "img", rect))

    return sorted(events, key=lambda e: e[0])


def merged_image_rects(page, label_ys=()):
    """把同一張圖被拆成的多個物件併起來。

    只有在兩塊之間**沒有夾著選項標號**時才合併——106 年 Q22 的四張 capnogram
    是上下堆疊、間距只有 4pt，但每張下面各有自己的 (A)(B)(C)(D)，不能併成一張。
    """
    rects = []
    for info in page.get_image_info():
        r = fitz.Rect(info["bbox"])
        if r.width >= MIN_SIZE and r.height >= MIN_SIZE:
            rects.append(r)

    def label_between(a, b):
        lo, hi = min(a.y1, b.y1), max(a.y0, b.y0)
        return any(lo - 2 <= y <= hi + 2 for y in label_ys)

    merged = []
    for r in sorted(rects, key=lambda r: (r.y0, r.x0)):
        for m in merged:
            if label_between(m, r):
                continue
            if m.intersects(r) or abs(m.y1 - r.y0) < 6:
                m |= r
                break
        else:
            merged.append(fitz.Rect(r))
    return merged


def collect(year):
    """走訪整份 PDF，回傳 {題號: [(page, rect) 或 ('opt', letter, page, rect)]}。"""
    cfg = LEGACY.get(year)
    doc = fitz.open(cfg["pdf"] if cfg else SRC / f"{year}_筆試_官方.pdf")
    qnum = cfg["qnum"] if cfg else OFFICIAL_QNUM
    opt = cfg["opt"] if cfg else OFFICIAL_OPT
    expect = [1]
    current = None
    per_question = {}

    for page in doc:
        for y, kind, value in page_events(page, expect, qnum, opt):
            if kind == "q":
                current = value
                per_question.setdefault(current, [])
            elif current is None:
                continue
            elif kind == "opt":
                per_question[current].append(("opt", value, None, None))
            else:
                per_question[current].append(("img", None, page, value))
    return doc, per_question


def assign(items):
    """判斷排版方向，回傳 {slot: (page, rect)}。slot 為 'stem' 或 'opt_X'。"""
    imgs = [it for it in items if it[0] == "img"]
    opts = [it for it in items if it[0] == "opt"]
    if not imgs:
        return {}

    if len(imgs) == len(opts) and opts:
        return {f"opt_{o[1]}": (i[2], i[3]) for o, i in zip(opts, imgs)}

    return {
        ("stem" if n == 0 else f"stem_{n + 1}"): (i[2], i[3])
        for n, i in enumerate(imgs)
    }


def render(year, qid, slot, page, rect):
    IMGDIR.mkdir(parents=True, exist_ok=True)
    name = f"{year}_Q{qid}_{slot}.png"
    clip = (fitz.Rect(rect) + (-PAD, -PAD, PAD, PAD)) & page.rect
    page.get_pixmap(clip=clip, dpi=DPI).save(IMGDIR / name)
    return name


def apply_to_questions(year, mapping):
    cfg = LEGACY.get(year)
    path = cfg["json"] if cfg else QDIR / f"{year}_written.json"
    data = json.loads(path.read_text("utf-8"))
    for q in data["questions"]:
        q.pop("images", None)
        q.pop("option_images", None)
        entry = mapping.get(q["id"])
        if not entry:
            continue
        stem = [v for k, v in sorted(entry.items()) if k.startswith("stem")]
        opts = {k[4:]: v for k, v in entry.items() if k.startswith("opt_")}
        if stem:
            q["images"] = stem
        if opts:
            q["option_images"] = dict(sorted(opts.items()))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")


def main():
    years = [int(a) for a in sys.argv[1:]] or [109, 110, 111, 112, 113]
    for year in years:
        doc, per_question = collect(year)
        mapping = {}
        for qid, items in sorted(per_question.items()):
            slots = assign(items)
            if not slots:
                continue
            mapping[qid] = {
                slot: render(year, qid, slot, page, rect)
                for slot, (page, rect) in slots.items()
            }
        apply_to_questions(year, mapping)
        total = sum(len(v) for v in mapping.values())
        print(f"{year}: {len(mapping)} 題有圖，共 {total} 張")
        for qid in sorted(mapping):
            print(f"    Q{qid}: {', '.join(sorted(mapping[qid]))}")


if __name__ == "__main__":
    main()
