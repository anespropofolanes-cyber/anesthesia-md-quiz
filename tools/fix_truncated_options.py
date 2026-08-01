#!/usr/bin/env python3
"""用官方 PDF 修正選項文字被截斷或多出雜訊的題目。

parser 修過兩個坑，但整份重抽會蓋掉後製欄位（分類、圖檔、answer_note），
所以這支只動選項文字，其餘欄位一律不動：

1. **被截斷**：`split_options` 原本只要文字裡出現 (A)–(E) 就當成新選項的起點，
   選項內文引用其他選項時就會被就地切斷（113 Q13 的四個選項全成了「Panel」）。
2. **多出雜訊**：110 年官方 PDF 第 2、3 頁完全重複，Q5 的選項 D 尾巴吃進了
   重複頁的頁首與第 1 題題幹。

只在新舊文字是單純的前綴關係時才覆蓋（一方是另一方的開頭），確定是這兩種
情形才動手，避免把 parser 的其他行為差異一併寫進題庫。

用法：python3 tools/fix_truncated_options.py [--dry-run]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parse_official as P   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
QDIR = ROOT / 'data' / 'questions'
PDF_YEARS = [108, 109, 110, 111, 112, 113]   # 114 是 docx，走另一條抽取路徑


def main() -> int:
    dry = '--dry-run' in sys.argv
    total = 0
    for year in PDF_YEARS:
        path = QDIR / f'{year}_written.json'
        paper = json.loads(path.read_text(encoding='utf-8'))
        qmap = {q['id']: q for q in paper['questions']}
        blocks = P.parse_pdf_year(year)
        changed = 0

        for qid, block in blocks.items():
            q = qmap.get(qid)
            if q is None:
                continue
            _, fresh = P.split_options(block)
            opt_imgs = q.get('option_images', {})
            for letter, old in q['options'].items():
                if letter in opt_imgs:      # 選項是圖，文字本來就空
                    continue
                new = fresh.get(letter, '').strip()
                old = old.strip()
                if not (old and new) or new == old:
                    continue
                if new.startswith(old):
                    kind = '截斷'
                elif old.startswith(new):
                    kind = '多出雜訊'
                else:
                    continue        # 不是單純的前綴關係，不碰
                print(f'{year} Q{qid} ({letter}) — {kind}')
                print(f'   舊: {old}')
                print(f'   新: {new}')
                q['options'][letter] = new
                changed += 1

        total += changed
        if changed and not dry:
            path.write_text(json.dumps(paper, ensure_ascii=False, indent=1) + '\n',
                            encoding='utf-8')
            print(f'→ 已更新 {path.name}（{changed} 個選項）\n')

    print(f'共補回 {total} 個被截斷的選項' + ('（--dry-run，未寫檔）' if dry else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
