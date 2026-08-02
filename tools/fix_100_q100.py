#!/usr/bin/env python3
"""補回 100 年真正的第 100 題。

`parse_legacy_old.py` 抽 100 年（2011）時，Q100 抓到的是**第 1 題的重複**，
題幹還帶著頁首日期殘留：

    10.09 1、 有關嚴重腦部外傷…

真正的第 100 題（俯臥脊椎手術後的 visual loss）整題遺失。原因是切分器
往前推進時，最後一題沒有「下一個題號」可停，回頭誤配到卷首那一題。

答案不受影響：100 年的答案是獨立答案檔、依題號對應，Q100 的答案 E 本來就是
第 100 題的答案（原本被套在錯的題目上）。這支只換題幹與選項。

用法：python3 tools/fix_100_q100.py [--dry-run]
"""
import json
import re
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / 'source' / 'legacy_src' / '2011' / '2011_筆試考題.pdf'
QJSON = ROOT / 'data' / 'legacy_wip' / '100_legacy.json'


def tidy(s: str) -> str:
    s = re.sub(r'[ \t]*\n[ \t]*', ' ', s)
    return re.sub(r'\s{2,}', ' ', s).strip()


def main() -> int:
    dry = '--dry-run' in sys.argv
    text = '\n'.join(p.get_text() for p in fitz.open(PDF))
    m = re.search(r'(?m)^\s*100\s*、(.*)', text, re.S)
    if not m:
        raise SystemExit('原檔找不到第 100 題')
    block = m.group(1)

    opts = list(re.finditer(r'(?m)^\s*([A-E])\.\s', block))
    if len(opts) < 4:
        raise SystemExit(f'第 100 題只找到 {len(opts)} 個選項')
    stem = tidy(block[: opts[0].start()])
    options = {}
    for i, om in enumerate(opts):
        end = opts[i + 1].start() if i + 1 < len(opts) else len(block)
        options[om.group(1)] = tidy(block[om.end():end])

    paper = json.loads(QJSON.read_text(encoding='utf-8'))
    q = next(x for x in paper['questions'] if x['id'] == 100)
    print('舊題幹:', q['question'][:70])
    print('新題幹:', stem)
    for letter, t in options.items():
        print(f'  {letter}. {t}')
    print(f'答案維持 {q["answer"]}（獨立答案檔依題號對應，不受影響）')

    if not dry:
        q['question'] = stem
        q['options'] = options
        QJSON.write_text(json.dumps(paper, ensure_ascii=False, indent=1) + '\n',
                         encoding='utf-8')
        print(f'→ 已更新 {QJSON.name}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
