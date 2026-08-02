#!/usr/bin/env python3
"""把某個分類代碼底下的題目匯出成純文字，供設計子題架構時閱讀。

單層的 17 碼太粗——B2 麻醉藥理有 218 題、C13 其他有 182 題，點進去等於沒分類。
要往下拆子題，得先看清楚該類實際考些什麼。

用法：
    python3 tools/dump_category.py B2            # 印出 B2 的所有題目
    python3 tools/dump_category.py B2 --brief    # 只印題幹（設計架構時夠用）
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_all():
    out = []
    for d, pat in [('questions', '*_written.json'), ('legacy_wip', '*_legacy.json')]:
        for path in sorted((ROOT / 'data' / d).glob(pat)):
            paper = json.loads(path.read_text(encoding='utf-8'))
            out.extend(paper['questions'])
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    code = sys.argv[1]
    brief = '--brief' in sys.argv

    qs = [q for q in load_all() if q.get('category') == code]
    qs.sort(key=lambda q: (-q['year'], q['id']))
    print(f'# {code}：{len(qs)} 題\n')
    for q in qs:
        print(f'## {q["year"]} Q{q["id"]}')
        print(q['question'].replace('\n', ' ')[:220])
        if not brief:
            for letter, text in q['options'].items():
                print(f'   ({letter}) {text[:110]}')
            print(f'   答案：{q["answer"]}')
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
