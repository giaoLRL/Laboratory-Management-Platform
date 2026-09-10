/** 关闭 JS 读取服务端渲染的 per_page 选项顺序（排除 Tom Select 干扰） */
const PW = 'C:/Users/PC/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8001';
const { chromium } = require(PW);

(async () => {
  const b = await chromium.launch({ executablePath: CHROME, headless: true });
  const resp = await fetch(BASE + '/login/');
  const csrf = ((await resp.text()).match(/name="csrfmiddlewaretoken" value="([^"]+)"/) || [])[1];
  const c1 = resp.headers.getSetCookie().map(c => c.split('; ')[0]);
  const r2 = await fetch(BASE + '/login/', {
    method: 'POST', redirect: 'manual',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded', Cookie: c1.join('; '), Referer: BASE + '/login/' },
    body: new URLSearchParams({ username: 'admin', password: 'Lab-Manager@2026', csrfmiddlewaretoken: csrf, next: '/plugins/lab-manager/' }),
  });
  const cookies = [...c1, ...r2.headers.getSetCookie().map(c => c.split('; ')[0])];
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, javaScriptEnabled: false });
  await ctx.addCookies(cookies.map(s => { const i = s.indexOf('='); return { name: s.slice(0, i), value: s.slice(i + 1), domain: '127.0.0.1', path: '/' }; }));

  const page = await ctx.newPage();
  await page.goto(BASE + '/plugins/lab-manager/checkins/', { waitUntil: 'load' });
  const raw = await page.evaluate(() => {
    const s = document.querySelector('select[name="per_page"]');
    return { opts: s ? [...s.options].map(o => `${o.value}${o.selected ? '(sel)' : ''}`) : null, outer: s ? s.outerHTML.replace(/\s+/g, ' ') : null };
  });
  console.log('无 JS（服务端顺序）:', JSON.stringify(raw, null, 1));
  await b.close();
})();
