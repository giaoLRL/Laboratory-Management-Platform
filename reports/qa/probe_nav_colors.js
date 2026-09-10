/** 探测侧栏当前项在两种主题下的实际配色 */
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
  await page.goto(BASE + '/plugins/lab-manager/checkins/', { waitUntil: 'load' });
  await page.waitForTimeout(800);
  for (const t of ['light', 'dark']) {
    await page.evaluate(x => document.documentElement.setAttribute('data-bs-theme', x), t);
    await page.waitForTimeout(200);
    const out = await page.evaluate(() => {
      const nav = document.querySelector('.navbar-vertical');
      const row = nav.querySelector('.dropdown-item.active');
      const a = row && row.querySelector('a[href]:not(.btn)');
      const cs = row ? getComputedStyle(row) : null;
      const root = getComputedStyle(document.documentElement);
      const linkCs = a ? getComputedStyle(a) : null;
      return {
        theme: document.documentElement.getAttribute('data-bs-theme'),
        navActiveBgVar: root.getPropertyValue('--tp-nav-active-bg').trim(),
        navAccentVar: root.getPropertyValue('--tp-nav-accent').trim(),
        rowBg: cs && cs.backgroundColor,
        rowShadow: cs && cs.boxShadow,
        navBg: getComputedStyle(nav).backgroundColor,
        linkColor: linkCs && linkCs.color,
        marker: a ? getComputedStyle(a, '::before').content : null,
      };
    });
    console.log(JSON.stringify(out));
  }
  await b.close();
})();
