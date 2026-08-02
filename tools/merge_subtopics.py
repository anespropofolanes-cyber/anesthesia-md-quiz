#!/usr/bin/env python3
"""把四批子題設計併進 data/taxonomy.json。

單層的 17 個學會代碼太粗——B2 麻醉藥理 218 題、C13 其他 182 題，點進去等於
沒分類。改成兩層：**學會代碼仍是第一層**（104／106 年是學會官方標記，這是
這套分類唯一的權威依據），底下依實際考題內容再分子題。

輸入：`audit/subtopic_design/proposal_*.json`，由子代理逐題讀完該類題目後設計。
各批另外寫了 `_meta.boundary_rules`（例如「問技術本身歸 cpb，問疾病術式歸
cardiac_surgery」），一併收進來——之後指派 1700 題時要靠它保持一致。

用法：python3 tools/merge_subtopics.py [--dry-run]
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADIR = ROOT / 'audit' / 'subtopic_design'
TAX = ROOT / 'data' / 'taxonomy.json'


def load_proposals():
    subs, rules, errors = {}, [], []
    seen_ids = Counter()
    for path in sorted(ADIR.glob('proposal_*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        for key, val in data.items():
            if key == '_meta':
                for r in (val.get('boundary_rules') or []):
                    rules.append(r if isinstance(r, str) else json.dumps(r, ensure_ascii=False))
                continue
            if key in subs:
                errors.append(f'{key} 在多個提案檔裡都出現')
                continue
            subs[key] = val
            for s in val:
                seen_ids[s['id']] += 1
    for sid, n in seen_ids.items():
        if n > 1:
            errors.append(f'子題 id 重複：{sid}（出現 {n} 次）')
    return subs, rules, errors


def actual_counts():
    """題庫裡各分類的實際題數，用來對照設計時的估計值。"""
    counts = Counter()
    for d, pat in [('questions', '*_written.json'), ('legacy_wip', '*_legacy.json')]:
        for path in (ROOT / 'data' / d).glob(pat):
            for q in json.loads(path.read_text(encoding='utf-8'))['questions']:
                if q.get('category'):
                    counts[q['category']] += 1
    return counts


def main() -> int:
    dry = '--dry-run' in sys.argv
    subs, rules, errors = load_proposals()
    tax = json.loads(TAX.read_text(encoding='utf-8'))
    codes = [c['code'] for c in tax['categories']]

    missing = [c for c in codes if c not in subs]
    extra = [c for c in subs if c not in codes]
    if missing:
        errors.append(f'這些分類沒有子題設計：{missing}')
    if extra:
        errors.append(f'提案裡有不存在的分類：{extra}')
    if errors:
        print('✗ 提案有問題：')
        for e in errors:
            print('   ' + e)
        return 1

    actual = actual_counts()
    total_sub = 0
    for c in tax['categories']:
        items = subs[c['code']]
        c['subtopics'] = [
            {'id': s['id'], 'name': s['name'], 'desc': s.get('desc', '')} for s in items
        ]
        total_sub += len(items)
        est = sum(s['est'] for s in items)
        real = actual.get(c['code'], 0)
        flag = '' if abs(est - real) <= 2 else f'  ← 估計 {est} 與實際 {real} 差 {abs(est - real)}'
        print(f'{c["code"]}：{len(items)} 個子題，估計 {est} 題{flag}')

    tax['_meta']['subtopic_note'] = (
        '子題是依實際考題內容細分的，不是學會的官方分類——學會只到第一層的 17 碼。'
        '每題的子題指派標在 subtopic 欄位。')
    if rules:
        tax['_meta']['boundary_rules'] = rules

    print(f'\n共 {total_sub} 個子題')
    if not dry:
        TAX.write_text(json.dumps(tax, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print(f'→ 已寫入 {TAX.relative_to(ROOT)}')
    else:
        print('（--dry-run，未寫檔）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
