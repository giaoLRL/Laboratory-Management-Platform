/** 导出任务列表页脚 HTML（确认每页下拉的真实标记与文案） */
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
  await page.goto(BASE + '/plugins/lab-manager/tasks/', { waitUntil: 'load' });
  await page.waitForTimeout(500);
  const out = await page.evaluate(() => {
    const nav = document.querySelector('nav[aria-label]');
    const dd = nav && nav.closest('.dropdown');
    const items = [...document.querySelectorAll('.dropdown-menu .dropdown-item, .dropdown-menu a')]
      .map(a => ({ href: a.getAttribute('href'), hx: a.getAttribute('hx-get'), text: a.textContent.trim() }))
      .filter(o => /per_page/.test((o.href || '') + (o.hx || '')));
    const footer = nav ? nav.parentElement.textContent.replace(/\s+/g, ' ').trim().slice(0, 160) : null;
    return { items, footer, ddHtml: dd ? dd.outerHTML.replace(/\s+/g, ' ').slice(0, 700) : null };
  });
  console.log(JSON.stringify(out, null, 1));
  await b.close();
})();
