#!/usr/bin/env python3
"""把子題指派套用到題庫。

輸入：`audit/subtopic_assign/*.json`，格式為 `{"<source>": "<子題 id>"}`。
由子代理逐題讀完題幹與選項後指派，依 taxonomy 的 `_meta.boundary_rules` 判斷邊界。

**子題必須屬於該題自己的分類**——B2 的題不能指派到 C8 的子題。這條在套用時
強制檢查，不合的一律擋下不寫入，因為分類練習是照第一層代碼進來的，
子題掛錯類會讓那一題在介面上永遠找不到。

用法：python3 tools/apply_subtopics.py [--dry-run]
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADIR = ROOT / 'audit' / 'subtopic_assign'
TAX = ROOT / 'data' / 'taxonomy.json'
SOURCE_NOTE = '依題目實際考點指派（非學會官方分類，學會只到第一層代碼）'


def load_valid():
    """{分類代碼: {子題 id}}。"""
    tax = json.loads(TAX.read_text(encoding='utf-8'))
    return {c['code']: {s['id'] for s in c.get('subtopics', [])} for c in tax['categories']}


def load_assignments():
    out, errors = {}, []
    for path in sorted(ADIR.glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        for src, sub in data.items():
            if src in out and out[src] != sub:
                errors.append(f'{src} 被指派了兩個不同子題：{out[src]} / {sub}')
                continue
            out[src] = sub
    return out, errors


def main() -> int:
    dry = '--dry-run' in sys.argv
    valid = load_valid()
    assign, errors = load_assignments()
    print(f'讀到 {len(assign)} 筆指派')

    applied = 0
    dist = Counter()
    for d, pat in [('questions', '*_written.json'), ('legacy_wip', '*_legacy.json')]:
        for path in sorted((ROOT / 'data' / d).glob(pat)):
            paper = json.loads(path.read_text(encoding='utf-8'))
            changed = 0
            for q in paper['questions']:
                sub = assign.get(q['source'])
                if not sub:
                    continue
                code = q.get('category')
                if not code:
                    errors.append(f'{q["source"]}: 有子題指派但沒有第一層分類')
                    continue
                if sub not in valid.get(code, set()):
                    errors.append(f'{q["source"]}: 子題 {sub!r} 不屬於分類 {code}')
                    continue
                q['subtopic'] = sub
                q['subtopic_source'] = SOURCE_NOTE
                dist[f'{code}/{sub}'] += 1
                changed += 1
            applied += changed
            if changed and not dry:
                path.write_text(json.dumps(paper, ensure_ascii=False, indent=1) + '\n',
                                encoding='utf-8')

    if errors:
        print(f'\n✗ {len(errors)} 項問題：')
        for e in errors[:15]:
            print('   ' + e)
        return 1

    # 每個子題都該有題目——空的子題在介面上是一張點不了的卡
    empty = [f'{c}/{s}' for c, subs in valid.items() for s in subs if f'{c}/{s}' not in dist]
    print(f'\n套用 {applied} 題，涵蓋 {len(dist)} 個子題')
    if empty:
        print(f'沒有題目的子題（{len(empty)}）：{empty}')
    if dry:
        print('（--dry-run，未寫檔）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
