#!/usr/bin/env python3
"""把 data/explanations/parts/<年>_p*.json 併成 data/explanations/<年>_expl.json。

解析是分批寫的（每批 25 題），這支只負責合併與加上 meta，內容一字不改。
併完請跑 tools/validate_explanations.py。

用法：python3 tools/merge_explanations.py 114
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

META_NOTE = ('AI 整理，非官方內容。題目與答案以台灣麻醉醫學會公告為準，'
             '解析僅供理解參考，與學會無關。')


def merge(year: int) -> int:
    parts = sorted((ROOT / 'data' / 'explanations' / 'parts').glob(f'{year}_p*.json'))
    if not parts:
        print(f'找不到 {year} 年的分批檔')
        return 1

    merged: dict[str, str] = {}
    for p in parts:
        chunk = json.loads(p.read_text(encoding='utf-8'))
        dup = set(chunk) & set(merged)
        if dup:
            print(f'✗ {p.name} 與先前的分批重複題號：{sorted(dup, key=int)}')
            return 1
        merged.update(chunk)
        print(f'  {p.name}：{len(chunk)} 題')

    paper = json.loads(
        (ROOT / 'data' / 'questions' / f'{year}_written.json').read_text(encoding='utf-8'))
    ids = [str(q['id']) for q in paper['questions']]
    missing = [i for i in ids if i not in merged]
    if missing:
        print(f'✗ 缺 {len(missing)} 題：{", ".join(missing[:20])}')
        return 1

    out = {
        'meta': {
            'year': year,
            'kind': 'explanation',
            'note': META_NOTE,
            'official': False,
            'generated_by': 'Claude（分批撰寫）＋ tools/merge_explanations.py',
        },
        'explanations': {i: merged[i] for i in ids},
    }
    dest = ROOT / 'data' / 'explanations' / f'{year}_expl.json'
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'→ {dest.relative_to(ROOT)}：{len(ids)} 題')
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(merge(int(sys.argv[1])))
