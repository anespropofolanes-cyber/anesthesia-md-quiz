#!/usr/bin/env python3
"""清掉混進題幹與選項的「出處／難易度」註記。

99 年（2010）的原始檔在每題後面附了命題端的註記，抽取時被當成內文吃進去，
而且常常一次夾好幾筆、插在句子中間：

    使用嘆息法可以打開塌陷的肺泡,但是要用到40 公分水柱的壓力才有效
      出處:Miller 7th P362 易 出處:Miller 7th P1820-1822 中(術後FEV1% : 27%)

    下列何者正確? 出處:Miller 7th P565-567 難易度:易 出處:Miller 7th P603-605 難易度:易
      (1)Propofol 的作用部位…

`parse_legacy_old.py` 本來就有移除註記的邏輯，但只擋得住行首那種寫法。

只刪「出處：」開頭到難易度為止的片段，其餘一律不碰。刪完若整段變空就維持原樣。

用法：python3 tools/fix_source_annotations.py [--dry-run]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = sorted((ROOT / 'data' / 'legacy_wip').glob('*_legacy.json'))

# 註記的寫法在同一份檔案裡就有好幾種：
#   出處:Miller 7th P362 易
#   出處:Miller 6th Ch P.607 Table 15-2 難易度:中
#   Ch P.1189 中          ← 連書名都省了
#   題參考處:Anesthesia, 5th edition, p1914 難易度:
#
# 「出處：」前綴寫成可有可無：同一處常連著好幾筆，前一筆的比對會把下一筆的
# 「出處」二字一起吃掉，只認有前綴的話會留下 `:Miller 7th P1641…` 這種殘骸。
# 靠書名或 `Ch P.` 當錨點就夠安全——題目內容不會出現這些字串加頁碼。
# Mill[ae]r：99 Q100 的原檔把書名拼成「Millar 6th」
BOOK = (r'(?:Mill[ae]r\s*\d+(?:th|nd|rd|st)?'
        r'|Anesthesia\s*,?\s*\d+(?:th|nd|rd|st)?\s*edition)')
_PAGE = r'(?:Ch\s*)?[Pp]\.?\s*\d[\d\s,，、\.\-–~～;；]*'
# 書名與頁碼至少要出現一個，否則整條規則會匹配到空字串、把空白亂插進內文
NOISE = re.compile(
    r'\s*(?:題?參考處|出處)?\s*[:：]?\s*'
    r'(?:' + BOOK + r'\s*[,，]?\s*(?:' + _PAGE + r')?'   # 94 年寫成「…5th edition, p1914」
    r'|' + _PAGE + r')'
    r'(?:(?:Table|Box|Fig(?:ure)?)[\s\w\-–\.]*)?'
    r'[,，、\s]*'
    r'(?:難\s*易\s*度?\s*[:：]\s*)?'
    r'(?:[易中難](?:\s*[~～]\s*[易中難])?)?\s*'
)
# 清完偶爾留下沒有頁碼的斷尾，例如 `Ch P. 易`、`難易度:`
TAIL = re.compile(r'\s*(?:Ch\s*P\.?|難\s*易\s*度?\s*[:：])\s*[易中難]?\s*')


def clean(text: str) -> str:
    out = text
    for _ in range(6):                 # 連續多筆，反覆清到收斂
        new = NOISE.sub(' ', out)
        if new == out:
            break
        out = new
    out = TAIL.sub(' ', out)
    out = re.sub(r'\s{2,}', ' ', out).strip()
    return out if out else text


def main() -> int:
    dry = '--dry-run' in sys.argv
    total = 0
    for path in TARGETS:
        paper = json.loads(path.read_text(encoding='utf-8'))
        changed = 0
        for q in paper['questions']:
            tag = f"{paper['meta']['year']} Q{q['id']}"
            new = clean(q['question'])
            if new != q['question']:
                print(f'{tag} 題幹\n   舊: {q["question"][:130]}\n   新: {new[:130]}')
                q['question'] = new
                changed += 1
            for letter, old in q['options'].items():
                new = clean(old)
                if new != old:
                    print(f'{tag} ({letter})\n   舊: {old[:130]}\n   新: {new[:130]}')
                    q['options'][letter] = new
                    changed += 1
        total += changed
        if changed and not dry:
            path.write_text(json.dumps(paper, ensure_ascii=False, indent=1) + '\n',
                            encoding='utf-8')
            print(f'→ 已更新 {path.name}（{changed} 處）\n')

    print(f'共清掉 {total} 處註記' + ('（--dry-run，未寫檔）' if dry else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
