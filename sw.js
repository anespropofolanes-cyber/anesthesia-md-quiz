/* sw.js — 離線快取

   改版流程（三個地方要一起改，否則使用者會拿到新舊混雜的檔案）：
   1. index.html 的 ?v=  →  2. 本檔的 ASSET_V  →  3. 本檔的 VERSION 加一
   VERSION 一改，activate 時舊快取整個清掉，不會留下上一版的殘骸。
   app.js 的 CACHE_NAME 也必須與這裡的 CACHE 一致。 */

const VERSION = 'v18';
const ASSET_V = '20260802d';   // 與 index.html 的 ?v= 一致
const CACHE = `anes-md-${VERSION}`;

const YEARS = [108, 109, 110, 111, 112, 113, 114];
const LEGACY_YEARS = [93, 94, 99, 100, 101, 102, 103, 104, 106, 107];

const CORE = [
  './', './index.html',
  `./css/app.css?v=${ASSET_V}`,
  ...['store', 'data', 'quiz', 'views', 'app'].map(f => `./js/${f}.js?v=${ASSET_V}`),
  './manifest.webmanifest',
  './assets/logo.png',
  './icons/icon-192.png', './icons/icon-512.png', './icons/icon-180.png',
  './data/taxonomy.json',
  ...YEARS.map(y => `./data/questions/${y}_written.json`),
  ...[114, 113, 112, 111, 110, 108].map(y => `./data/oral/${y}_oral.json`),
  './data/oral/108_ultrasound.json'
];

// 舊考題與 AI 解析：抓不到也不該讓安裝失敗（解析檔是分年陸續補上的）
const OPTIONAL = [
  ...LEGACY_YEARS.map(y => `./data/legacy_wip/${y}_legacy.json`),
  ...[...YEARS, ...LEGACY_YEARS].map(y => `./data/explanations/${y}_expl.json`),
  './data/image_manifest.json',
  './data/subtopic_briefs.json'
];

/** 題庫引用的圖檔清單。寫死在這裡遲早會漏，所以改讀 manifest
    （由 tools/build_image_manifest.py 產生）。離線時圖載不到，
    有圖的那 40 題就等於無法作答。 */
async function imageList(c) {
  const res = (await c.match('./data/image_manifest.json')) ||
              (await fetch('./data/image_manifest.json'));
  if (!res || !res.ok) return [];
  return (await res.json()).map(n => `./images/${n}`);
}

/** 抓取並存入快取。cache:'reload' 繞過瀏覽器 HTTP 快取，確保拿到的是本次改版的檔案。 */
async function put(c, url) {
  const res = await fetch(url, { cache: 'reload' });
  if (!res.ok) throw new Error(`${res.status} ${url}`);
  await c.put(url, res);
}

/** 補齊核心資源；已存在的不重抓。 */
async function fillCore() {
  const c = await caches.open(CACHE);
  const missing = [];
  for (const u of CORE) {
    if (!(await c.match(u))) missing.push(u);
  }
  await Promise.all(missing.map(u => put(c, u)));
  await Promise.allSettled(
    OPTIONAL.map(async u => (await c.match(u)) || put(c, u))
  );
  // 圖片放最後：量最大（約 12 MB），但少了它有圖的題目離線就看不了
  const imgs = await imageList(c);
  await Promise.allSettled(
    imgs.map(async u => (await c.match(u)) || put(c, u))
  );
}

self.addEventListener('install', e => {
  e.waitUntil(fillCore().then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)));
    await self.clients.claim();
    // 保險：若快取曾被清空而 sw.js 未改版，install 不會重跑，這裡補回來
    await fillCore().catch(() => {});
  })());
});

// 頁面可主動要求補齊（例如使用者清過瀏覽器資料後）
self.addEventListener('message', e => {
  if (e.data === 'fill-core') e.waitUntil(fillCore().catch(() => {}));
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;   // 字型等外部資源交給瀏覽器自己處理

  // HTML 導覽：網路優先，離線時回退到快取的殼
  if (req.mode === 'navigate') {
    e.respondWith((async () => {
      try {
        const net = await fetch(req);
        const c = await caches.open(CACHE);
        c.put('./index.html', net.clone());
        return net;
      } catch {
        return (await caches.match('./index.html')) || Response.error();
      }
    })());
    return;
  }

  // 其餘（JSON、CSS、JS、圖片）：快取優先，背景更新
  e.respondWith((async () => {
    const cached = await caches.match(req);
    const fetching = fetch(req).then(res => {
      if (res && res.ok) caches.open(CACHE).then(c => c.put(req, res.clone()));
      return res;
    }).catch(() => null);
    return cached || (await fetching) || Response.error();
  })());
});
