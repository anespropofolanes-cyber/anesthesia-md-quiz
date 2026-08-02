#!/usr/bin/env python3
"""把分批寫的子題重點整理併成 data/subtopic_briefs.json。

重點整理是「練這個子題之前該知道什麼」——由子代理讀完該子題的全部題目
與既有解析後歸納出高頻考點與易錯處，不是教科書節錄。

輸入：`audit/briefs/*.json`，鍵是 `"<分類>/<子題 id>"`。

用法：python3 tools/merge_briefs.py [--dry-run]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADIR = ROOT / 'audit' / 'briefs'
DEST = ROOT / 'data' / 'subtopic_briefs.json'
TAX = ROOT / 'data' / 'taxonomy.json'

# 重點整理是純文字，混進 markdown 會在網頁上原樣顯示成一堆星號與井號
MARKDOWN = re.compile(r'(?m)^\s*#{1,6}\s|\*\*|^\s*[-*]\s')


def main() -> int:
    dry = '--dry-run' in sys.argv
    tax = json.loads(TAX.read_text(encoding='utf-8'))
    valid = {f"{c['code']}/{s['id']}" for c in tax['categories'] for s in c.get('subtopics', [])}

    merged, errors = {}, []
    for path in sorted(ADIR.glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        for key, text in data.items():
            if key not in valid:
                errors.append(f'{path.name}: {key} 不是有效的子題')
                continue
            if key in merged:
                errors.append(f'{key} 在多個檔案裡都有')
                continue
            if not isinstance(text, str) or len(text.strip()) < 200:
                errors.append(f'{key}: 內容過短（{len(text or "")} 字）')
                continue
            if MARKDOWN.search(text):
                errors.append(f'{key}: 含 markdown 標記，網頁上會原樣顯示')
                continue
            merged[key] = text.strip()

    missing = sorted(valid - set(merged))
    if errors:
        print(f'✗ {len(errors)} 項問題：')
        for e in errors[:12]:
            print('   ' + e)
        return 1

    lens = sorted(len(v) for v in merged.values())
    print(f'{len(merged)}/{len(valid)} 個子題有重點整理')
    if lens:
        print(f'字數：最短 {lens[0]}、中位 {lens[len(lens) // 2]}、最長 {lens[-1]}')
    if missing:
        print(f'還沒寫的（{len(missing)}）：{missing[:8]}')

    if not dry:
        DEST.write_text(json.dumps(merged, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print(f'→ {DEST.relative_to(ROOT)}')
    else:
        print('（--dry-run，未寫檔）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
