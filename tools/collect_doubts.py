#!/usr/bin/env python3
"""把各批解析的疑慮筆記彙整成一份報告。

寫解析時每 25 題一批，遇到「答案可疑」「兩個選項都錯」「單位誤植」之類的情形
就各自寫進 `audit/explanation_doubts/<年>_p<批>.md`。檔案一多就沒人看得完，
這支把它們併成一份 `audit/DOUBTS.md`，依年份由新到舊排列。

對舊考題來說這份報告特別重要：108–114 年有官方答案卡可以逐題核對，
舊考題沒有，這些筆記是唯一的把關記錄。

用法：python3 tools/collect_doubts.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'audit' / 'explanation_doubts'
DEST = ROOT / 'audit' / 'DOUBTS.md'

OFFICIAL = {108, 109, 110, 111, 112, 113, 114}


def main() -> int:
    files = sorted(SRC.glob('*_p*.md'))
    by_year: dict = {}
    for f in files:
        m = re.match(r'(\d+)_p(\d+)', f.stem)
        if not m:
            continue
        by_year.setdefault(int(m.group(1)), []).append((int(m.group(2)), f))

    lines = [
        '# 解析撰寫時記下的疑慮',
        '',
        '由 `tools/collect_doubts.py` 從 `audit/explanation_doubts/` 彙整，**不要直接編輯本檔**。',
        '',
        '這些是撰寫解析時逐題細讀後記下的觀察：答案可疑、兩個選項都錯、單位或拼字誤植等。',
        '**題庫的答案一律未依這些疑慮改動**——解析都是照官方／檔案答案寫的，這裡只做記錄。',
        '',
        '108–114 年有學會公告的答案卡可逐題核對，這些疑慮多半是命題品質問題。',
        '舊考題沒有答案卡，這份記錄是唯一的把關。',
        '',
    ]

    total = 0
    for year in sorted(by_year, reverse=True):
        kind = '官方答案卡可核對' if year in OFFICIAL else '無官方答案卡'
        lines.append(f'## 民國 {year} 年（{kind}）')
        lines.append('')
        for part, f in sorted(by_year[year]):
            body = f.read_text(encoding='utf-8').strip()
            # 把各批自己的標題降級，避免與本檔的層級打架
            body = re.sub(r'^#+ ', lambda m: '#' * min(len(m.group(0).strip()) + 2, 6) + ' ',
                          body, flags=re.M)
            start = (part - 1) * 25 + 1
            lines.append(f'### Q{start}–Q{start + 24}')
            lines.append('')
            lines.append(body)
            lines.append('')
            total += 1

    DEST.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{DEST.relative_to(ROOT)}：{len(by_year)} 個年份、{total} 份筆記')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
