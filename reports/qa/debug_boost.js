/** 连续多次局部导航是否稳定（定位第三次失败） */
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
  const errs = [];
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 140)); });
  page.on('pageerror', e => errs.push('PAGEERROR ' + e.message.slice(0, 140)));
  await page.goto(BASE + '/plugins/lab-manager/', { waitUntil: 'load' });
  await page.waitForTimeout(700);

  const targets = ['/hardware/', '/tasks/', '/checkins/', '/calendar/', '/members/', '/projects/'];
  for (const t of targets) {
    errs.length = 0;
    const before = await page.evaluate(() => location.pathname);
    await page.evaluate(tt => {
      const a = [...document.querySelectorAll('.navbar-vertical a')].find(x => (x.getAttribute('href') || '').indexOf(tt) !== -1);
      if (a) a.click();
    }, t);
    let ok = false;
    try {
      await page.waitForFunction(tt => location.pathname.indexOf(tt) !== -1, t, { timeout: 6000 });
      ok = true;
    } catch (e) { /* 失败 */ }
    const after = await page.evaluate(() => location.pathname);
    console.log(`${ok ? 'PASS' : 'FAIL'}  → ${t.padEnd(12)} before=${before.padEnd(30)} after=${after.padEnd(30)} errs=${errs.slice(0, 2).join(' | ') || '无'}`);
    await page.waitForTimeout(500);
  }
  await b.close();
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 200)); process.exit(1); });
