/** 验证侧栏高亮随局部导航正确变化 */
const PW = 'C:/Users/PC/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8001';
const { chromium } = require(PW);

const ACTIVE = () => {
  const nav = document.querySelector('.navbar-vertical');
  const act = [...nav.querySelectorAll('.active')].map(el => {
    const a = el.tagName === 'A' ? el : el.querySelector('a[href]');
    return (a ? a.getAttribute('href') : el.className);
  });
  return act;
};

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
  await page.waitForTimeout(800);
  const home = await page.evaluate(ACTIVE);
  check('首页加载时高亮指向 /plugins/lab-manager/', home.some(h => h === '/plugins/lab-manager/'), JSON.stringify(home));

  const hops = [
    ['/plugins/lab-manager/hardware/', '/plugins/lab-manager/hardware/'],
    ['/plugins/lab-manager/tasks/', '/plugins/lab-manager/tasks/'],
    ['/plugins/lab-manager/mission-control/', '/plugins/lab-manager/mission-control/'],
    ['/plugins/lab-manager/checkins/', '/plugins/lab-manager/checkins/'],
    ['/plugins/lab-manager/design-system/', '/plugins/lab-manager/design-system/'],
    ['/plugins/lab-manager/hardware/add/', '/plugins/lab-manager/hardware/'],
  ];
  for (const [href, expect] of hops) {
    await page.evaluate(h => {
      const a = [...document.querySelectorAll('.navbar-vertical a')].find(x => x.getAttribute('href') === h);
      if (a) a.click();
    }, href);
    await page.waitForFunction(h => location.pathname.indexOf(h.replace('/plugins/lab-manager', '')) !== -1, href, { timeout: 10000 }).catch(() => {});
    await page.waitForTimeout(600);
    // 正确的不变量：高亮项 = 与当前 URL 最长前缀匹配的侧栏链接
    const inv = await page.evaluate(() => {
      const path = location.pathname.replace(/\/+$/, '');
      const nav = document.querySelector('.navbar-vertical');
      const navLinks = [...nav.querySelectorAll('a[href^="/"]')]
        .filter(a => !a.closest('.btn-group') && !a.classList.contains('btn'));
      const links = navLinks
        .map(a => a.getAttribute('href').split('?')[0].replace(/\/+$/, ''))
        .filter(h => h && h !== '/plugins/lab-manager');
      const expect = links.filter(h => path === h || path.indexOf(h + '/') === 0)
        .sort((x, y) => y.length - x.length)[0] || '/plugins/lab-manager/';
      // 高亮元素可能是一个包裹了多个链接的 .dropdown-item，因此检查"该元素内是否包含目标链接"
      const actEls = [...nav.querySelectorAll('.active')];
      const act = actEls.map(el => (el.tagName === 'A' ? el.getAttribute('href') : (el.querySelector('a[href]') || {}).getAttribute
        ? el.querySelector('a[href]').getAttribute('href') : null)).filter(Boolean);
      const contains = actEls.some(el => {
        const inEl = el.tagName === 'A' ? [el] : [...el.querySelectorAll('a[href]')];
        return inEl.some(a => (a.getAttribute('href') || '').split('?')[0].replace(/\/+$/, '') === expect.replace(/\/+$/, ''));
      });
      // 精确项：aria-current 必须落在与 expect 完全一致的链接上
      const cur = nav.querySelector('a[aria-current="page"]');
      const exact = !!cur && cur.getAttribute('href').split('?')[0].replace(/\/+$/, '') === expect.replace(/\/+$/, '');
      return { path, expect, act, ok: contains, exact, cur: cur ? cur.getAttribute('href') : null };
    });
    check(`局部导航到 ${inv.path} 后高亮 = 最长匹配项`, inv.ok, `expect=${inv.expect} act=${JSON.stringify(inv.act)}`);
    check(`  └ aria-current 精确指向当前页`, inv.exact, `cur=${inv.cur} expect=${inv.expect}`);
  }
  check('无 JS 报错', errs.length === 0, errs.slice(0, 2).join(' | '));
  const bad = results.filter(r => !r[1]);
  console.log(`\n总计 ${results.length} 项，通过 ${results.length - bad.length}，失败 ${bad.length}`);
  await b.close();
  process.exit(bad.length ? 1 : 0);
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 200)); process.exit(1); });
