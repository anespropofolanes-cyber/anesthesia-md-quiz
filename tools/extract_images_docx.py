#!/usr/bin/env python3
"""抽 114 年（官方檔為 docx）題幹附圖，並把檔名寫回題庫。

`extract_images.py` 是從 PDF 頁面裁切算繪的，對 docx 完全沒作用——114 年因此
整年漏抽了 5 張圖（Q32、Q33、Q34、Q36、Q46），題幹寫著「下圖」卻沒有圖。

docx 沒有版面座標可用，改走文件流：`word/document.xml` 的段落依序掃，遇到
`numId=1 且 ilvl=0` 的段落就是下一題的題幹（與 `parse_official.py` 同一條規則，
恰好 100 段），圖片段落就歸給當下那一題。114 年 5 張圖都是題幹附圖，沒有
「選項本身是圖」的情形，所以不需要 PDF 版那套標號配對邏輯。

圖直接取原始嵌入物件（docx 的圖是完整 PNG，不像 PDF 那樣可能被切成好幾塊）。

用法：python3 tools/extract_images_docx.py
"""
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCX = ROOT / 'source' / 'official' / '114_筆試_官方.docx'
QJSON = ROOT / 'data' / 'questions' / '114_written.json'
IMGDIR = ROOT / 'images'
YEAR = 114


def image_map(docx: Path) -> dict:
    """回傳 {題號: [(媒體檔名, bytes), …]}。"""
    z = zipfile.ZipFile(docx)
    xml = z.read('word/document.xml').decode('utf-8')
    rels = z.read('word/_rels/document.xml.rels').decode('utf-8')
    relmap = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="media/([^"]+)"', rels))

    out: dict = {}
    qno = 0
    for para in re.findall(r'<w:p[ >].*?</w:p>|<w:p/>', xml, re.S):
        num_id = re.search(r'<w:numId w:val="(\d+)"', para)
        ilvl = re.search(r'<w:ilvl w:val="(\d+)"', para)
        if num_id and num_id.group(1) == '1' and ilvl and ilvl.group(1) == '0':
            qno += 1
        for rid in re.findall(r'r:embed="(rId\d+)"', para):
            name = relmap.get(rid)
            if not name:
                continue
            out.setdefault(qno, []).append((name, z.read(f'word/media/{name}')))
    if qno != 100:
        raise SystemExit(f'題幹數是 {qno}，不是 100——版面判定與 parse_official.py 不一致')
    return out


def main() -> None:
    IMGDIR.mkdir(exist_ok=True)
    mapping = image_map(DOCX)
    paper = json.loads(QJSON.read_text(encoding='utf-8'))
    qmap = {q['id']: q for q in paper['questions']}

    written = 0
    for qno, imgs in sorted(mapping.items()):
        if qno not in qmap:
            raise SystemExit(f'圖片落在不存在的題號 {qno}')
        names = []
        for i, (_, blob) in enumerate(imgs):
            suffix = '' if len(imgs) == 1 else f'_{i + 1}'
            name = f'{YEAR}_Q{qno}_stem{suffix}.png'
            (IMGDIR / name).write_bytes(blob)
            names.append(name)
            written += 1
        qmap[qno]['images'] = names
        print(f'Q{qno}: {", ".join(names)}')

    QJSON.write_text(json.dumps(paper, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'\n共 {written} 張圖，已寫回 {QJSON.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
