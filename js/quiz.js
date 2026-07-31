/* quiz.js — 答題流程 */

const Q = {
  list: [],        // 本次要練的題目
  i: 0,
  picks: {},       // source -> 'A'
  mode: 'practice',
  label: '',       // 顯示用標題
  origin: 'years'  // 完成後返回哪一頁
};

function startQuiz(list, { mode = 'practice', label = '', origin = 'years', shuffle = false, restore = null } = {}) {
  if (!list.length) { toast('沒有符合條件的題目'); return; }
  Q.list = shuffle ? shuffled(list) : list.slice();
  Q.i = 0; Q.picks = {}; Q.mode = mode; Q.label = label; Q.origin = origin;
  if (restore) {
    Q.picks = restore.picks || {};
    Q.i = Math.min(restore.i || 0, Q.list.length - 1);
    if (restore.order) {
      const map = new Map(list.map(q => [q.source, q]));
      const rebuilt = restore.order.map(s => map.get(s)).filter(Boolean);
      if (rebuilt.length === list.length) Q.list = rebuilt;
    }
  }
  go('quiz');
  renderQuiz();
}

function shuffled(a) {
  const r = a.slice();
  for (let i = r.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [r[i], r[j]] = [r[j], r[i]];
  }
  return r;
}

function curQ() { return Q.list[Q.i]; }

function pick(letter) {
  const q = curQ();
  if (Q.mode === 'practice' && Q.picks[q.source]) return;  // 練習模式作答後鎖定
  Q.picks[q.source] = letter;

  if (Q.mode === 'practice') {
    if (isCorrect(q, letter)) store.markRight(q.source);
    else store.markWrong(q.source, letter);
  }
  saveProgress();
  renderQuiz();
}

function move(d) {
  const n = Q.i + d;
  if (n < 0 || n >= Q.list.length) return;
  Q.i = n; saveProgress(); renderQuiz();
  document.querySelector('main').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function jump(i) { Q.i = i; saveProgress(); renderQuiz(); }

function finish() {
  const unanswered = Q.list.filter(q => !Q.picks[q.source] && !isFree(q)).length;
  if (unanswered && !confirm(`還有 ${unanswered} 題未作答，確定要結束並計分嗎？`)) return;

  if (Q.mode === 'exam') {   // 考試模式收尾才批次記錄
    for (const q of Q.list) {
      const p = Q.picks[q.source];
      if (isFree(q) || (p && isCorrect(q, p))) store.markRight(q.source);
      else if (p) store.markWrong(q.source, p);
    }
  }
  store.clearProgress();
  renderResult();
  go('result');
}

function saveProgress() {
  if (Q.origin === 'review') return;   // 錯題／書籤複習不留續作紀錄
  store.setProgress({
    label: Q.label, mode: Q.mode, origin: Q.origin,
    order: Q.list.map(q => q.source),
    i: Q.i, picks: Q.picks, at: Date.now()
  });
}

function scoreOf() {
  let ok = 0, no = 0, blank = 0;
  for (const q of Q.list) {
    const p = Q.picks[q.source];
    if (isFree(q)) ok++;
    else if (!p) blank++;
    else if (isCorrect(q, p)) ok++;
    else no++;
  }
  return { ok, no, blank, total: Q.list.length, pct: Math.round(ok / Q.list.length * 100) };
}
