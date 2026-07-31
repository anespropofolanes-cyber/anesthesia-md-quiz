/* views.js — 畫面渲染 */

const esc = s => String(s ?? '').replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const jsonAttr = v => JSON.stringify(v).replace(/"/g, '&quot;');

function yearLabel(q) {
  return isLegacyYear(q.year) ? `${q.year} 年` : `${q.year} 年`;
}

function qTags(q, { showCategory = true } = {}) {
  const t = [];
  if (!q.verified) {
    t.push(q.answer_tier === 'examiner'
      ? '<span class="tag unofficial">答案來自命題端檔案</span>'
      : '<span class="tag disputed">答案未經官方核對</span>');
  }
  if (isFree(q)) t.push('<span class="tag free">送分</span>');
  else if (isMulti(q)) t.push(`<span class="tag multi">兩案皆可 ${esc(q.answer.split('').join('／'))}</span>`);
  if (showCategory && q.category && DB.catName[q.category]) {
    t.push(`<span class="tag topic">${esc(DB.catName[q.category])}</span>`);
  }
  return t.join('');
}

/* ══ 答題畫面 ══ */
function renderQuiz() {
  const q = curQ(), n = Q.list.length, pick0 = Q.picks[q.source];
  const answered = Object.keys(Q.picks).length;
  const reveal = Q.mode === 'practice' && !!pick0;

  document.getElementById('quiz-head').innerHTML = `
    <div class="progress">
      <span>${esc(Q.label)}</span>
      <span class="bar"><i style="width:${(Q.i + 1) / n * 100}%"></i></span>
      <span>${Q.i + 1} / ${n}</span>
    </div>
    ${Q.mode === 'exam' ? `<div class="dots">${Q.list.map((x, i) =>
      `<button class="dot ${Q.picks[x.source] ? 'done' : ''} ${i === Q.i ? 'cur' : ''}"
        onclick="jump(${i})" aria-label="第 ${i + 1} 題">${i + 1}</button>`).join('')}</div>` : ''}`;

  const opts = optionLetters(q).map(L => {
    let cls = '';
    if (reveal) {
      if (!isFree(q) && q.answer.includes(L)) cls = 'correct';
      else if (pick0 === L) cls = 'wrong';
    } else if (pick0 === L) cls = 'picked';
    return `<li><button class="opt ${cls}" onclick="pick('${L}')" ${reveal ? 'disabled' : ''}>
      <span class="L">${L}</span><span>${optionBody(q, L)}</span></button></li>`;
  }).join('');

  let after = '';
  if (reveal) {
    const ok = isCorrect(q, pick0);
    const v = isFree(q)
      ? '<div class="verdict free">本題送分，全體給分</div>'
      : `<div class="verdict ${ok ? 'ok' : 'no'}">${ok ? '答對了' : `答錯了　正解 ${esc(answerText(q))}`}</div>`;
    after = v + sourceHTML(q);
  }

  document.getElementById('quiz-body').innerHTML = `
    <div class="qcard">
      <div class="qhead">
        <span class="qno">${yearLabel(q)} Q${q.id}</span>
        ${qTags(q)}
        <button class="iconbtn ${store.isMarked(q.source) ? 'on' : ''}" onclick="toggleMark('${q.source}')"
          title="書籤" aria-label="加入書籤">★</button>
      </div>
      <div class="stem">${esc(q.question)}</div>
      ${figHTML(q)}
      <ul class="opts">${opts}</ul>
      ${after}
      ${noteHTML(q)}
    </div>`;

  document.getElementById('btn-prev').disabled = Q.i === 0;
  document.getElementById('btn-next').disabled = Q.i === n - 1;
  document.getElementById('btn-finish').textContent =
    Q.mode === 'exam' ? `完成作答並計分（已答 ${answered}／${n}）` : '結束並看成績';
}

/** 有幾題的選項本身就是圖（波形判讀），這種選項沒有文字。 */
function optionBody(q, L) {
  const img = (q.option_images || {})[L];
  const text = esc(q.options[L] || '');
  if (!img) return text;
  return `${text}<img class="optimg" src="images/${esc(img)}" alt="選項 ${L} 的圖"
    loading="lazy" onclick="event.stopPropagation();openLightbox(this.src)">`;
}

function figHTML(q) {
  const imgs = q.images || [];
  if (!imgs.length) return '';
  return imgs.map(src => `<div class="fig">
    <img src="images/${esc(src)}" alt="題目附圖" loading="lazy"
      onclick="openLightbox(this.src)" onerror="this.parentNode.style.display='none'">
  </div>`).join('');
}

/** 這個題庫沒有解析，取而代之顯示答案的來源與出處，讓讀者自己查得下去。 */
function sourceHTML(q) {
  const rows = [];
  if (q.answer_note) rows.push(`<div class="revnote">${esc(q.answer_note)}</div>`);
  if (q.reference) rows.push(`<div>教科書出處：${esc(q.reference)}</div>`);
  if (q.category && DB.catName[q.category]) {
    rows.push(`<div>學會分類：${esc(q.category)} ${esc(DB.catName[q.category])}</div>`);
  }
  if (q.verified) {
    rows.push('<div>答案來源：台灣麻醉醫學會公告之答案卡，已逐題核對。</div>');
  } else {
    rows.push(`<div>答案來源：${esc(q.answer_source || '考卷檔案內附')}。</div>`);
    rows.push(q.answer_tier === 'examiner'
      ? '<div>這一年沒有學會的公開公告可核對，但檔案帶有命題端才會有的出處與難易度標記。</div>'
      : '<div><strong>這一年沒有學會的公開公告可核對，請自行查證。</strong></div>');
  }
  return `<div class="explain"><span class="h">答案出處</span>${rows.join('')}</div>`;
}

function noteHTML(q) {
  return `<div class="noteblk">
    <div class="lbl">我的筆記 <span class="saved" id="saved-${esc(q.source)}">已儲存</span></div>
    <textarea placeholder="寫下你自己的理解、記憶法或補充…"
      oninput="onNote('${q.source}', this.value)">${esc(store.getNote(q.source))}</textarea>
  </div>`;
}

let noteTimer = null;
function onNote(src, val) {
  store.setNote(src, val);
  clearTimeout(noteTimer);
  const el = document.getElementById('saved-' + src);
  if (el) { el.classList.add('show'); noteTimer = setTimeout(() => el.classList.remove('show'), 1400); }
  refreshCounts();
}

/* ══ 結果 ══ */
function renderResult() {
  const s = scoreOf();
  const wrongs = Q.list.filter(q => { const p = Q.picks[q.source]; return p && !isCorrect(q, p); });
  const blanks = Q.list.filter(q => !Q.picks[q.source] && !isFree(q));
  const pass = s.pct >= 60;

  document.getElementById('result-body').innerHTML = `
    <h1 class="page">${pass ? '完成，表現不錯' : '完成，還有進步空間'}</h1>
    <p class="lede">${esc(Q.label)}　甄審筆試及格標準為 60 分</p>
    <div class="card">
      <div class="score">
        <div class="ring" style="--pct:${s.pct}"><div class="v"><b>${s.pct}%</b><s>正確率</s></div></div>
        <div class="stats">
          <div class="stat ok"><b>${s.ok}</b><s>答對</s></div>
          <div class="stat no"><b>${s.no}</b><s>答錯</s></div>
          <div class="stat"><b>${s.blank}</b><s>未作答</s></div>
        </div>
      </div>
      <div class="btnrow">
        <button class="btn primary" onclick="go('${Q.origin}')">回上一頁</button>
        ${wrongs.length ? `<button class="btn" onclick="practiceSources(${jsonAttr(wrongs.map(q => q.source))}, '本次錯題複習')">複習本次錯題（${wrongs.length}）</button>` : ''}
        <button class="btn" onclick="startQuiz(Q.list,{mode:Q.mode,label:Q.label,origin:Q.origin})">再做一次</button>
      </div>
    </div>
    ${wrongs.length || blanks.length ? `
      <div class="sect-label">逐題檢討</div>
      <div class="list">${[...wrongs, ...blanks].map(q => reviewItem(q, Q.picks[q.source])).join('')}</div>` : ''}`;
}

function reviewItem(q, my) {
  return `<div class="item">
    <div class="top"><strong>${yearLabel(q)} Q${q.id}</strong>${qTags(q)}</div>
    <div class="q">${esc(q.question)}</div>
    ${figHTML(q)}
    <div class="ans">你的答案：<strong>${my ? `${my}　${esc(q.options[my] || '')}` : '未作答'}</strong><br>
      正解：<strong>${esc(answerText(q))}</strong>${
        isFree(q) ? '' : `　${esc(q.options[q.answer[0]] || '')}`}</div>
    ${sourceHTML(q)}
  </div>`;
}

/** 沒有官方公告的年份，依答案來源分兩級標示。 */
function legacyTag(year) {
  const p = DB.papers[Number(year)];
  const tier = p && p.questions[0] && p.questions[0].answer_tier;
  return tier === 'examiner'
    ? '<span class="tag unofficial">命題端檔案</span>'
    : '<span class="tag disputed">未經官方核對</span>';
}

/* ══ 分類總覽 ══ */
function renderCategories() {
  const el = document.getElementById('cat-list');
  const secs = DB.taxonomy.sections.map(sec => {
    const cards = DB.taxonomy.categories.filter(c => c.section === sec.id).map(c => {
      const qs = byCategory(c.code);
      const done = qs.filter(q => store.s.right[q.source]).length;
      const pct = qs.length ? Math.round(done / qs.length * 100) : 0;
      return `<button class="topic" onclick="openCategory('${c.code}')" ${qs.length ? '' : 'disabled style="opacity:.45"'}>
        <span class="t">${esc(c.code)}　${esc(c.name)}</span>
        <span class="s">${esc(c.note || '')}</span>
        <span class="meta"><span>${qs.length} 題</span>
          <span class="bar"><i style="width:${pct}%"></i></span><span>${pct}%</span></span>
      </button>`;
    }).join('');
    return `<div class="sect-label">${esc(sec.name)}　${esc(sec.note)}</div><div class="topics">${cards}</div>`;
  }).join('');
  el.innerHTML = secs;
}

function openCategory(code) {
  go('cat');
  const c = DB.taxonomy.categories.find(x => x.code === code);
  const qs = byCategory(code);
  const byYear = {};
  for (const q of qs) (byYear[q.year] ||= []).push(q);

  document.getElementById('cat-detail').innerHTML = `
    <h1 class="page">${esc(c.code)}　${esc(c.name)}</h1>
    <p class="lede">共 ${qs.length} 題${c.note ? `。${esc(c.note)}` : ''}</p>
    <div class="btnrow" style="margin-bottom:18px">
      <button class="btn primary" onclick="practiceSources(${jsonAttr(qs.map(q => q.source))}, '${esc(c.name)}', 'cat', true)">
        練習全部 ${qs.length} 題（隨機順序）</button>
    </div>
    <div class="sect-label">依年份</div>
    <div class="list">${Object.keys(byYear).sort((a, b) => b - a).map(y => {
      const list = byYear[y];
      const done = list.filter(q => store.s.right[q.source]).length;
      return `<button class="item" onclick="practiceSources(${jsonAttr(list.map(q => q.source))}, '${esc(c.name)}／${y} 年', 'cat', true)">
        <div class="top"><strong>${y} 年</strong>
          <span class="tag">${list.length} 題</span>
          ${isLegacyYear(y) ? legacyTag(y) : ''}
          ${done ? `<span class="tag topic">已答對 ${done}</span>` : ''}</div>
      </button>`;
    }).join('')}</div>`;
}

/* ══ 清單頁 ══ */
function renderList(kind) {
  const map = { wrong: 'wrong-list', mark: 'mark-list', note: 'note-list' }[kind];
  const el = document.getElementById(map);
  const table = kind === 'wrong' ? store.s.wrong : kind === 'mark' ? store.s.marks : store.s.notes;
  const keys = Object.keys(table);
  // 口試筆記的鍵不在筆試索引裡，要另外查，否則會整批消失
  const oralKeys = kind === 'note' ? keys.filter(isOralNoteKey) : [];
  const items = keys.filter(k => !isOralNoteKey(k)).map(s => DB.index[s]).filter(Boolean);
  if (!items.length && !oralKeys.length) {
    const msg = { wrong: '還沒有錯題。開始練習後答錯的題目會自動收進來。',
                  mark: '還沒有書籤。在答題畫面點右上角的星號即可標記。',
                  note: '還沒有筆記。在任何一題下方的筆記欄寫下想法即可。' }[kind];
    el.innerHTML = `<div class="empty"><div class="big">·</div>${msg}</div>`;
    return;
  }
  items.sort((a, b) => (table[b.source].at || 0) - (table[a.source].at || 0));
  oralKeys.sort((a, b) => (table[b].at || 0) - (table[a].at || 0));
  el.innerHTML = `<div class="list">${oralKeys.map(oralNoteItem).join('')}${items.map(q => {
    const extra = kind === 'wrong'
      ? `<div class="ans">你答過：<strong>${esc(store.s.wrong[q.source].my || '—')}</strong>　正解：<strong>${esc(answerText(q))}</strong>　答錯 ${store.s.wrong[q.source].n} 次</div>`
      : kind === 'note'
        ? `<div class="explain" style="margin-top:10px"><span class="h">我的筆記</span>${esc(store.getNote(q.source))}</div>`
        : `<div class="ans">正解：<strong>${esc(answerText(q))}</strong></div>`;
    return `<div class="item">
      <div class="top"><strong>${yearLabel(q)} Q${q.id}</strong>${qTags(q)}
        <button class="btn sm" style="margin-left:auto" onclick="practiceSources(['${q.source}'],'單題複習')">練這題</button></div>
      <div class="q">${esc(q.question)}</div>${extra}
      <div class="btnrow" style="margin-top:10px">
        ${kind === 'wrong' ? `<button class="btn sm" onclick="store.clearWrong('${q.source}');renderList('wrong');refreshCounts()">從錯題本移除</button>` : ''}
        ${kind === 'mark' ? `<button class="btn sm" onclick="toggleMark('${q.source}');renderList('mark')">取消書籤</button>` : ''}
      </div>
    </div>`;
  }).join('')}</div>`;
}

/** 筆記頁裡的口試筆記。索引沒建起來時（還沒載入口試資料）也要看得到內容。 */
function oralNoteItem(key) {
  const hit = (DB.oralIndex || {})[key];
  const [, year, qid, idx] = key.split(':');
  const head = hit ? `${hit.question.year} 年 ${hit.question.title}` : `${year} 年 口試第${qid}題`;
  const title = hit ? hit.sub.title : `子題 ${idx}`;
  return `<div class="item">
    <div class="top"><strong>${esc(head)}</strong>
      <span class="tag topic">口試</span>
      <button class="btn sm" style="margin-left:auto" onclick="go('oral')">前往口試</button></div>
    <div class="q">${esc(title)}</div>
    <div class="explain" style="margin-top:10px"><span class="h">我的答案</span>${esc(store.getNote(key))}</div>
  </div>`;
}

/* ══ 搜尋 ══ */
function doSearch() {
  const kw = document.getElementById('q').value.trim();
  const el = document.getElementById('search-result');
  if (kw.length < 2) { el.innerHTML = `<p class="hint">請輸入至少 2 個字。</p>`; return; }
  const lc = kw.toLowerCase();
  const hits = allQuestions().filter(q =>
    q.question.toLowerCase().includes(lc) ||
    Object.values(q.options).some(o => (o || '').toLowerCase().includes(lc))
  ).sort((a, b) => b.year - a.year || a.id - b.id).slice(0, 60);
  if (!hits.length) { el.innerHTML = `<div class="empty">找不到含「${esc(kw)}」的題目。</div>`; return; }
  const hl = s => esc(s).replace(new RegExp(esc(kw).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'), m => `<mark>${m}</mark>`);
  el.innerHTML = `<p class="hint">找到 ${hits.length} 題${hits.length === 60 ? '（僅顯示前 60 題）' : ''}</p>
    <div class="btnrow" style="margin-bottom:14px">
      <button class="btn sm" onclick="practiceSources(${jsonAttr(hits.map(q => q.source))}, '搜尋：${esc(kw)}')">練習這 ${hits.length} 題</button>
    </div>
    <div class="list">${hits.map(q => `<div class="item">
      <div class="top"><strong>${yearLabel(q)} Q${q.id}</strong>${qTags(q)}
        <button class="btn sm" style="margin-left:auto" onclick="practiceSources(['${q.source}'],'單題練習')">練這題</button></div>
      <div class="q">${hl(q.question)}</div>
      <div class="ans">正解：<strong>${esc(answerText(q))}</strong></div>
    </div>`).join('')}</div>`;
}

/* ══ 口試與超音波 ══
   這兩種是情境演練，不計分也不記錯題。用法是先自己把答案講一遍，
   再展開官方參考答案補漏掉的地方——所以參考答案預設收合。 */

function renderOral() {
  const el = document.getElementById('oral-list');
  const oral = DB.oral || [], us = DB.ultrasound || [];
  if (!oral.length && !us.length) {
    el.innerHTML = '<div class="empty"><div class="big">·</div>口試資料載入失敗。</div>';
    return;
  }

  const byYear = {};
  for (const q of oral) (byYear[q.year] ||= []).push(q);

  el.innerHTML = `
    <div class="sect-label">口試</div>
    ${Object.keys(byYear).sort((a, b) => b - a).map(y => `
      <div class="sect-year">${y} 年</div>
      ${byYear[y].sort((a, b) => a.id - b.id).map(oralCard).join('')}`).join('')}
    ${us.length ? `<div class="sect-label">108 年超音波實作</div>
      ${us.map(usCard).join('')}` : ''}`;
}

function oralCard(q) {
  const total = q.subquestions.reduce((n, s) => n + s.weight, 0);
  return `<div class="card scen">
    <h2>${esc(q.title)}
      ${q.has_reference ? '' : '<span class="tag disputed">學會未公布參考答案</span>'}</h2>
    <div class="scenario">${esc(q.scenario)}</div>
    ${(q.scenario_images || []).map(figTag).join('')}
    <div class="sect-label">子題（配分合計 ${total}%）</div>
    ${q.subquestions.map((s, i) => {
      const hasRef = s.reference || (s.reference_images || []).length;
      return `<details class="sub">
        <summary><span class="w">${s.weight}%</span>${esc(s.title)}</summary>
        ${hasRef ? `
          <div class="ref">${s.reference ? esc(s.reference) : ''}
            ${(s.reference_images || []).map(figTag).join('')}</div>`
          : '<div class="ref none">學會未公布這一子題的參考答案。下面可以寫下你自己整理的版本。</div>'}
        ${oralNote(s.noteKey || oralNoteKey(q, i), hasRef)}
      </details>`;
    }).join('')}
    ${q.reference_text ? `
      <details class="sub">
        <summary><span class="w">解答</span>官方參考答案（未分子題）</summary>
        <div class="ref">${esc(q.reference_text)}</div>
      </details>` : ''}
  </div>`;
}

function usCard(q) {
  return `<div class="card scen">
    <h2>${esc(q.title)}</h2>
    <div class="scenario">${esc(q.task)}</div>
    ${(q.images || []).map(figTag).join('')}
    <details class="sub">
      <summary><span class="w">評分</span>評分方式</summary>
      <div class="ref">${esc(q.grading)}</div>
    </details>
    <details class="sub">
      <summary><span class="w">參考</span>逐項參考答案</summary>
      <div class="ref">${esc(q.criteria)}</div>
    </details>
  </div>`;
}

/** 口試每個子題都給一個作答欄。
    有官方參考答案時是「先寫再對照」，沒有時這裡就是唯一能留下答案的地方。 */
function oralNote(key, hasRef) {
  return `<div class="noteblk oral">
    <div class="lbl">${hasRef ? '我的答案（先自己寫，再對照上面的參考答案）'
                              : '我自己整理的答案'}
      <span class="saved" id="saved-${esc(key)}">已儲存</span></div>
    <textarea placeholder="${hasRef ? '把你會講的重點寫下來，再展開參考答案看漏了什麼…'
                                    : '查了 Miller 或和同事討論後，把結論寫在這裡…'}"
      oninput="onNote('${esc(key)}', this.value)">${esc(store.getNote(key))}</textarea>
  </div>`;
}

function figTag(src) {
  return `<div class="fig"><img src="images/${esc(src)}" alt="附圖" loading="lazy"
    onclick="openLightbox(this.src)" onerror="this.parentNode.style.display='none'"></div>`;
}
