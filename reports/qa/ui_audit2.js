/**
 * 第二轮定点测量：
 *  A. 分页能力（用 ?per_page=1 强制多页，检查是否存在 page 链接与页大小控件、是否被静默截断）
 *  B. 仪表板首屏构成（多少卡片在首屏内、主内容被推到多低）
 *  C. 列表页列数与工具栏按钮数（横向信息密度 / 控件冗余）
 */
const PW = 'C:/Users/PC/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8001';
const { chromium } = require(PW);
const results = [];

const LISTS = [
  ['硬件', '/plugins/lab-manager/hardware/', 3],
  ['任务', '/plugins/lab-manager/tasks/', 12],
  ['借出', '/plugins/lab-manager/borrow-records/', 0],
  ['项目', '/plugins/lab-manager/projects/', 1],
  ['工具', '/plugins/lab-manager/agent-tools/', 8],
  ['打卡记录', '/plugins/lab-manager/checkins/', 3],
  ['浏览记录', '/plugins/lab-manager/member-open-records/', 99],
  ['通知', '/plugins/lab-manager/notifications/', 0],
  ['成员', '/plugins/lab-manager/members/', 2],
];

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const resp = await fetch(BASE + '/login/');
  const csrf = ((await resp.text()).match(/name="csrfmiddlewaretoken" value="([^"]+)"/) || [])[1];
  const c1 = resp.headers.getSetCookie().map(c => c.split('; ')[0]);
  const r2 = await fetch(BASE + '/login/', {
    method: 'POST', redirect: 'manual',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded', Cookie: c1.join('; '), Referer: BASE + '/login/' },
    body: new URLSearchParams({ username: 'admin', password: 'Lab-Manager@2026', csrfmiddlewaretoken: csrf, next: '/plugins/lab-manager/' }),
  });
  const cookies = [...c1, ...r2.headers.getSetCookie().map(c => c.split('; ')[0])]
    .map(s => { const i = s.indexOf('='); return { name: s.slice(0, i), value: s.slice(i + 1), domain: '127.0.0.1', path: '/' }; });

  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addCookies(cookies);
  const page = await ctx.newPage();

  console.log('=== A. 分页能力（?per_page=1 强制多页）===');
  console.log('页面        行数  首行/总条数   page链接  页大小控件  分页器文本');
  for (const [name, path, expectedRows] of LISTS) {
    const r = await page.goto(BASE + path + '?per_page=1', { waitUntil: 'domcontentloaded', timeout: 40000 }).catch(() => null);
    await page.waitForTimeout(700);
    const m = await page.evaluate(() => {
      const rows = document.querySelectorAll('table tbody tr').length;
      const pageLinks = [...document.querySelectorAll('a[href*="page="]')].map(a => a.getAttribute('href'));
      const sizeLinks = [...document.querySelectorAll('a[href*="per_page="], select[name="per_page"], .dropdown-menu a')].map(a => (a.textContent || '').trim()).filter(t => /^\d+$/.test(t));
      const total = (document.querySelector('.total-object-count') || {}).textContent || '';
      const pag = document.querySelector('.pagination, .paginator, nav[aria-label*="Page" i]');
      const rowTexts = [...document.querySelectorAll('table tbody')].map(t => (t.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 50));
      const cardLists = document.querySelectorAll('.list-group-item, .member-row, .checkin-row').length;
      return { rows, pageLinks: pageLinks.length, sizeLinks: [...new Set(sizeLinks)].slice(0, 6),
               total: total.replace(/\s+/g, ' ').trim().slice(0, 30),
               pagText: pag ? pag.textContent.replace(/\s+/g, ' ').trim().slice(0, 50) : '', rowTexts, cardLists };
    });
    console.log(`${name.padEnd(8)} ${String(m.rows).padEnd(4)} ${String(m.total).padEnd(12)} ${String(m.pageLinks).padEnd(8)} ${String(m.sizeLinks.join('/')).padEnd(10)} ${m.pagText || '(无)'}`);
    results.push({ name, path, expectedRows, status: r ? r.status() : 'ERR', ...m });
  }

  console.log('\n=== B. 仪表板首屏构成（1440x900）===');
  await page.goto(BASE + '/plugins/lab-manager/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(900);
  const dash = await page.evaluate(() => {
    const vh = window.innerHeight;
    const cards = [...document.querySelectorAll('.card')];
    const inFold = cards.filter(c => { const r = c.getBoundingClientRect(); return r.top < vh && r.bottom > 0; });
    const sections = cards.map(c => {
      const h = c.querySelector('.card-header');
      const r = c.getBoundingClientRect();
      return { title: h ? (h.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 24) : '(无标题)',
               top: Math.round(r.top), h: Math.round(r.height), w: Math.round(r.width) };
    });
    return { total: cards.length, inFold: inFold.length, sections,
             body: { scrollH: document.documentElement.scrollHeight, vh } };
  });
  console.log(`卡片总数=${dash.total} 首屏内=${dash.inFold} 页面高=${dash.body.scrollH}px`);
  console.log('卡片清单（top/高/宽）:');
  for (const s of dash.sections) console.log(`   ${String(s.top).padStart(5)}px  h=${String(s.h).padStart(4)}  w=${String(s.w).padStart(4)}  ${s.title}`);

  console.log('\n=== C. 列表页列数 / 工具栏按钮 / 筛选器数量 ===');
  for (const [name, path] of LISTS) {
    await page.goto(BASE + path, { waitUntil: 'domcontentloaded', timeout: 40000 }).catch(() => {});
    await page.waitForTimeout(600);
    const m = await page.evaluate(() => ({
      cols: document.querySelectorAll('table thead th').length,
      colNames: [...document.querySelectorAll('table thead th')].map(t => (t.textContent || '').trim().slice(0, 10)).filter(Boolean),
      toolbarBtns: document.querySelectorAll('.btn-list > .btn, .btn-list > a.btn, #controls .btn').length,
      filterFields: document.querySelectorAll('#filters-form input, #filters-form select').length,
      tabs: [...document.querySelectorAll('.nav-tabs .nav-link')].map(t => (t.textContent || '').trim().slice(0, 12)),
    }));
    console.log(`${name.padEnd(8)} 列数=${String(m.cols).padEnd(3)} 工具栏按钮=${String(m.toolbarBtns).padEnd(3)} 筛选项=${String(m.filterFields).padEnd(3)} 标签=${m.tabs.join('|')} 列=${m.colNames.join(',')}`);
  }

  require('fs').writeFileSync('C:/Users/PC/Documents/实验室/reports/qa/ui_metrics2.json',
    JSON.stringify({ results, dash }, null, 1), 'utf8');
  await browser.close();
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 300)); process.exit(1); });
