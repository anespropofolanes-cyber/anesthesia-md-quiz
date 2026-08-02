#!/usr/bin/env python3
"""把舊考題的分類指派套用到題庫。

分類練習原本只涵蓋 894/1700 題——108–114 年（推定）與 104／106 年（學會官方標記）
有分類，其餘 800 題完全沒有，等於一半的題庫進不了分類練習。

輸入：`audit/taxonomy_assign/*.json`，格式為 `{"<source>": "<代碼>"}`，
例如 `{"107_written_Q1": "B1"}`。由子代理依 104／106 的官方標記慣例推定。

**不覆蓋已有的分類**：104／106 年是學會自己標的，比推定可靠，一律保留。
套用的題目會標 `category_source` 註明是推定而非官方。

用法：python3 tools/apply_taxonomy_legacy.py [--dry-run]
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QDIR = ROOT / 'data' / 'legacy_wip'
ADIR = ROOT / 'audit' / 'taxonomy_assign'
SOURCE_NOTE = '依 104／106 年學會標記慣例推定'


def load_codes():
    tax = json.loads((ROOT / 'data' / 'taxonomy.json').read_text(encoding='utf-8'))
    return {c['code'] for c in tax['categories']}


def load_assignments(codes):
    """讀進舊考題的指派檔，順便擋掉不存在的代碼與重複指派。

    官方年份（108–114）的指派檔用純題號當鍵（`"1": "C1"`），跨年會互相撞鍵，
    而且那些年份的分類早就套用過了。這裡只認 `<年>_written_Q<題號>` 這種鍵。
    """
    out, errors = {}, []
    for path in sorted(ADIR.glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            continue
        for src, code in data.items():
            if not re.fullmatch(r'\d{2,3}_written_Q\d{1,3}', src):
                continue                      # 官方年份的舊格式，跳過
            if not isinstance(code, str):
                continue
            if code not in codes:
                errors.append(f'{path.name}: {src} 的代碼 {code!r} 不在 taxonomy 裡')
                continue
            if src in out and out[src] != code:
                errors.append(f'{src} 被指派了兩個不同代碼：{out[src]} / {code}')
                continue
            out[src] = code
    return out, errors


def main() -> int:
    dry = '--dry-run' in sys.argv
    codes = load_codes()
    assign, errors = load_assignments(codes)
    if errors:
        print('✗ 指派檔有問題：')
        for e in errors:
            print('   ' + e)
        return 1
    print(f'讀到 {len(assign)} 筆指派')

    total_new = 0
    for path in sorted(QDIR.glob('*_legacy.json')):
        paper = json.loads(path.read_text(encoding='utf-8'))
        year = paper['meta']['year']
        added, kept, missing = 0, 0, []
        dist = Counter()
        for q in paper['questions']:
            if q.get('category'):
                kept += 1                      # 學會官方標記，不動
                continue
            code = assign.get(q['source'])
            if not code:
                missing.append(q['id'])
                continue
            q['category'] = code
            q['category_source'] = SOURCE_NOTE
            dist[code] += 1
            added += 1
        if added or missing:
            note = f'{year}：新增 {added}'
            if kept:
                note += f'、保留官方 {kept}'
            if missing:
                note += f'、仍缺 {len(missing)}（{missing[:6]}…）' if len(missing) > 6 \
                    else f'、仍缺 {len(missing)}（{missing}）'
            print(note)
        total_new += added
        if added and not dry:
            path.write_text(json.dumps(paper, ensure_ascii=False, indent=1) + '\n',
                            encoding='utf-8')

    print(f'\n共套用 {total_new} 題' + ('（--dry-run，未寫檔）' if dry else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
