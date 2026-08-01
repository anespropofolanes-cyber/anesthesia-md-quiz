#!/usr/bin/env python3
"""補抽「題幹提到圖卻沒有圖」的舊考題。

驗證器會列出這種題目，但成因不只一種，通用抽圖器都漏掉了：

- **94 Q19**：圖畫在題號**上方**（題幹就寫「上圖」）。`parse_legacy_old.py`
  只把圖歸給「位置在它前面的題號」，這張圖前面沒有題號，整張被丟掉。
- **93 Q12**：圖是**向量繪製**的，`get_image_info()` 一張都抓不到，
  只能從 `get_drawings()` 的線段範圍反推圖的位置。

兩種都靠版面座標定位：找到該題題號的 y 座標，取它上方（或下方）最近的圖形區域。
抽完直接寫回題庫的 `images` 欄位，其餘欄位不動。

用法：python3 tools/fix_missing_figures.py [--dry-run]
"""
import json
import re
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'source' / 'legacy_src'
IMGDIR = ROOT / 'images'
DPI = 200
PAD = 6

# 年 -> (PDF 相對路徑, 題號, 圖在題號的哪一側)
JOBS = [
    (94, '2005/2005_筆試.pdf', 19, 'above'),
    (93, '2004/2004_筆試.pdf', 12, 'below'),
]
QNUM = re.compile(r'^\s*(\d{1,3})\s*[、.]')


def question_y(page, qid):
    """回傳該頁上這一題題號的 y 座標，找不到回 None。"""
    for block in page.get_text('dict')['blocks']:
        if block.get('type') != 0:
            continue
        for line in block['lines']:
            text = ''.join(s['text'] for s in line['spans']).strip()
            # 2004 年的題號前面還有答案前綴「(D) 12.」
            text = re.sub(r'^\([A-E]\s*\)\s*', '', text)
            m = QNUM.match(text)
            if m and int(m.group(1)) == qid:
                return line['bbox'][1]
    return None


def figure_rects(page):
    """該頁上的圖形區域：嵌入圖優先，沒有就用向量線段的範圍。"""
    rects = [fitz.Rect(i['bbox']) for i in page.get_image_info()]
    rects = [r for r in rects if r.width >= 60 and r.height >= 30]
    if not rects:
        drawings = [fitz.Rect(d['rect']) for d in page.get_drawings()]
        drawings = [r for r in drawings if r.width >= 20 and r.height >= 10]
        if drawings:
            whole = drawings[0]
            for r in drawings[1:]:
                whole |= r
            rects = [whole]

    # 上下相鄰的圖塊要併成一張：94 Q19 的四個 pressure-volume loop 就是分成
    # 上下兩塊。合併必須寫回串列——`m |= r` 只會重新綁定迴圈變數，串列不會變。
    merged = []
    for r in sorted(rects, key=lambda r: (r.y0, r.x0)):
        for i, m in enumerate(merged):
            if m.intersects(r) or abs(m.y1 - r.y0) < 12:
                merged[i] = m | r
                break
        else:
            merged.append(fitz.Rect(r))
    return merged


def run(year, rel, qid, side, dry):
    doc = fitz.open(SRC / rel)
    for page in doc:
        y = question_y(page, qid)
        if y is None:
            continue
        rects = figure_rects(page)
        if side == 'above':
            cands = [r for r in rects if r.y1 <= y + 2]
            pick = cands[-1] if cands else None
        else:
            cands = [r for r in rects if r.y0 >= y - 2]
            pick = cands[0] if cands else None
        if pick is None:
            print(f'{year} Q{qid}: 該頁找不到{"上" if side == "above" else "下"}方的圖')
            return None
        name = f'{year}_Q{qid}_stem.png'
        print(f'{year} Q{qid}: 頁 {page.number + 1}，{pick} → {name}')
        if not dry:
            IMGDIR.mkdir(exist_ok=True)
            clip = (pick + (-PAD, -PAD, PAD, PAD)) & page.rect
            page.get_pixmap(clip=clip, dpi=DPI).save(IMGDIR / name)
        return name
    print(f'{year} Q{qid}: 找不到題號')
    return None


def main() -> int:
    dry = '--dry-run' in sys.argv
    for year, rel, qid, side in JOBS:
        name = run(year, rel, qid, side, dry)
        if name is None or dry:
            continue
        path = ROOT / 'data' / 'legacy_wip' / f'{year}_legacy.json'
        paper = json.loads(path.read_text(encoding='utf-8'))
        for q in paper['questions']:
            if q['id'] == qid:
                q['images'] = sorted(set(q.get('images', []) + [name]))
        path.write_text(json.dumps(paper, ensure_ascii=False, indent=1) + '\n',
                        encoding='utf-8')
        print(f'   已寫回 {path.name}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
