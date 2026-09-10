/** 局部换页后按钮是否重新绑定（密度切换 + 幂等） */
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
  page.on('pageerror', e => errs.push(e.message.slice(0, 120)));
  const results = [];
  const check = (n, ok, d) => { results.push([n, ok]); console.log((ok ? '  PASS ' : '  FAIL ') + n + (d ? '  ' + d : '')); };

  await page.goto(BASE + '/plugins/lab-manager/', { waitUntil: 'load' });
  await page.waitForTimeout(700);
  await Promise.all([
    page.waitForFunction(() => location.pathname.includes('/hardware/'), { timeout: 20000 }).catch(() => {}),
    page.click('.navbar-vertical a[href="/plugins/lab-manager/hardware/"]'),
  ]);
  await page.waitForTimeout(800);

  const before = await page.evaluate(() => document.body.classList.contains('lm-density--compact'));
  await page.click('#page-content button[data-lm-density-toggle]');
  await page.waitForTimeout(250);
  const after = await page.evaluate(() => document.body.classList.contains('lm-density--compact'));
  check('局部换页后密度切换生效', before !== after, `${before} -> ${after}`);

  await page.click('#page-content button[data-lm-density-toggle]');
  await page.waitForTimeout(250);
  const back = await page.evaluate(() => document.body.classList.contains('lm-density--compact'));
  check('再次点击能切回（无重复绑定）', back === before, `${after} -> ${back}`);

  // 局部换页后行点击（data-lm-href）仍可跳转
  await Promise.all([
    page.waitForFunction(() => location.pathname.includes('/checkins/'), { timeout: 20000 }).catch(() => {}),
    page.evaluate(() => {
      const a = [...document.querySelectorAll('.navbar-vertical a')].find(x => x.getAttribute('href') === '/plugins/lab-manager/checkins/');
      if (a) a.click();
    }),
  ]);
  await page.waitForTimeout(900);
  const onCheckins = await page.evaluate(() => location.pathname.includes('/checkins/'));
  check('通过侧栏局部导航到达打卡记录', onCheckins);
  if (onCheckins) {
    const rowOk = await page.evaluate(() => {
      const row = document.querySelector('#page-content tr[data-lm-href]');
      if (!row) return 'no-row';
      row.click();
      return 'clicked';
    });
    await page.waitForTimeout(900);
    const navigated = await page.evaluate(() => location.pathname.includes('/checkins/') && /\d+/.test(location.pathname));
    check('局部换页后行点击可进入详情', rowOk === 'clicked' && navigated, `${rowOk} / ${location}`);
  }

  check('无 JS 报错', errs.length === 0, errs.slice(0, 2).join(' | '));
  const bad = results.filter(r => !r[1]);
  console.log(`\n总计 ${results.length} 项，通过 ${results.length - bad.length}，失败 ${bad.length}`);
  await b.close();
  process.exit(bad.length ? 1 : 0);
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 200)); process.exit(1); });
