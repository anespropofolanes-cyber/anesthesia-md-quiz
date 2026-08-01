#!/usr/bin/env python3
"""把題庫裡的 CJK 相容區碼位換成一般漢字。

108 年（698 字）、109 年（29 字）、112 年（2 字）的原始檔混用了 CJK Compatibility
Ideographs（U+F900–U+FAFF）。它們**看起來與一般漢字一模一樣**，但碼位不同：

    109 Q7 的「數」是 U+F969，不是 U+6578

後果是使用者在站上搜尋「數值」永遠找不到這一題，程式裡的字串比對也會莫名其妙
失敗（先前修疊字時就踩到這個坑）。NFC 正規化即可把相容區碼位映射回一般漢字，
字形不變。

只動 U+F900–U+FAFF 這個區段，其他字元一律不碰——全篇 NFKC 會把「（）」等全形
標點也改掉，那會動到題目原貌。

用法：python3 tools/normalize_cjk.py [--dry-run]
"""
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = sorted((ROOT / 'data' / 'questions').glob('*_written.json')) + \
          sorted((ROOT / 'data' / 'legacy_wip').glob('*_legacy.json'))


def fix(text: str) -> tuple:
    """回傳 (正規化後的字串, 換掉幾個字)。"""
    out = []
    n = 0
    for ch in text:
        if 0xF900 <= ord(ch) <= 0xFAFF:
            repl = unicodedata.normalize('NFC', ch)
            out.append(repl)
            n += 1
        else:
            out.append(ch)
    return ''.join(out), n


def main() -> int:
    dry = '--dry-run' in sys.argv
    total = 0
    for path in TARGETS:
        paper = json.loads(path.read_text(encoding='utf-8'))
        changed = 0
        samples = []
        for q in paper['questions']:
            new, n = fix(q['question'])
            if n:
                if len(samples) < 2:
                    samples.append(f'Q{q["id"]} 題幹：{new[:40]}')
                q['question'] = new
                changed += n
            for letter, old in q['options'].items():
                new, n = fix(old)
                if n:
                    q['options'][letter] = new
                    changed += n
        total += changed
        if changed:
            print(f'{paper["meta"]["year"]}：換掉 {changed} 個相容區碼位')
            for s in samples:
                print(f'    {s}')
            if not dry:
                path.write_text(json.dumps(paper, ensure_ascii=False, indent=1) + '\n',
                                encoding='utf-8')
    print(f'共 {total} 個' + ('（--dry-run，未寫檔）' if dry else '，已寫回題庫'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
