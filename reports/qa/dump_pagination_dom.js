/** 抓取打卡记录 / 任务列表页面中所有分页相关的 DOM，确认页大小选项来源 */
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

  for (const url of ['/plugins/lab-manager/checkins/', '/plugins/lab-manager/tasks/', '/plugins/lab-manager/hardware/']) {
    const page = await ctx.newPage();
    await page.goto(BASE + url, { waitUntil: 'load' });
    await page.waitForTimeout(400);
    const out = await page.evaluate(() => {
      const sels = [...document.querySelectorAll('select')].map(s => ({
        name: s.name, cls: s.className, opts: [...s.options].map(o => o.value),
        parent: s.closest('.lm-paginator') ? 'lm-paginator' : (s.closest('.card-footer') ? 'card-footer' : 'other'),
      })).filter(s => s.name === 'per_page' || /per_page|page-size/i.test(s.name + s.cls));
      const paginators = [...document.querySelectorAll('.lm-paginator')].length;
      const perPageLinks = [...document.querySelectorAll('a.dropdown-item')].filter(a => /per_page=/.test(a.getAttribute('href') || '')).map(a => a.getAttribute('href').match(/per_page=(\d+)/)[1]);
      const rowCount = document.querySelectorAll('table.object-list tbody tr, table tbody tr').length;
      const showing = (document.body.textContent.match(/Showing\s+[\d\-]+\s+of\s+\d+/i) || [])[0] || null;
      return { rowCount, paginators, sels, perPageLinks, showing };
    });
    console.log(url, JSON.stringify(out));
    await page.close();
  }
  await b.close();
})();
