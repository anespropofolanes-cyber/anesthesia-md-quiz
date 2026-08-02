#!/usr/bin/env python3
"""列出題庫實際引用的圖檔，供 Service Worker 離線快取使用。

離線實測時發現：題目與解析都讀得到，但**圖片全部載不到**——`sw.js` 從來沒有
把 `images/` 列入快取，40 題有圖的題目一離線就無法作答。

圖檔會隨著補抽陸續增加，把清單寫死在 sw.js 裡遲早會漏，所以改成產生一份
manifest，sw.js 讀它。`images/` 底下有些檔案已經沒有題目引用（早期抽取的殘留），
這裡只收**題庫真的用到的**，免得白白灌大離線體積。

用法：python3 tools/build_image_manifest.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / 'data' / 'image_manifest.json'


def referenced():
    names = set()
    globs = [
        (ROOT / 'data' / 'questions').glob('*.json'),
        (ROOT / 'data' / 'legacy_wip').glob('*.json'),
        (ROOT / 'data' / 'oral').glob('*.json'),
    ]
    for g in globs:
        for path in g:
            data = json.loads(path.read_text(encoding='utf-8'))
            for q in data.get('questions', []):
                names.update(q.get('images') or [])
                names.update((q.get('option_images') or {}).values())
                for sub in q.get('subquestions') or []:
                    names.update(sub.get('images') or [])
    return names


def main() -> int:
    names = sorted(referenced())
    missing = [n for n in names if not (ROOT / 'images' / n).exists()]
    if missing:
        print(f'✗ 題庫引用了 {len(missing)} 個不存在的圖檔：{missing[:8]}')
        return 1

    on_disk = {p.name for p in (ROOT / 'images').glob('*.png')}
    orphans = sorted(on_disk - set(names))

    DEST.write_text(json.dumps(names, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    total = sum((ROOT / 'images' / n).stat().st_size for n in names)
    print(f'{DEST.relative_to(ROOT)}：{len(names)} 張，共 {total / 1024 / 1024:.1f} MB')
    if orphans:
        print(f'（images/ 另有 {len(orphans)} 個沒被引用的檔案，未列入離線快取）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
