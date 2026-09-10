/** 验证列表页默认每页 10 条 + 页大小切换可用 */
const PW = 'C:/Users/PC/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8001';
const { chromium } = require(PW);

const PAGES = [
  ['硬件列表', '/plugins/lab-manager/hardware/'],
  ['全部任务', '/plugins/lab-manager/tasks/'],
  ['借出记录', '/plugins/lab-manager/borrow-records/'],
  ['项目列表', '/plugins/lab-manager/projects/'],
  ['智能体工具', '/plugins/lab-manager/agent-tools/'],
  ['打卡记录', '/plugins/lab-manager/checkins/'],
  ['成员浏览记录', '/plugins/lab-manager/member-open-records/'],
  ['成员列表', '/plugins/lab-manager/members/'],
  ['站内通知', '/plugins/lab-manager/notifications/'],
];

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

  const probe = () => page.evaluate(() => {
    const rows = document.querySelectorAll('table.object-list tbody tr, table tbody tr');
    // 页脚的分页控件：取「当前每页条数」的显示值
    const sel = document.querySelector('.lm-paginator select, #page-size, select[name="per_page"]');
    const active = document.querySelector('.lm-paginator [data-per-page].active, .pagination .page-item.active');
    const opts = sel ? [...sel.options].map(o => o.value || o.textContent.trim()) : null;
    const text = document.querySelector('.lm-paginator') ? document.querySelector('.lm-paginator').textContent.replace(/\s+/g, ' ').trim().slice(0, 90) : null;
    return { rows: rows.length, sel: sel ? sel.value : null, opts, activeText: active ? active.textContent.trim() : null, text };
  });

  for (const [name, url] of PAGES) {
    await page.goto(BASE + url, { waitUntil: 'load' });
    await page.waitForTimeout(450);
    const r = await probe();
    // 默认每页 10 条：行数应 <= 10
    check(`${name} 默认每页 ≤10 条`, r.rows <= 10, `rows=${r.rows} sel=${r.sel} ${r.text ? '| ' + r.text : ''}`);
    if (r.opts) check(`  └ ${name} 页大小选项含 10`, r.opts.some(o => String(o).indexOf('10') === 0), JSON.stringify(r.opts));
  }

  // 显式 per_page 仍可覆盖
  await page.goto(BASE + '/plugins/lab-manager/hardware/?per_page=25', { waitUntil: 'load' });
  await page.waitForTimeout(400);
  const over = await probe();
  check('显式 ?per_page=25 仍生效', over.rows <= 25 && over.rows > 0, `rows=${over.rows} sel=${over.sel}`);

  // 局部导航到列表页也要 10 条
  await page.goto(BASE + '/plugins/lab-manager/', { waitUntil: 'load' });
  await page.waitForTimeout(600);
  await page.click('.navbar-vertical a[href="/plugins/lab-manager/hardware/"]');
  await page.waitForTimeout(800);
  const boosted = await probe();
  check('局部导航后的列表页同样 10 条', boosted.rows <= 10, `rows=${boosted.rows}`);

  check('无 JS 报错', errs.length === 0, errs.slice(0, 2).join(' | '));
  const bad = results.filter(r => !r[1]);
  console.log(`\n总计 ${results.length} 项，通过 ${results.length - bad.length}，失败 ${bad.length}`);
  await b.close();
  process.exit(bad.length ? 1 : 0);
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 200)); process.exit(1); });
