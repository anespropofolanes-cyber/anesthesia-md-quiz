/* store.js — localStorage 存取層
   所有使用者資料都放這裡，方便匯出／匯入與版本升級。 */

const KEY = 'anes_md_v1';

const DEFAULTS = {
  wrong: {},      // source -> {at, my, n}       答錯紀錄（n = 累計答錯次數）
  right: {},      // source -> {at, n}           答對紀錄（用於主題進度）
  marks: {},      // source -> {at}              書籤
  notes: {},      // source -> {text, at}        個人筆記
  progress: null, // 進行中的一份練習
  prefs: { font: 1, shuffle: false, theme: 'light' }   // font：0-4，1 為預設 16px
};

let S = null;

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    S = raw ? { ...structuredClone(DEFAULTS), ...JSON.parse(raw) } : structuredClone(DEFAULTS);
    S.prefs = { ...DEFAULTS.prefs, ...(S.prefs || {}) };
  } catch (e) {
    console.warn('讀取本機資料失敗，改用預設值', e);
    S = structuredClone(DEFAULTS);
  }
  return S;
}

let saveTimer = null;
function save(immediate) {
  clearTimeout(saveTimer);
  const write = () => {
    try {
      localStorage.setItem(KEY, JSON.stringify(S));
    } catch (e) {
      toast('儲存失敗，瀏覽器空間可能已滿');
    }
  };
  if (immediate) write(); else saveTimer = setTimeout(write, 250);
}

const store = {
  get s() { return S || load(); },

  markRight(src) {
    const r = this.s.right[src] || { n: 0 };
    this.s.right[src] = { at: Date.now(), n: r.n + 1 };
    const w = this.s.wrong[src];
    if (w && r.n + 1 >= w.n + 2) delete this.s.wrong[src]; // 答對次數超前兩次即移出錯題本
    save();
  },
  markWrong(src, my) {
    const w = this.s.wrong[src] || { n: 0 };
    this.s.wrong[src] = { at: Date.now(), my, n: w.n + 1 };
    save();
  },
  isWrong(src) { return !!this.s.wrong[src]; },
  clearWrong(src) {
    if (src) delete this.s.wrong[src]; else this.s.wrong = {};
    save(true);
  },

  toggleMark(src) {
    if (this.s.marks[src]) delete this.s.marks[src];
    else this.s.marks[src] = { at: Date.now() };
    save(true);
    return !!this.s.marks[src];
  },
  isMarked(src) { return !!this.s.marks[src]; },

  getNote(src) { return (this.s.notes[src] || {}).text || ''; },
  setNote(src, text) {
    if (text.trim()) this.s.notes[src] = { text, at: Date.now() };
    else delete this.s.notes[src];
    save();
  },

  setProgress(p) { this.s.progress = p; save(); },
  clearProgress() { this.s.progress = null; save(true); },

  pref(k, v) {
    if (v === undefined) return this.s.prefs[k];
    this.s.prefs[k] = v; save(true); return v;
  },

  counts() {
    return {
      wrong: Object.keys(this.s.wrong).length,
      mark: Object.keys(this.s.marks).length,
      note: Object.keys(this.s.notes).length
    };
  },

  exportBlob() {
    const payload = { _app: '麻醉專科醫師題庫', _version: 1, _exportedAt: new Date().toISOString(), data: this.s };
    return new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  },

  /** 合併匯入：筆記若兩邊都有，保留較新的；紀錄取聯集。 */
  importObj(obj) {
    const d = obj && obj.data;
    if (!d || typeof d !== 'object') throw new Error('備份檔格式不正確');
    let n = 0;
    for (const k of ['wrong', 'right', 'marks']) {
      for (const [src, v] of Object.entries(d[k] || {})) {
        if (!this.s[k][src] || (v.at || 0) > (this.s[k][src].at || 0)) { this.s[k][src] = v; n++; }
      }
    }
    for (const [src, v] of Object.entries(d.notes || {})) {
      const cur = this.s.notes[src];
      if (!cur || (v.at || 0) > (cur.at || 0)) { this.s.notes[src] = v; n++; }
    }
    save(true);
    return n;
  },

  wipe() { S = structuredClone(DEFAULTS); save(true); }
};

load();
