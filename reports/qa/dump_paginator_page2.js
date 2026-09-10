/** 检查第 2 页的自定义分页器是否仍带「每页」选择器 */
const PW = 'C:/Users/PC/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8001';
const { chromium } = require(PW);

(async () => {
  const b = await chromium.launch({ executablePath: CHROME, headless: true });
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const resp = await fetch(BASE + '/login/');
  const csrf = ((await resp.text()).match(/name="csrfmiddlewaretoken" value="([^"]+)"/) || [])[1];
  const c1 = resp.headers.getSetCookie().map(c => c.split('; ')[0]);
  const r2 = await fetch(BASE + '/login/', {
    method: 'POST', redirect: 'manual',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded', Cookie: c1.join('; '), Referer: BASE + '/login/' },
    body: new URLSearchParams({ username: 'admin', password: 'Lab-Manager@2026', csrfmiddlewaretoken: csrf, next: '/plugins/lab-manager/' }),
  });
  await ctx.addCookies([...c1, ...r2.headers.getSetCookie().map(c => c.split('; ')[0])]
    .map(s => { const i = s.indexOf('='); return { name: s.slice(0, i), value: s.slice(i + 1), domain: '127.0.0.1', path: '/' }; }));

  const page = await ctx.newPage();
  for (const url of ['/plugins/lab-manager/member-open-records/?per_page=25', '/plugins/lab-manager/member-open-records/?per_page=25&page=2']) {
    await page.goto(BASE + url, { waitUntil: 'load' });
    await page.waitForTimeout(500);
    const out = await page.evaluate(() => {
      const p = document.querySelector('.lm-paginator');
      return {
        hasPaginator: !!p,
        selects: [...document.querySelectorAll('select')].map(s => s.name + '=' + s.value),
        forms: [...document.querySelectorAll('form')].map(f => (f.getAttribute('action') || '') + ' ' + f.textContent.replace(/\s+/g, ' ').trim().slice(0, 40)).slice(0, 4),
        pagText: p ? p.textContent.replace(/\s+/g, ' ').trim().slice(0, 120) : null,
      };
    });
    console.log(url, JSON.stringify(out));
  }
  await b.close();
})();
