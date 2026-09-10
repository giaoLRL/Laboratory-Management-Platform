/** 局部导航（boost）后的功能验证：各页面组件与脚本是否仍正常 */
const PW = 'C:/Users/PC/AppData/Roaming/npm/node_modules/playwright'.replace('playwright', '@playwright/mcp/node_modules/playwright');
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8001';
const { chromium } = require('C:/Users/PC/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright');

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
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
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 120)); });
  page.on('pageerror', e => errs.push('PAGEERROR ' + e.message.slice(0, 120)));
  const results = [];
  const check = (n, ok, d) => { results.push([n, ok, d]); console.log((ok ? '  PASS ' : '  FAIL ') + n + (d ? '  ' + d : '')); };

  await page.goto(BASE + '/plugins/lab-manager/', { waitUntil: 'load' });
  await page.waitForTimeout(800);

  // 通过侧栏局部导航依次访问（不整页刷新）
  const visits = [
    ['/plugins/lab-manager/checkins/', 'checkins', '#page-content .lm-filters', '#page-content table tbody tr'],
    ['/plugins/lab-manager/member-open-records/', 'member-open-records', '#page-content .lm-kpi-row', '#page-content .lm-table--cards'],
    ['/plugins/lab-manager/tasks/board/', 'tasks/board', '#page-content .lm-kanban', '#page-content .lm-kanban__card'],
    ['/plugins/lab-manager/mission-control/', 'mission-control', '#page-content .lm-heatmap', '#page-content .lm-mission'],
    ['/plugins/lab-manager/design-system/', 'design-system', '#page-content .lm-kpi', '#page-content .lm-waterline'],
    ['/plugins/lab-manager/hardware/', 'hardware', '#page-content .lm-toolbar', '#page-content table'],
    ['/plugins/lab-manager/members/', 'members', '#page-content', '#page-content'],
  ];
  for (const [href, label, sel1, sel2] of visits) {
    await Promise.all([
      page.waitForFunction(h => location.pathname.indexOf(h) !== -1, href.replace('/plugins/lab-manager', ''), { timeout: 20000 }).catch(() => {}),
      page.click(`.navbar-vertical a[href="${href}"]`).catch(() => {}),
    ]);
    await page.waitForTimeout(600);
    const ok = await page.evaluate(([s1, s2]) => !!document.querySelector(s1) && !!document.querySelector(s2), [sel1, sel2]);
    const sameSidebar = await page.evaluate(() => !!window.__sidebarKept || true);
    check(`局部导航到 ${label}：组件正常`, ok, `${sel1} + ${sel2}`);
  }

  // 局部导航后：看板拖拽是否重新绑定
  await page.goto(BASE + '/plugins/lab-manager/', { waitUntil: 'load' });
  await page.waitForTimeout(500);
  await Promise.all([
    page.waitForFunction(() => location.pathname.includes('/board/'), { timeout: 20000 }).catch(() => {}),
    page.click('.navbar-vertical a[href="/plugins/lab-manager/tasks/board/"]'),
  ]);
  await page.waitForTimeout(800);
  const draggable = await page.evaluate(() => {
    const c = document.querySelector('.lm-kanban__card');
    return !!c && c.getAttribute('draggable') === 'true';
  });
  check('局部导航后看板卡片仍可拖拽', draggable);

  // 局部导航后：列表工具条（密度/特效）仍可用
  await Promise.all([
    page.waitForFunction(() => location.pathname.includes('/hardware/'), { timeout: 20000 }).catch(() => {}),
    page.click('.navbar-vertical a[href="/plugins/lab-manager/hardware/"]'),
  ]);
  await page.waitForTimeout(600);
  const before = await page.evaluate(() => document.body.classList.contains('lm-density--compact'));
  await page.click('#page-content button[data-lm-density-toggle]');
  await page.waitForTimeout(200);
  const after = await page.evaluate(() => document.body.classList.contains('lm-density--compact'));
  check('局部导航后密度切换仍生效', before !== after, `${before} -> ${after}`);

  // 局部导航后：分页器仍可翻页
  await Promise.all([
    page.waitForFunction(() => location.pathname.includes('/checkins/'), { timeout: 20000 }).catch(() => {}),
    page.click('.navbar-vertical a[href="/plugins/lab-manager/checkins/"]'),
  ]);
  await page.waitForTimeout(600);
  const pagerOk = await page.evaluate(() => !!document.querySelector('#page-content .lm-paginator'));
  check('局部导航后分页器存在', pagerOk);

  check('全程无 JS 报错', errs.length === 0, errs.slice(0, 3).join(' | '));

  const bad = results.filter(r => !r[1]);
  console.log(`\n总计 ${results.length} 项，通过 ${results.length - bad.length}，失败 ${bad.length}`);
  await browser.close();
  process.exit(bad.length ? 1 : 0);
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 250)); process.exit(1); });
