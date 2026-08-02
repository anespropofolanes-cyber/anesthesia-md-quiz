#!/usr/bin/env python3
"""用跨年重複題交叉驗證舊考題的答案。

102–107 年沒有學會公告的答案卡，答案取自考卷檔案本身，無法直接核對。
但歷年考題會重複出題——只要同一題同時出現在舊考題與「有官方答案卡」的
108–114 年，兩邊的答案是否一致就是硬證據。

比對時要小心兩件事，否則會誤判成「答案不一致」：

1. **選項順序會被打散**：同一題在不同年份的 (A)(B)(C)(D) 排列可能不同，
   所以要比對答案「選項的文字內容」，不是比對字母。
2. **同題幹但不同版本**：學會常沿用題幹、換掉全部選項另出一題。
   這種情況兩邊的答案本來就不同，不算矛盾。判準是選項組是否有交集。

輸出報告到 audit/crosscheck_legacy.md。
"""
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFICIAL_DIR = ROOT / "data" / "questions"
LEGACY_DIR = ROOT / "data" / "legacy_wip"
REPORT = ROOT / "audit" / "crosscheck_legacy.md"

PUNCT = re.compile(r"[，,。.、？?！!：:；;（）()「」【】\[\]\"'’“”]")


# 同一題在不同年份的卷子上會有異體字差異（週／周、台／臺…）
VARIANTS = str.maketrans("週裡佈昇歷麽жЖ", "周里布升历么жЖ")


def norm(s):
    s = PUNCT.sub("", re.sub(r"[\s　]+", "", str(s))).lower()
    return s.translate(VARIANTS)


def close(a, b):
    """兩段文字是不是同一句話的不同轉錄。

    同一題被兩年沿用時，轉錄常有細微出入——多一個「雖」字、把「狀況」寫進去、
    異體字——語意完全相同。這種差異不該被當成答案矛盾擋下部署，
    但門檻要夠高，免得把真的不同的選項也吞掉。
    """
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= 0.85


def load(dir_path, pattern):
    out = {}
    for path in sorted(dir_path.glob(pattern)):
        data = json.loads(path.read_text("utf-8"))
        for q in data["questions"]:
            out.setdefault(norm(q["question"]), []).append((data["meta"]["year"], q))
    return out


def classify(lq, oq):
    """回傳 (結論, 說明)。"""
    l_opts = {norm(v): k for k, v in lq["options"].items() if v.strip()}
    o_opts = {norm(v): k for k, v in oq["options"].items() if v.strip()}
    shared = set(l_opts) & set(o_opts)

    l_ans = norm(lq["options"].get(lq["answer"][0], ""))
    o_ans = norm(oq["options"].get(oq["answer"][0], ""))

    if lq["answer"] == oq["answer"] and l_ans == o_ans:
        return "一致", "答案字母與內容都相同"
    if l_ans and l_ans == o_ans:
        return "一致", f"選項順序不同（舊 {lq['answer']} ＝ 官方 {oq['answer']}），答案內容相同"
    if close(l_ans, o_ans):
        return "一致", "答案內容相同，兩年的轉錄有細微字句差異"
    if not shared or len(shared) <= 1:
        return "不同版本", f"選項組幾乎無交集（共用 {len(shared)} 個選項），是沿用題幹另出的題"
    return "矛盾", f"選項組有 {len(shared)} 個重疊，但答案內容不同——需要人工判斷"


def main():
    official = load(OFFICIAL_DIR, "*_written.json")
    legacy = load(LEGACY_DIR, "*_legacy.json")

    rows = []
    for stem, legs in legacy.items():
        if stem not in official or len(stem) <= 15:
            continue
        ly, lq = legs[0]
        oy, oq = official[stem][0]
        verdict, why = classify(lq, oq)
        rows.append((verdict, ly, lq, oy, oq, why))

    order = {"矛盾": 0, "不同版本": 1, "一致": 2}
    rows.sort(key=lambda r: (order[r[0]], r[1], r[2]["id"]))

    counts = {k: sum(1 for r in rows if r[0] == k) for k in order}
    lines = [
        "# 舊考題答案交叉驗證",
        "",
        "由 `tools/crosscheck_legacy.py` 產生。原理見該檔的說明。",
        "",
        f"題幹相同、橫跨舊考題與官方年份的題目共 **{len(rows)} 題**：",
        "",
        f"- 一致：**{counts['一致']}**",
        f"- 同題幹但選項組不同（沿用題幹另出的題，不算矛盾）：**{counts['不同版本']}**",
        f"- **矛盾：{counts['矛盾']}**",
        "",
    ]
    for verdict, ly, lq, oy, oq, why in rows:
        lines += [
            f"## {verdict}　舊 {ly} Q{lq['id']}（{lq['answer']}）vs 官方 {oy} Q{oq['id']}（{oq['answer']}）",
            "",
            f"> {oq['question'][:90]}",
            "",
            f"- {why}",
            f"- 舊檔答案：{lq['options'].get(lq['answer'][0], '')[:90]}",
            f"- 官方答案：{oq['options'].get(oq['answer'][0], '')[:90]}",
            "",
        ]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), "utf-8")

    print(f"重複題 {len(rows)} 題：一致 {counts['一致']}、"
          f"不同版本 {counts['不同版本']}、矛盾 {counts['矛盾']}")
    print(f"報告：{REPORT.relative_to(ROOT)}")
    return 1 if counts["矛盾"] else 0


if __name__ == "__main__":
    sys.exit(main())
