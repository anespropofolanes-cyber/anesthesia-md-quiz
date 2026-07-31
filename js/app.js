/* app.js — 啟動、路由與首頁互動 */

const SEL = { year: 114, cats: new Set(), mode: 'practice' };

/* ── 路由 ── */
function go(name) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('on'));
  const el = document.getElementById('s-' + name);
  (el || document.getElementById('s-home')).classList.add('on');
  if (location.hash !== '#' + name) history.replaceState(null, '', '#' + name);
  window.scrollTo({ top: 0, behavior: 'instant' });

  if (name === 'cats') renderCategories();
  if (name === 'oral') loadOral().then(renderOral);
  if (name === 'wrong') renderList('wrong');
  if (name === 'marks') renderList('mark');
  if (name === 'notes') renderList('note');
  if (name === 'home') renderResume();
  if (name === 'search') setTimeout(() => document.getElementById('q').focus(), 60);
}

/* ── 首頁：續作 ── */
function renderResume() {
  const p = store.s.progress;
  const slot = document.getElementById('resume-slot');
  if (!p || !p.order || !p.order.length) { slot.innerHTML = ''; return; }
  const done = Object.keys(p.picks || {}).length;
  slot.innerHTML = `<div class="resume">
    <div class="h">有一份還沒做完</div>
    <div class="s">${esc(p.label)}　${p.mode === 'exam' ? '模擬考試' : '練習模式'}
      已答 ${done}／${p.order.length}　${timeAgo(p.at)}</div>
    <div class="row">
      <button class="btn primary sm" onclick="resume()">繼續作答</button>
      <button class="btn sm" onclick="store.clearProgress();renderResume()">捨棄</button>
    </div></div>`;
}

function resume() {
  const p = store.s.progress;
  if (!p) return;
  const list = p.order.map(s => DB.index[s]).filter(Boolean);
  if (list.length !== p.order.length) {
    toast('題目已更新，無法接續'); store.clearProgress(); renderResume(); return;
  }
  startQuiz(list, { mode: p.mode, label: p.label, origin: p.origin || 'years', restore: p });
}

function timeAgo(t) {
  if (!t) return '';
  const m = Math.floor((Date.now() - t) / 60000);
  if (m < 1) return '剛剛';
  if (m < 60) return `${m} 分鐘前`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} 小時前`;
  return `${Math.floor(h / 24)} 天前`;
}

/* ── 歷屆試題選卷 ── */
function buildPickers() {
  // 每一年都有完整答案，記號標的是「答案來源」而不是「有沒有答案」——
  // 先前一律用 ⚠ 會被讀成「這年沒答案」，所以三級各有各的樣子。
  document.getElementById('pick-year').innerHTML = ALL_YEARS.map(y => {
    const tier = yearTier(y);
    const mark = tier === 'exam_file' ? ' ※' : '';
    return `<button class="chip ${y === SEL.year ? 'on' : ''} tier-${tier}"
       title="${esc(TIER_LABEL[tier])}" onclick="setYear(${y})">${y}${mark}</button>`;
  }).join('');

  document.getElementById('pick-cat').innerHTML = DB.taxonomy.categories.map(c =>
    `<button class="chip sm ${SEL.cats.has(c.code) ? 'on' : ''}" onclick="toggleCat('${c.code}')">${c.name}</button>`).join('');
}

/** 三級答案來源：official 官方公告／examiner 命題端檔案／exam_file 考卷檔案內附。 */
const TIER_LABEL = {
  official: '答案出自學會公開公告的答案卡，已逐題核對',
  examiner: '答案出自命題端檔案（每題附教科書出處與難易度），非公開公告',
  exam_file: '答案出自考卷檔案本身，沒有公開公告可核對'
};

function yearTier(y) {
  if (!isLegacyYear(y)) return 'official';
  return DB.papers[Number(y)]?.questions[0]?.answer_tier || 'exam_file';
}

function setYear(y) { SEL.year = y; buildPickers(); updateCount(); }
function toggleCat(c) { SEL.cats.has(c) ? SEL.cats.delete(c) : SEL.cats.add(c); buildPickers(); updateCount(); }
function setMode(m) {
  SEL.mode = m;
  document.querySelectorAll('#pick-mode .chip').forEach(c => c.classList.toggle('on', c.dataset.v === m));
}
function toggleShuffle() {
  const v = !store.pref('shuffle');
  store.pref('shuffle', v);
  const b = document.getElementById('chip-order');
  b.textContent = v ? '隨機出題' : '依題號';
}

function selected() {
  const p = DB.papers[SEL.year];
  if (!p) return [];
  return p.questions.filter(q => !SEL.cats.size || SEL.cats.has(q.category));
}

function updateCount() {
  const n = selected().length;
  const el = document.getElementById('year-count');
  const legacy = isLegacyYear(SEL.year);
  const tier = yearTier(SEL.year);
  el.innerHTML = (n === 100 ? '整卷 100 題' : `符合條件 ${n} 題`) +
    '　<span class="src">' + esc(TIER_LABEL[tier]) + '。</span>';
  document.querySelector('#s-years .btn.primary').disabled = n === 0;
}

async function startYear() {
  await loadPaper(SEL.year);
  const list = selected();
  startQuiz(list, {
    mode: SEL.mode, origin: 'years', shuffle: store.pref('shuffle'),
    label: `${SEL.year} 年筆試${list.length < 100 ? `（篩選 ${list.length} 題）` : ''}`
  });
}

/* ── 由 source 清單開練 ── */
function practiceSources(sources, label, origin = 'review', shuffle = false) {
  const list = sources.map(s => DB.index[s]).filter(Boolean);
  startQuiz(list, { mode: 'practice', label, origin, shuffle });
}
function practiceList(kind) {
  const keys = Object.keys(kind === 'wrong' ? store.s.wrong : store.s.marks);
  if (!keys.length) { toast(kind === 'wrong' ? '錯題本是空的' : '還沒有書籤'); return; }
  practiceSources(keys, kind === 'wrong' ? '錯題複習' : '書籤複習', kind === 'wrong' ? 'wrong' : 'marks', true);
}

/* ── 小工具 ── */
function toggleMark(src) {
  const on = store.toggleMark(src);
  toast(on ? '已加入書籤' : '已取消書籤');
  refreshCounts();
  if (document.getElementById('s-quiz').classList.contains('on')) renderQuiz();
}

function refreshCounts() {
  const c = store.counts();
  document.getElementById('n-wrong').textContent = c.wrong;
  document.getElementById('n-mark').textContent = c.mark;
  document.getElementById('n-note').textContent = c.note;
}

/* ── 主題 ── 預設淺色；auto 才跟隨系統 */
const THEMES = [
  { id: 'light', icon: '☀', label: '淺色' },
  { id: 'dark', icon: '☾', label: '深色' },
  { id: 'auto', icon: '◐', label: '跟隨系統' }
];
function cycleTheme() {
  const cur = store.pref('theme') || 'light';
  const i = THEMES.findIndex(t => t.id === cur);
  const next = THEMES[(i + 1) % THEMES.length];
  store.pref('theme', next.id);
  applyTheme();
  toast('配色：' + next.label);
}
function applyTheme() {
  const id = store.pref('theme') || 'light';
  document.documentElement.className = id;
  const t = THEMES.find(x => x.id === id) || THEMES[0];
  const b = document.getElementById('btn-theme');
  if (b) { b.textContent = t.icon; b.title = '配色：' + t.label; b.classList.toggle('on', id !== 'light'); }
  const dark = id === 'dark' || (id === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches);
  document.querySelectorAll('meta[name="theme-color"]').forEach(m => m.remove());
  const m = document.createElement('meta');
  m.name = 'theme-color';
  m.content = dark ? '#1e2122' : '#fff9b3';
  document.head.appendChild(m);
}

/* 字級 5 段，預設第 2 段（16px）。 */
const FONT_LABELS = ['小', '中', '大', '特大', '最大'];
function stepFont(d) {
  const n = Math.min(FONT_LABELS.length - 1, Math.max(0, (store.pref('font') ?? 1) + d));
  store.pref('font', n);
  applyFont();
}
function applyFont() {
  let n = store.pref('font');
  if (typeof n !== 'number' || n < 0 || n >= FONT_LABELS.length) n = 1;
  document.body.className = 'fs-' + n;
  const lv = document.getElementById('font-level');
  if (lv) lv.textContent = FONT_LABELS[n];
  const dn = document.getElementById('btn-font-down');
  const up = document.getElementById('btn-font-up');
  if (dn) dn.disabled = n === 0;
  if (up) up.disabled = n === FONT_LABELS.length - 1;
}

function openLightbox(src) {
  document.getElementById('lightbox-img').src = src;
  document.getElementById('lightbox').classList.add('on');
}
function closeLightbox() { document.getElementById('lightbox').classList.remove('on'); }
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeLightbox();
  if (!document.getElementById('s-quiz').classList.contains('on')) return;
  if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
  if (e.key === 'ArrowLeft') move(-1);
  if (e.key === 'ArrowRight') move(1);
  // 有些年份是五選項，鍵盤快捷鍵要含 E
  if (/^[a-eA-E]$/.test(e.key)) pick(e.key.toUpperCase());
});

let toastTimer = null;
function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('on');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('on'), 2000);
}

/* ── 匯出／匯入 ── */
function exportData() {
  const url = URL.createObjectURL(store.exportBlob());
  const a = document.createElement('a');
  a.href = url;
  a.download = `麻醉醫師題庫備份_${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
  toast('備份檔已下載');
}

function importData(input) {
  const f = input.files && input.files[0];
  if (!f) return;
  const r = new FileReader();
  r.onload = () => {
    try {
      const n = store.importObj(JSON.parse(r.result));
      toast(`已匯入 ${n} 筆紀錄`);
      refreshCounts(); renderResume();
    } catch (e) {
      toast('匯入失敗：' + e.message);
    }
    input.value = '';
  };
  r.readAsText(f);
}

const CACHE_NAME = 'anes-md-v8';   // 必須與 sw.js 的 CACHE 一致

/** 核心資源（不含圖片）。由頁面確保入快取，不倚賴 service worker 的安裝時機——
    使用者清過瀏覽器資料、或 sw.js 未改版時 install 不會重跑，靠這裡補齊。 */
function coreUrls() {
  const css = document.querySelector('link[href*="css/app.css"]')?.getAttribute('href') || 'css/app.css';
  const v = (css.split('?v=')[1] || '');
  const q = v ? `?v=${v}` : '';
  return [
    './', './index.html', `./css/app.css${q}`,
    ...['store', 'data', 'quiz', 'views', 'app'].map(f => `./js/${f}.js${q}`),
    './manifest.webmanifest', './assets/logo.png',
    './icons/icon-192.png', './icons/icon-512.png', './icons/icon-180.png',
    './data/taxonomy.json',
    ...ORAL_YEARS.map(y => `./data/oral/${y}_oral.json`),
    './data/oral/108_ultrasound.json',
    ...YEARS.map(y => `./data/questions/${y}_written.json`),
    ...LEGACY_YEARS.map(y => `./data/legacy_wip/${y}_legacy.json`)
  ];
}

async function ensureOfflineCore() {
  if (!('caches' in window)) return;
  try {
    const c = await caches.open(CACHE_NAME);
    for (const u of coreUrls()) {
      if (await c.match(u)) continue;
      try {
        // cache:'reload' 繞過瀏覽器 HTTP 快取，避免存到舊檔
        const res = await fetch(u, { cache: 'reload' });
        if (res.ok) await c.put(u, res);
      } catch { /* 離線中，下次再補 */ }
    }
  } catch { /* 不影響使用 */ }
}

/** 圖檔由使用者主動觸發才下載，以免耗用行動網路。 */
async function cacheImages() {
  const btn = document.getElementById('btn-dl-img');
  const st = document.getElementById('dl-status');
  const imgs = [...new Set(allQuestions().flatMap(q =>
    [...(q.images || []), ...Object.values(q.option_images || {})]).map(f => 'images/' + f))];
  if (!('caches' in window)) { st.textContent = '這個瀏覽器不支援離線快取。'; return; }
  if (!imgs.length) { st.textContent = '目前沒有圖片需要下載。'; return; }

  btn.disabled = true;
  let done = 0, failed = 0;
  const c = await caches.open(CACHE_NAME);
  for (const u of imgs) {
    try {
      const res = await fetch(u, { cache: 'reload' });
      if (!res.ok) throw new Error(res.status);
      await c.put(u, res);
    } catch { failed++; }
    done++;
    st.textContent = `下載中… ${done} / ${imgs.length}`;
  }
  btn.disabled = false;
  st.textContent = failed
    ? `完成 ${done - failed} / ${imgs.length}，有 ${failed} 張失敗，稍後可再試一次。`
    : `完成，${imgs.length} 張圖已存到裝置上，離線也看得到了。`;
  toast('圖檔下載完成');
}

function clearWrong() {
  if (!confirm('確定要清除所有錯題紀錄嗎？此動作無法復原。')) return;
  store.clearWrong(); renderList('wrong'); refreshCounts(); toast('已清除');
}

function wipeAll() {
  if (!confirm('這會刪除這台裝置上的所有紀錄（錯題、書籤、筆記、進度），無法復原。確定嗎？')) return;
  store.wipe(); refreshCounts(); renderResume(); applyTheme(); applyFont(); toast('已清除所有紀錄');
}

/* ── 啟動 ── */
(async function boot() {
  applyTheme();
  applyFont();
  try {
    await loadTaxonomy();
    await loadAll();
  } catch (e) {
    document.querySelector('main').innerHTML =
      `<div class="empty"><div class="big">·</div>題庫載入失敗。<br>${esc(e.message)}<br><br>
       若你是用檔案總管直接開啟 index.html，請改用本機伺服器或線上網址開啟。</div>`;
    return;
  }
  buildPickers();
  updateCount();
  refreshCounts();
  renderResume();
  if (store.pref('shuffle')) document.getElementById('chip-order').textContent = '隨機出題';

  const verified = allQuestions().filter(q => q.verified).length;
  document.getElementById('build-info').textContent =
    `共 ${allQuestions().length} 題，其中 ${verified} 題與學會公告答案卡逐題核對過`;

  const h = location.hash.slice(1);
  if (h && document.getElementById('s-' + h) && !['quiz', 'result', 'cat'].includes(h)) go(h);

  if ('serviceWorker' in navigator && location.protocol !== 'file:') {
    navigator.serviceWorker.register('sw.js').catch(() => {});
    ensureOfflineCore();   // 不 await：背景補齊，不擋使用
  }
})();
