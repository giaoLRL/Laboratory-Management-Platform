/** 翻页时是否保留 per_page（自定义分页器 + 原生分页器），并检查 Tom Select 选项顺序 */
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
  page.on('pageerror', e => errs.push(e.message.slice(0, 100)));
  const results = [];
  const check = (n, ok, d) => { results.push([n, ok]); console.log((ok ? '  PASS ' : '  FAIL ') + n + (d ? '  ' + d : '')); };

  // 1) 自定义分页器：per_page=25 时翻到第 2 页应保留 per_page
  await page.goto(BASE + '/plugins/lab-manager/member-open-records/?per_page=25', { waitUntil: 'load' });
  await page.waitForTimeout(400);
  const href2 = await page.evaluate(() => {
    const a = [...document.querySelectorAll('.lm-paginator .page-link')].find(x => x.textContent.trim() === '2');
    return a ? a.getAttribute('href') : null;
  });
  check('自定义分页器第 2 页链接保留 per_page', !!href2 && /per_page=25/.test(href2), `href=${href2}`);
  await page.goto(BASE + href2, { waitUntil: 'load' });
  await page.waitForTimeout(400);
  const after = await page.evaluate(() => ({
    rows: document.querySelectorAll('table tbody tr').length,
    sel: (document.querySelector('.lm-paginator select[name="per_page"]') || {}).value || null,
    tsControl: (document.querySelector('.lm-paginator .ts-control') || {}).textContent || null,
    page: (location.search.match(/[?&]page=(\d+)/) || [])[1],
    url: location.search,
  }));
  check('第 2 页仍为 25 行/页', after.rows === 25 && after.page === '2' && /per_page=25/.test(after.url),
    JSON.stringify(after));

  // 2) 原生分页器：翻页保留 per_page（htmx 或普通链接）
  await page.goto(BASE + '/plugins/lab-manager/tasks/?per_page=5', { waitUntil: 'load' });
  await page.waitForTimeout(400);
  const nat = await page.evaluate(() => {
    const a = [...document.querySelectorAll('.pagination .page-link, nav[aria-label] a')]
      .find(x => /page=2/.test((x.getAttribute('href') || '') + (x.getAttribute('hx-get') || '')));
    return a ? { href: a.getAttribute('href'), hx: a.getAttribute('hx-get') } : null;
  });
  check('原生分页器第 2 页链接保留 per_page', !!nat && /per_page=5/.test((nat.href || '') + (nat.hx || '')), JSON.stringify(nat));

  // 3) 自定义分页器的 Tom Select 渲染顺序（仅记录）
  await page.goto(BASE + '/plugins/lab-manager/member-open-records/', { waitUntil: 'load' });
  await page.waitForTimeout(600);
  const ts = await page.evaluate(() => {
    const ctl = document.querySelector('.lm-paginator .ts-control');
    const dd = document.querySelector('.lm-paginator .ts-dropdown');
    return { control: ctl ? ctl.textContent.trim() : null, order: dd ? [...dd.querySelectorAll('[data-value]')].map(o => o.getAttribute('data-value')) : null };
  });
  console.log('  INFO Tom Select:', JSON.stringify(ts));

  check('无 JS 报错', errs.length === 0, errs.slice(0, 2).join(' | '));
  const bad = results.filter(r => !r[1]);
  console.log(`\n总计 ${results.length} 项，通过 ${results.length - bad.length}，失败 ${bad.length}`);
  await b.close();
  process.exit(bad.length ? 1 : 0);
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 200)); process.exit(1); });
