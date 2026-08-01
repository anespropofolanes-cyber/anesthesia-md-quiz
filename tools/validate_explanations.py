#!/usr/bin/env python3
"""AI 解析檔的驗證。任何改動 data/explanations/ 之後都要跑。

檢查：
- 解析檔的題號與該年題庫完全一致（不多、不少、不重複）
- 每則解析非空且有實質長度
- 解析裡若明寫「答案是 X」，X 必須是官方答案之一
  （scoring=any 的題目兩個字母都算；送分題不檢查）
- meta 必須標明非官方

解析檔是分年陸續補上的，缺整年只提示、不算錯。
"""
from __future__ import annotations   # 這台機器的 python3 是 3.9，需要它才能用 int | None

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFICIAL_YEARS = [108, 109, 110, 111, 112, 113, 114]
LEGACY_YEARS = [93, 94, 99, 100, 101, 102, 103, 104, 106, 107]
YEARS = OFFICIAL_YEARS + LEGACY_YEARS


def paper_path(year):
    if year in OFFICIAL_YEARS:
        return ROOT / 'data' / 'questions' / f'{year}_written.json'
    return ROOT / 'data' / 'legacy_wip' / f'{year}_legacy.json'

# 「正解是 B」「正確答案為 (C)」「答案應為D」等寫法
ANS_RE = re.compile(r'(?:正解|正確答案|答案)(?:是|為|應為|應是|選)?\s*[（(]?([A-E])[）)]?')


def check_year(year: int, errors: list[str]) -> int | None:
    path = ROOT / 'data' / 'explanations' / f'{year}_expl.json'
    if not path.exists():
        return None
    ex = json.loads(path.read_text(encoding='utf-8'))
    paper = json.loads(paper_path(year).read_text(encoding='utf-8'))
    qmap = {str(q['id']): q for q in paper['questions']}

    meta = ex.get('meta', {})
    if '非官方' not in json.dumps(meta, ensure_ascii=False):
        errors.append(f'{year}: meta 沒有標明「非官方」')
    if meta.get('year') != year:
        errors.append(f'{year}: meta.year 是 {meta.get("year")}')

    got = ex.get('explanations', {})
    missing = sorted(set(qmap) - set(got), key=int)
    extra = sorted(set(got) - set(qmap), key=int)
    if missing:
        errors.append(f'{year}: 缺 {len(missing)} 題：{", ".join(missing[:10])}…' if len(missing) > 10
                      else f'{year}: 缺題號 {", ".join(missing)}')
    if extra:
        errors.append(f'{year}: 多出不存在的題號 {", ".join(extra)}')

    for qid, text in got.items():
        q = qmap.get(qid)
        if q is None:
            continue
        if not isinstance(text, str) or len(text.strip()) < 50:
            errors.append(f'{year} Q{qid}: 解析過短或非文字')
            continue
        if 'TODO' in text or '待補' in text:
            errors.append(f'{year} Q{qid}: 解析含未完成標記')
        # 送分題沒有標準答案；unscored 是原檔缺答案或選項的舊考題，都不比對字母
        if q['scoring'] in ('free', 'unscored') or not q.get('answer'):
            continue
        for m in ANS_RE.finditer(text):
            if m.group(1) not in q['answer']:
                errors.append(f'{year} Q{qid}: 解析寫「答案 {m.group(1)}」但官方答案是 {q["answer"]}')
    return len(got)


def main() -> int:
    errors: list[str] = []
    total = 0
    for y in YEARS:
        n = check_year(y, errors)
        if n is None:
            print(f'{y}：（還沒有解析檔）')
        else:
            total += n
            print(f'{y}：{n} 題解析')
    print(f'\n共 {total} 題解析。')
    if errors:
        print(f'\n✗ {len(errors)} 個問題：')
        for e in errors:
            print('  ' + e)
        return 1
    print('結構全部通過。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
