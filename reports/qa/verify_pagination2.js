/** 验证 NetBox 原生列表（tasks）的每页下拉与翻页，并截图页脚 */
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

  const rows = () => page.evaluate(() => document.querySelectorAll('table.object-list tbody tr, table tbody tr').length);
  const foot = () => page.evaluate(() => {
    // NetBox 原生分页在 htmx 模式下把 per_page 放在 hx-get 上（href 是 #），两种都要读
    const links = [...document.querySelectorAll('a.dropdown-item')]
      .map(a => ((a.getAttribute('href') || '') + ' ' + (a.getAttribute('hx-get') || '')).match(/per_page=(\d+)/))
      .filter(Boolean).map(m => m[1]);
    const btn = document.querySelector('nav[aria-label] button.dropdown-toggle');
    const txt = (document.querySelector('nav[aria-label]') ? document.querySelector('nav[aria-label]').parentElement.textContent : '').replace(/\s+/g, ' ');
    // 站点为中文，页脚文案是「显示 1-10 共 12」；同时兼容英文
    const m = txt.match(/显示\s+([\d\-]+)\s+共\s+(\d+)/) || txt.match(/Showing\s+([\d\-]+)\s+of\s+(\d+)/i);
    return { perPageLinks: [...new Set(links)], btn: btn ? btn.textContent.trim() : null, showing: m ? m.slice(1) : [], txt };
  });

  await page.goto(BASE + '/plugins/lab-manager/tasks/', { waitUntil: 'load' });
  await page.waitForTimeout(500);
  const f1 = await foot();
  check('任务列表默认 10 行', (await rows()) === 10, `rows=${await rows()}`);
  check('任务列表出现「Per Page」下拉', !!f1.btn, JSON.stringify(f1));
  check('任务列表每页选项含 10', f1.perPageLinks.includes('10'), JSON.stringify(f1.perPageLinks));
  check('任务列表分页统计正确（1-10 / 共 12）', f1.showing[0] === '1-10' && f1.showing[1] === '12', JSON.stringify(f1.showing) + ' | ' + f1.txt);
  await page.evaluate(() => document.querySelector('nav[aria-label] button.dropdown-toggle').scrollIntoView({ block: 'center' }));
  await page.waitForTimeout(200);
  await page.screenshot({ path: 'reports/qa/shots/pagination_tasks_10.png', clip: await page.evaluate(() => { const r = document.querySelector('.card-footer, .table-container') || document.body; const b = r.getBoundingClientRect(); return { x: 240, y: Math.max(0, b.bottom - 160), width: 700, height: 150 }; }) });

  // 切换到每页 25
  await page.goto(BASE + '/plugins/lab-manager/tasks/?per_page=25', { waitUntil: 'load' });
  await page.waitForTimeout(500);
  check('每页 25 时 12 条一页显示完', (await rows()) === 12, `rows=${await rows()}`);

  // 自定义分页器页面截图（成员浏览记录：243 条 → 25 页）
  await page.goto(BASE + '/plugins/lab-manager/member-open-records/', { waitUntil: 'load' });
  await page.waitForTimeout(500);
  const f2 = await foot();
  const custom = await page.evaluate(() => {
    const p = document.querySelector('.lm-paginator');
    return p ? p.textContent.replace(/\s+/g, ' ').trim().slice(0, 80) : null;
  });
  check('浏览记录 10 行/页 + 自定义分页器', (await rows()) === 10 && !!custom, `rows=${await rows()} | ${custom}`);
  await page.locator('.lm-paginator').screenshot({ path: 'reports/qa/shots/pagination_custom_10.png' });

  check('无 JS 报错', errs.length === 0, errs.slice(0, 2).join(' | '));
  const bad = results.filter(r => !r[1]);
  console.log(`\n总计 ${results.length} 项，通过 ${results.length - bad.length}，失败 ${bad.length}`);
  await b.close();
  process.exit(bad.length ? 1 : 0);
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 200)); process.exit(1); });
