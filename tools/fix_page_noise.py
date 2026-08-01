#!/usr/bin/env python3
"""清掉舊考題題幹與選項裡的頁首頁尾雜訊。

103／104／106 年的原始 PDF 每頁印著 `Page #`，102 年印著 `Exhibit: 2013 麻專筆試`，
抽取時被當成內文吃了進去，讀起來就像：

    有關於 Maternal-fetal drug transfer 的敘述，下列敘述何者為非? Page #
    Axillary block 的超音波短軸圖如下，請問箭頭處為何構造: Exhibit:

這些字樣只會出現在版面邊緣，不可能是題目內容，整批刪掉即可。刪完若整段變空
就不動它——寧可留著雜訊，也不要生出一個空白選項。

用法：python3 tools/fix_page_noise.py [--dry-run]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = sorted((ROOT / 'data' / 'legacy_wip').glob('*_legacy.json'))

NOISE = re.compile(
    r'\s*(?:Page\s*#?\s*\d*'          # 103／104／106 年的頁尾
    r'|Exhibit\s*:?'                  # 102 年圖片題的標記
    r'|20\d\d\s*麻專筆試)\s*'          # 102 年的頁首（也會單獨出現在題幹開頭）
)


def clean(text: str) -> str:
    out = NOISE.sub(' ', text)
    out = re.sub(r'\s{2,}', ' ', out).strip()
    return out if out else text        # 清成空的就維持原樣


def main() -> int:
    dry = '--dry-run' in sys.argv
    total = 0
    for path in TARGETS:
        paper = json.loads(path.read_text(encoding='utf-8'))
        changed = 0
        for q in paper['questions']:
            tag = f"{paper['meta']['year']} Q{q['id']}"
            new = clean(q['question'])
            if new != q['question']:
                print(f'{tag} 題幹\n   舊: {q["question"]}\n   新: {new}')
                q['question'] = new
                changed += 1
            for letter, old in q['options'].items():
                new = clean(old)
                if new != old:
                    print(f'{tag} ({letter})\n   舊: {old}\n   新: {new}')
                    q['options'][letter] = new
                    changed += 1
        total += changed
        if changed and not dry:
            path.write_text(json.dumps(paper, ensure_ascii=False, indent=1) + '\n',
                            encoding='utf-8')
            print(f'→ 已更新 {path.name}（{changed} 處）\n')

    print(f'共清掉 {total} 處雜訊' + ('（--dry-run，未寫檔）' if dry else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
