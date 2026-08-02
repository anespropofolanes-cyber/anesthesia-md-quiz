/* data.js — 題庫載入
   資料是分年的 JSON，首次用到才 fetch，載入後快取在記憶體。 */

/** 有學會公告答案卡可逐題核對的年份。 */
const YEARS = [108, 109, 110, 111, 112, 113, 114];

/** 只有考卷檔案內附答案、無官方答案卡可核對的年份。 */
const LEGACY_YEARS = [93, 94, 99, 100, 101, 102, 103, 104, 106, 107];

const ALL_YEARS = [...YEARS].reverse().concat([...LEGACY_YEARS].reverse());

/** 口試與超音波是情境練習，不計分，與筆試分開存放。 */
const ORAL_YEARS = [114, 113, 112, 111, 110, 108];

const DB = {
  oral: null,        // [{year, id, title, scenario, subquestions, …}]
  ultrasound: null,
  oralIndex: null,   // 筆記鍵 -> {題目, 子題}，筆記頁要靠它把口試筆記找回來
  taxonomy: null,
  briefs: null,    // "B2/inhalational" -> 該子題的重點整理（純文字版）
  concepts: null,  // "B2" -> 該類的教材（分節、含表格與陷阱框）
  papers: {},      // 108 -> {meta, questions}
  index: null,     // source -> question（全部載入後才有）
  catName: {},     // "B1" -> "麻醉生理"
  catOrder: []
};

function isLegacyYear(y) { return LEGACY_YEARS.includes(Number(y)); }
function paperPath(y) {
  return isLegacyYear(y) ? `data/legacy_wip/${y}_legacy.json` : `data/questions/${y}_written.json`;
}

async function getJSON(path) {
  const r = await fetch(path, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`載入失敗 ${path}（${r.status}）`);
  return r.json();
}

async function loadTaxonomy() {
  if (DB.taxonomy) return DB.taxonomy;
  const t = await getJSON('data/taxonomy.json');
  DB.taxonomy = t;
  // 子題的重點整理（純文字版，教材尚未改寫的分類會用到）
  DB.briefs = await getJSON('data/subtopic_briefs.json').catch(() => ({}));
  for (const c of t.categories) {
    DB.catName[c.code] = c.name;
    DB.catOrder.push(c.code);
  }
  return t;
}

async function loadPaper(year) {
  year = Number(year);
  if (DB.papers[year]) return DB.papers[year];
  const p = await getJSON(paperPath(year));
  const verified = p.meta.verified !== false;
  p.questions.forEach(q => { q.year = year; q.verified = verified; });
  // AI 解析（非官方）是分年陸續補上的，檔案不存在就當作沒有，不擋題目載入
  const ex = await getJSON(`data/explanations/${year}_expl.json`).catch(() => null);
  if (ex) p.questions.forEach(q => { q.explanation = ex.explanations[String(q.id)] || null; });
  DB.papers[year] = p;
  return p;
}

/** 載入全部年份並建立 source 索引。分類練習、搜尋、錯題本都需要。 */
async function loadAll() {
  if (DB.index) return DB.index;
  await Promise.all(ALL_YEARS.map(loadPaper));
  DB.index = {};
  for (const p of Object.values(DB.papers)) {
    for (const q of p.questions) DB.index[q.source] = q;
  }
  return DB.index;
}

function allQuestions() { return Object.values(DB.index || {}); }

/** 口試（各年）與超音波（108 年三站）。抓不到就當作沒有，不擋其他功能。 */
async function loadOral() {
  if (DB.oral) return DB.oral;
  const files = await Promise.all(ORAL_YEARS.map(y =>
    getJSON(`data/oral/${y}_oral.json`).catch(() => null)));
  DB.oral = files.filter(Boolean).flatMap(f => f.questions);
  DB.ultrasound = (await getJSON('data/oral/108_ultrasound.json').catch(() => null))?.questions || [];

  DB.oralIndex = {};
  for (const q of DB.oral) {
    q.subquestions.forEach((s, i) => {
      s.noteKey = oralNoteKey(q, i);
      DB.oralIndex[s.noteKey] = { question: q, sub: s, index: i };
    });
  }
  return DB.oral;
}

/** 口試筆記的鍵。用年份＋題號＋子題序號，重跑解析器也不會變。 */
function oralNoteKey(q, i) {
  return `oral:${q.year}:${q.id}:${i + 1}`;
}
function isOralNoteKey(k) { return String(k).startsWith('oral:'); }

function byCategory(code, { verifiedOnly = false } = {}) {
  return allQuestions()
    .filter(q => q.category === code && (!verifiedOnly || q.verified))
    .sort((a, b) => b.year - a.year || a.id - b.id);
}

/** 子題底下的題目。子題只在該分類內唯一，所以要連分類一起比對。 */
function bySubtopic(code, subId) {
  return byCategory(code).filter(q => q.subtopic === subId);
}

/** 教材：一個學會代碼一份，底下每節對應一個子題。
    首次用到才抓，抓不到就當作這一類還沒有教材。 */
async function loadConcept(code) {
  DB.concepts ||= {};
  if (code in DB.concepts) return DB.concepts[code];
  const c = await getJSON(`data/concepts/${code}.json`).catch(() => null);
  DB.concepts[code] = c;
  return c;
}

/** 分類的子題定義（沒有子題就回空陣列，介面自己退回舊版呈現）。 */
function subtopicsOf(code) {
  const c = (DB.taxonomy?.categories || []).find(x => x.code === code);
  return c?.subtopics || [];
}

/* ── 判分 ──
   每題的 scoring 欄位決定怎麼判：
     exact  單一正解
     any    答案卡有兩個字母，選任一個都算對
            （全部來自事後申覆／委員會決議，考卷本身是單選題）
     free   送分，一律計對
   舊版護理師網站用 split('') 比對，送分題永遠判錯，這裡不重蹈覆轍。 */
function isFree(q) { return q.scoring === 'free' || q.answer === '送分'; }
/** 原檔本身缺答案或選項的題目，只能閱讀不能判分。 */
function isUnscored(q) { return q.scoring === 'unscored'; }
function isMulti(q) { return q.scoring === 'any'; }
function isCorrect(q, pick) {
  if (isFree(q)) return true;
  if (isUnscored(q)) return false;
  return !!pick && q.answer.includes(pick);
}
function answerText(q) {
  if (isUnscored(q)) return '原檔缺答案';
  if (isFree(q)) return '送分（全題給分）';
  return q.answer.split('').join(' 或 ');
}

/** 該題實際有哪些選項標號——各年四選項與五選項混用。 */
function optionLetters(q) {
  return Object.keys(q.options || {});
}
