#!/usr/bin/env python3
"""驗證 data/concepts/<代碼>.json（教材）。

檢查：
  - 檔名的代碼與檔內 code 一致，且是 taxonomy 裡真的有的分類
  - 每節的 subtopic 存在於該分類的 subtopics
  - 同一份教材裡 subtopic 不重複
  - block 的 type 合法，且該型別必要欄位齊全
  - question_refs 指到真的存在的題目 source，且該題確實屬於這個分類與子題
  - 有 subtopic 卻沒教材的，只列出來提醒（不算錯）

任何改動教材之後都要跑，全綠才可以部署。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONCEPTS = ROOT / "data" / "concepts"
QUESTIONS = ROOT / "data" / "questions"
LEGACY = ROOT / "data" / "legacy_wip"

BLOCK_TYPES = {"text", "table", "compare", "pitfall"}

errors = []
warnings = []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def load_questions():
    """回傳 {source: (category, subtopic)}。題庫散在 data/questions 與已上線的舊考題。"""
    index = {}
    files = sorted(QUESTIONS.glob("*.json")) + sorted(LEGACY.glob("*.json"))
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        qs = data["questions"] if isinstance(data, dict) else data
        for q in qs:
            index[q["source"]] = (q.get("category"), q.get("subtopic"))
    return index


def check_block(b, where):
    t = b.get("type")
    if t not in BLOCK_TYPES:
        err(f"{where}：block type「{t}」不合法（只能是 {'／'.join(sorted(BLOCK_TYPES))}）")
        return
    if t in ("text", "pitfall"):
        if not str(b.get("content", "")).strip():
            err(f"{where}：{t} 區塊沒有 content")
    elif t == "table":
        cols = b.get("columns") or []
        rows = b.get("rows") or []
        if not cols:
            err(f"{where}：table 沒有 columns")
        if not rows:
            err(f"{where}：table 沒有 rows")
        for i, r in enumerate(rows):
            if not isinstance(r, list):
                err(f"{where}：table 第 {i + 1} 列不是陣列")
            elif len(r) != len(cols):
                err(f"{where}：table 第 {i + 1} 列有 {len(r)} 格，欄位有 {len(cols)} 個")
    elif t == "compare":
        items = b.get("items") or []
        if not items:
            err(f"{where}：compare 沒有 items")
        for i, it in enumerate(items):
            missing = [k for k in ("a", "b", "note") if not str(it.get(k, "")).strip()]
            if missing:
                err(f"{where}：compare 第 {i + 1} 項缺 {'／'.join(missing)}")


def main():
    taxonomy = json.loads((ROOT / "data" / "taxonomy.json").read_text(encoding="utf-8"))
    cats = {c["code"]: c for c in taxonomy["categories"]}
    qindex = load_questions()

    files = sorted(CONCEPTS.glob("*.json"))
    if not files:
        print("data/concepts/ 底下沒有教材檔")
        return 1

    total_sections = 0
    total_refs = 0
    covered = {}

    for f in files:
        code = f.stem
        where0 = f.name
        if code not in cats:
            err(f"{where0}：檔名代碼「{code}」不在 taxonomy 裡")
            continue
        cat = cats[code]
        valid_subs = {s["id"] for s in cat.get("subtopics", [])}

        data = json.loads(f.read_text(encoding="utf-8"))
        if data.get("code") != code:
            err(f"{where0}：檔內 code 是「{data.get('code')}」，與檔名不符")
        if not str(data.get("title", "")).strip():
            err(f"{where0}：沒有 title")
        if not str(data.get("intro", "")).strip():
            err(f"{where0}：沒有 intro")

        seen = set()
        sections = data.get("sections") or []
        if not sections:
            err(f"{where0}：沒有 sections")
        for s in sections:
            sub = s.get("subtopic")
            where = f"{where0} / {sub}"
            total_sections += 1
            if sub not in valid_subs:
                err(f"{where}：subtopic「{sub}」不在 {code} 的子題清單裡")
                continue
            if sub in seen:
                err(f"{where}：subtopic 重複")
            seen.add(sub)
            covered.setdefault(code, set()).add(sub)

            if not str(s.get("title", "")).strip():
                err(f"{where}：沒有 title")
            if not str(s.get("exam_focus", "")).strip():
                err(f"{where}：沒有 exam_focus")
            blocks = s.get("blocks") or []
            if not blocks:
                err(f"{where}：沒有 blocks")
            for i, b in enumerate(blocks):
                check_block(b, f"{where} block[{i}]")

            refs = s.get("question_refs") or []
            if not refs:
                warn(f"{where}：沒有 question_refs")
            if len(set(refs)) != len(refs):
                err(f"{where}：question_refs 有重複題號")
            for r in refs:
                total_refs += 1
                if r not in qindex:
                    err(f"{where}：question_refs 的「{r}」在題庫裡找不到")
                    continue
                rcat, rsub = qindex[r]
                if rcat != code:
                    err(f"{where}：「{r}」屬於分類 {rcat}，不是 {code}")
                elif rsub != sub:
                    err(f"{where}：「{r}」的子題是 {rsub}，不是 {sub}")

    # 覆蓋率：哪些子題還沒有教材
    missing = []
    for code, cat in cats.items():
        for s in cat.get("subtopics", []):
            if s["id"] not in covered.get(code, set()):
                missing.append(f"{code}/{s['id']}")
    all_subs = sum(len(c.get("subtopics", [])) for c in cats.values())

    print(f"教材 {len(files)} 份／子題小節 {total_sections} 節／代表題 {total_refs} 題")
    print(f"子題覆蓋率：{all_subs - len(missing)}/{all_subs}")
    if missing:
        print("  尚無教材：" + "、".join(missing))
    for w in warnings:
        print(f"提醒：{w}")
    if errors:
        print(f"\n✗ {len(errors)} 項錯誤")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("\n✓ 全部通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
