#!/usr/bin/env python3
"""修補 106 年命題端檔案的欄位錯置。

106 年每題附有「出處／難易度／分類」三行，抽取時有兩種狀況會出錯：

- **難易度欄是空的**（Q56、Q57）：parser 把下一行「分類：C11」整串當成難易度值，
  網站上就會顯示「難易度：分類：C11」。
- **原檔自己填錯**（Q9）：出處欄寫成「A」、難易度欄填成「2014 筆試題庫 QUESTION 47」，
  兩個欄位互相錯位。同一題的分類 B1 原檔有寫，但沒被抽到。

Q31／36／37／55／59／67 沒有分類是**原檔本來就沒填**，不是抽取問題，維持原樣
（有分類的恰好 93 題，與先前的紀錄相符）。

用法：python3 tools/fix_examiner_metadata.py [--dry-run]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / 'data' / 'legacy_wip' / '106_legacy.json'


def main() -> int:
    dry = '--dry-run' in sys.argv
    paper = json.loads(PATH.read_text(encoding='utf-8'))
    qmap = {q['id']: q for q in paper['questions']}
    changed = []

    # 難易度欄空白，吃進了下一行的分類
    for qid in (56, 57):
        q = qmap[qid]
        if str(q.get('difficulty', '')).startswith('分類'):
            changed.append(f'Q{qid}: 移除誤植的難易度 {q["difficulty"]!r}（原檔該欄空白）')
            q.pop('difficulty', None)

    # 原檔自己把出處與難易度填錯位，分類則是抽取漏掉
    q9 = qmap[9]
    if q9.get('reference') == 'A':
        changed.append("Q9: 移除出處 'A'、難易度 '2014 筆試題庫'（原檔這兩欄互相錯位）")
        q9.pop('reference', None)
        q9.pop('difficulty', None)
    if not q9.get('category'):
        changed.append('Q9: 補回原檔標的分類 B1')
        q9['category'] = 'B1'
        q9['category_raw'] = 'B1'

    for line in changed:
        print(line)
    if changed and not dry:
        PATH.write_text(json.dumps(paper, ensure_ascii=False, indent=1) + '\n',
                        encoding='utf-8')
        print(f'→ 已更新 {PATH.name}')
    if not changed:
        print('沒有需要修補的欄位')
    return 0


if __name__ == '__main__':
    sys.exit(main())
