#!/usr/bin/env python3
"""清掉 PDF 文字層重疊造成的整段重複。

109 年官方 PDF 的文字層有重疊圖層，抽出來會把一整段字印兩次：

    三個獨立影響酸鹼平衡的因子，何者為非 影響酸鹼平衡的因子，何者為非 ?
    BIS 值下降通常與意識喪失有相關性，但是有三個麻醉藥例外，分別是
      通常與意識喪失有相關性，但是有三個麻醉藥例外，分別是ketamine、…

印出來的考卷是正常的，重複只存在於文字層。形狀一律是 A + S + S + B——
同一段 S 連著出現兩次——所以只在偵測到這種嚴格連續重複時刪掉一份。

**只處理 109 年**，而且重複片段必須含中文字。這兩條限制不是保守而已，是必要的：
純字元比對會把 `norepinephrine, epinephrine,` 判成重複（`epinephrine, ` 剛好是
`norepinephrine, ` 的後綴），一跑就會把 113 Q67 的三個升壓劑刪成兩個。
只有 109 年的 PDF 有這個文字層問題，其他年份不該碰。

用法：python3 tools/fix_duplicated_text.py [--dry-run]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = [ROOT / 'data' / 'questions' / '109_written.json']

# 門檻壓到 2 個字，才抓得到「例外？ 外？」「執行 執行」這種短疊字。夠安全的原因是
# acceptable() 要求重複的兩份之間隔著空白——中文正常書寫不會這樣斷開。
MIN_RUN = 2
HAN = re.compile(r'[一-鿿]')
DUP = re.compile(r'(.{%d,}?)\s+\1' % MIN_RUN)   # 兩份之間必須隔著空白


def acceptable(text: str, m) -> bool:
    """判斷這個重複是不是圖層重疊造成的。

    含中文的片段直接收——中文沒有詞界，`影響酸鹼平衡的因子…` 這種重複起點
    多半落在字中間。純英文的片段則要求起點落在詞界（開頭或空白之後），
    否則 `norepinephrine, epinephrine,` 會被當成 `epinephrine, ` 重複兩次，
    一刪就少掉一個升壓劑。
    """
    if HAN.search(m.group(1)):
        return True
    if m.group(1)[0].isspace():        # 片段自己就從空白起頭，等於落在詞界
        return True
    return m.start() == 0 or text[m.start() - 1].isspace()


def dedupe(text: str) -> str:
    """把連續重複兩次的片段收成一份，重複收斂為止。"""
    prev = None
    while prev != text:
        prev = text
        for m in DUP.finditer(text):
            if acceptable(text, m):
                text = text[:m.start()] + m.group(1) + text[m.end():]
                break
    return re.sub(r'\s{2,}', ' ', text).strip()


def main() -> int:
    dry = '--dry-run' in sys.argv
    total = 0
    for path in TARGETS:
        paper = json.loads(path.read_text(encoding='utf-8'))
        changed = 0
        for q in paper['questions']:
            tag = f"{paper['meta']['year']} Q{q['id']}"
            new_stem = dedupe(q['question'])
            if new_stem != q['question']:
                print(f'{tag} 題幹')
                print(f'   舊: {q["question"]}')
                print(f'   新: {new_stem}')
                q['question'] = new_stem
                changed += 1
            for letter, old in q['options'].items():
                new = dedupe(old)
                if new != old:
                    print(f'{tag} ({letter})')
                    print(f'   舊: {old}')
                    print(f'   新: {new}')
                    q['options'][letter] = new
                    changed += 1
        total += changed
        if changed and not dry:
            path.write_text(json.dumps(paper, ensure_ascii=False, indent=1) + '\n',
                            encoding='utf-8')
            print(f'→ 已更新 {path.name}（{changed} 處）\n')

    print(f'共清掉 {total} 處重複' + ('（--dry-run，未寫檔）' if dry else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
