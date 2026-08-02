#!/usr/bin/env python3
"""從 94 年考卷 PDF 的灰底標示重建答案。

94 年（2005）原卷的正確選項**本身帶灰底**，命題端的註解再用引線指向它。
先前只讀了文字層的「註解 [S55]: C.Ans: D」，而註解編號是 Word 的全域流水號、
與題號不是一對一，導致答案整批錯位（詳見 audit/94_answer_investigation.md）。

灰底是版面上的實體，直接對應到選項，不必經過編號——這是可靠得多的來源。

做法：
1. 取頁面上的填色矩形（灰底），排除整頁背景與過大的區塊
2. 找出被矩形覆蓋過半的字詞，判斷落在哪一個 `A.`–`E.` 選項行
3. 該選項所屬的題號，就是灰底標出的答案

用法：
    python3 tools/extract_94_answers.py            # 只比對，不寫檔
    python3 tools/extract_94_answers.py --apply    # 寫回題庫
"""
import json
import re
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / 'source' / 'legacy_src' / '2005' / '2005_筆試.pdf'
QJSON = ROOT / 'data' / 'legacy_wip' / '94_legacy.json'

OPT = re.compile(r'^([A-E])[.、]')
QNUM = re.compile(r'^(\d{1,3})\s*、')


def page_rows(page):
    """回傳 [(y, 種類, 值)]，種類是 'q'（題號）或 'o'（選項字母）。"""
    lines = {}
    for w in page.get_text('words'):
        lines.setdefault((w[5], w[6]), []).append(w)
    rows = []
    for ws in lines.values():
        ws.sort(key=lambda w: w[0])
        text = ' '.join(w[4] for w in ws)
        y = min(w[1] for w in ws)
        m = QNUM.match(text)
        if m and 1 <= int(m.group(1)) <= 100:
            rows.append((y, 'q', int(m.group(1))))
            continue
        m = OPT.match(text)
        if m:
            rows.append((y, 'o', m.group(1)))
    rows.sort()
    return rows


def highlights(page):
    """灰底矩形。行高範圍內、寬度不過小，且不是整頁背景。"""
    out = []
    for dr in page.get_drawings():
        if not dr.get('fill'):
            continue
        r = fitz.Rect(dr['rect'])
        # 寬度門檻要放得很低：Q57 的正解選項只有一個「8」字，灰底寬度不到 10
        if 3 < r.height < 30 and 3 < r.width < page.rect.width * 0.9:
            out.append(r)
    return out


def extract():
    doc = fitz.open(PDF)
    found = {}
    for page in doc:
        rows = page_rows(page)
        words = page.get_text('words')
        for r in highlights(page):
            covered = [w for w in words
                       if fitz.Rect(w[:4]).intersects(r)
                       and (min(w[3], r.y1) - max(w[1], r.y0)) > 0.5 * (w[3] - w[1])]
            if not covered:
                continue
            opts = [x for x in rows if x[1] == 'o']
            if not opts:
                continue
            letter = min(opts, key=lambda x: abs(x[0] - r.y0))[2]
            qs = [x for x in rows if x[1] == 'q' and x[0] < r.y0 + 4]
            if not qs:
                continue
            qid = qs[-1][2]
            found.setdefault(qid, (letter, ' '.join(w[4] for w in covered)[:40]))
    return found


def main() -> int:
    apply = '--apply' in sys.argv
    found = extract()
    paper = json.loads(QJSON.read_text(encoding='utf-8'))
    qmap = {q['id']: q for q in paper['questions']}

    same = diff = 0
    changes = []
    for qid in sorted(found):
        letter, text = found[qid]
        q = qmap.get(qid)
        if q is None or q.get('scoring') == 'unscored':
            continue
        if letter not in q['options']:
            print(f'  Q{qid}: 灰底指向 {letter}，但該題沒有這個選項——略過')
            continue
        if q['answer'] == letter:
            same += 1
        else:
            diff += 1
            changes.append((qid, q['answer'], letter, text))

    print(f'灰底抽出 {len(found)} 題；與現有題庫相符 {same}、不符 {diff}')
    for qid, old, new, text in changes:
        print(f'  Q{qid}: 題庫={old} → 灰底={new}（{text}）')

    missing = [i for i in range(1, 101)
               if i not in found and qmap[i].get('scoring') != 'unscored']
    if missing:
        print(f'\n沒有灰底可判讀的題號（{len(missing)}）：{missing}')

    if apply and changes:
        for qid, _, new, _ in changes:
            qmap[qid]['answer'] = new
        QJSON.write_text(json.dumps(paper, ensure_ascii=False, indent=1) + '\n',
                         encoding='utf-8')
        print(f'\n→ 已更新 {QJSON.name}（{len(changes)} 題）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
