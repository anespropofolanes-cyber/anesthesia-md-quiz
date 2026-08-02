# 麻醉專科醫師題庫

**線上使用**：<https://anespropofolanes-cyber.github.io/anesthesia-md-quiz/>

台灣麻醉醫學會麻醉科專科醫師甄審歷屆筆試題庫，純靜態 PWA，無框架、無建置流程。

## 題庫

| 範圍 | 題數 | 答案來源 |
|---|---|---|
| 民國 108–114 年 | 700 | 學會公告的答案卡，**逐題核對** |
| 民國 104／106 年 | 200 | **命題端檔案**（每題附教科書出處、難易度、分類代碼），非公開公告 |
| 民國 102／103／107 年 | 300 | 考卷檔案內附，無公開公告可核對 |
| 民國 93／94／99／100／101 年 | 500 | 考卷檔案內附（前綴、Word 註解或獨立答案檔），無公開公告可核對 |

**全部 1700 題都有解析**（`data/explanations/`），標明「AI 整理，非官方」，
預設收合。沒有官方答案卡的年份另外標示解析是依考卷檔案所附的答案撰寫。

**1694 題有分類代碼**：104／106 年是學會官方標記，其餘依其慣例推定
（標 `category_source`）。缺的 6 題是 106 年原檔就沒填。

另有 **12 題口試與 3 站超音波**（`data/oral/`），照抄學會原檔的官方參考答案，
不計分。110、113、114 年學會未公布參考答案，站上有標示。

三者在網站上明確區隔：沒有公開公告的年份，年份籤是虛線框加 ⚠，
題目上依 `answer_tier` 顯示「答案來自命題端檔案」或「答案未經官方核對」。

## 本機執行

```bash
python3 -m http.server 8811
```

然後開 <http://localhost:8811>。直接用瀏覽器開 `index.html` 不行（fetch 會被 file:// 擋掉）。

## 改動題庫之後一定要跑

```bash
python3 tools/validate_questions.py     # 700 題：結構＋答案逐題比對官方答案卡
python3 tools/validate_legacy.py        # 1000 題：結構、判分、分類覆蓋率
python3 tools/validate_explanations.py  # 1700 題解析：題號齊全、不得與答案矛盾
python3 tools/crosscheck_legacy.py      # 跨年重複題交叉驗證，矛盾數必須為 0
python3 tools/validate_oral.py          # 口試與超音波：配分、圖檔、標題是否切錯
python3 tools/build_image_manifest.py   # 圖檔有增減時重跑，否則離線會缺圖
```

`validate_questions.py` 沒有全綠就不可以部署。

## 工具

| 檔案 | 用途 |
|---|---|
| `tools/parse_official.py` | 從官方考卷抽 108–114 年題目 |
| `tools/parse_legacy_years.py` | 抽 102／103／104／106／107 年題目 |
| `tools/extract_images.py` | 抽圖片題的圖並寫回題庫 |
| `tools/apply_answer_notes.py` | 替多答案題補上公告出處 |
| `tools/apply_taxonomy.py` | 套用分類結果 |
| `tools/validate_questions.py` | 官方年份的驗證（部署前必跑） |
| `tools/validate_legacy.py` | 舊考題的結構驗證 |
| `tools/crosscheck_legacy.py` | 用跨年重複題交叉驗證舊考題的答案 |
| `tools/parse_oral.py` | 抽口試題目、子題配分與參考答案 |
| `tools/parse_ultrasound.py` | 抽 108 年超音波三站 |
| `tools/validate_oral.py` | 口試與超音波的驗證 |
| `tools/inventory_legacy.py` | 盤點 2003–2012 的答案來源（只讀不寫） |
| `tools/merge_explanations.py` | 把分批寫的解析併成 `<年>_expl.json` |
| `tools/collect_doubts.py` | 彙整各批解析記下的疑慮成 `audit/DOUBTS.md` |
| `tools/apply_taxonomy_legacy.py` | 套用舊考題的推定分類（不覆蓋官方標記） |
| `tools/build_image_manifest.py` | 產生離線快取用的圖檔清單 |
| `tools/extract_94_answers.py` | 從 94 年原卷的灰底標示重建答案 |
| `tools/extract_images_docx.py` | 抽 114 年 docx 內的題幹附圖 |
| `tools/fix_*.py` | 修 PDF 抽取的各種汙染（截斷、重複、頁碼、編號遺失） |

`parse_*.py` 會覆蓋題庫檔，所以重跑之後要接著跑 `apply_answer_notes.py`、
`apply_taxonomy.py`、`extract_images.py`，再跑驗證。

## 改版流程

三個地方要一起改，否則使用者會拿到新舊混雜的檔案：

1. `index.html` 的 `?v=`
2. `sw.js` 的 `ASSET_V`
3. `sw.js` 的 `VERSION` 加一（`js/app.js` 的 `CACHE_NAME` 必須與 `sw.js` 的 `CACHE` 一致）

## 其他

詳細的資料來源查證、判分規則、分類架構由來與踩過的坑，都記在 `PROGRESS.md`。
