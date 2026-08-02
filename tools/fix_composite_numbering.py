#!/usr/bin/env python3
"""把 101 年複合題的敘述編號補回來。

101 年（2012）有一批題目長這樣：題幹之後接 4–5 個敘述，選項則是「1+2+3」這種
組合。但敘述的編號是 Word 自動編號，文字層看不到，`parse_legacy_old.py` 又把
題幹與敘述用空白串成一行，結果站上呈現的是：

    有關局部麻醉劑的敘述,下列何者為是? 局部麻醉劑可逆性的阻斷鈉離子通道… 在合宜
    溶解度下… Cocaine歸類於esters… 低血氧會加重局部麻醉劑的毒性。
    (A) 1+2+3+4  (B) 僅1+2+4  …

讀者根本無從得知哪一句是 1、哪一句是 2——**這種題目實際上無法作答**。

docx 裡題幹與敘述各自是獨立段落，順序完好，所以只要照原順序編號再串回去即可。
只處理「選項是數字組合」的題目，其餘一律不碰。

用法：python3 tools/fix_composite_numbering.py [--dry-run]
"""
import json
import re
import sys
import unicodedata
import html as _html
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCX = ROOT / 'source' / 'legacy_src' / '2012' / '2012_筆試題目.docx'
QJSON = ROOT / 'data' / 'legacy_wip' / '101_legacy.json'

# 組合式選項：「1+2+3」「僅1+3」，也可能是單獨一個「2」「僅4」。
# 允許單一數字，但下面另外要求整題至少有一個選項含 +，
# 免得把 108 Q77 那種「58/55/43/48/70」純數字選項的題目也算進來。
COMBO = re.compile(r'^\s*(?:僅\s*)?[1-9](?:\s*\+\s*[1-9])*\s*$')
HAS_PLUS = re.compile(r'\d\s*\+\s*\d')


def docx_paragraphs():
    xml = zipfile.ZipFile(DOCX).read('word/document.xml').decode('utf-8')
    out = []
    for para in re.split(r'</w:p>', xml):
        text = ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', para))
        text = unicodedata.normalize('NFKC', _html.unescape(text)).strip()
        if not text:
            continue
        m = re.search(r'<w:ilvl w:val="(\d+)"', para)
        out.append((int(m.group(1)) if m else 0, text))
    return out


def groups():
    """重跑 parse_legacy_old 的切分，但保留題幹各段不合併。"""
    paras = docx_paragraphs()
    head, rest = paras[:7], paras[7:]
    first = ({'stem': [head[1][1]], 'options': [t for _, t in head[2:7]]}
             if len(head) == 7 else None)
    out, current = ([first] if first else []), None
    for lvl, text in rest:
        if lvl == 0:
            if current and current['options']:
                out.append(current)
                current = None
            if current is None:
                current = {'stem': [text], 'options': []}
            else:
                current['stem'].append(text)
        elif current is not None:
            current['options'].append(text)
    if current and current['options']:
        out.append(current)
    return out


def main() -> int:
    dry = '--dry-run' in sys.argv
    paper = json.loads(QJSON.read_text(encoding='utf-8'))
    qmap = {q['id']: q for q in paper['questions']}
    parsed = groups()

    changed = 0
    for i, g in enumerate(parsed, start=1):
        q = qmap.get(i)
        if q is None or len(g['stem']) < 2:
            continue
        # 只處理選項是數字組合的題目
        values = list(q['options'].values())
        if not all(COMBO.match(t) for t in values):
            continue
        if not any(HAS_PLUS.search(t) for t in values):
            continue
        stem = g['stem'][0]
        items = g['stem'][1:]
        new = stem + '\n' + '\n'.join(f'{n}. {t}' for n, t in enumerate(items, start=1))
        if new == q['question']:
            continue
        print(f'Q{i}（{len(items)} 個敘述）')
        print(f'   舊: {q["question"][:100]}…')
        print(f'   新: {new[:100]}…')
        q['question'] = new
        changed += 1

    if changed and not dry:
        QJSON.write_text(json.dumps(paper, ensure_ascii=False, indent=1) + '\n',
                         encoding='utf-8')
        print(f'→ 已更新 {QJSON.name}')
    print(f'共修正 {changed} 題' + ('（--dry-run，未寫檔）' if dry else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
