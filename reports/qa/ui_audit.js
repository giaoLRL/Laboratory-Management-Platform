/**
 * 全站界面可视化量化：滚动深度 / 主内容起点 / 卡片与分区数 / 分页 / 首屏信息密度
 * 输出每页一行紧凑 JSON，便于汇总成分析表。
 */
const PW = 'C:/Users/PC/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8001';
const { chromium } = require(PW);

const PAGES = [
  ['仪表板', '/plugins/lab-manager/'],
  ['硬件列表', '/plugins/lab-manager/hardware/'],
  ['硬件详情', '/plugins/lab-manager/hardware/3/'],
  ['任务列表', '/plugins/lab-manager/tasks/'],
  ['任务详情', '/plugins/lab-manager/tasks/1/'],
  ['我的任务', '/plugins/lab-manager/my-tasks/'],
  ['借出列表', '/plugins/lab-manager/borrow-records/'],
  ['项目列表', '/plugins/lab-manager/projects/'],
  ['工具管理', '/plugins/lab-manager/agent-tools/'],
  ['打卡记录', '/plugins/lab-manager/checkins/'],
  ['打卡详情', '/plugins/lab-manager/checkins/3/'],
  ['浏览记录', '/plugins/lab-manager/member-open-records/'],
  ['成员列表', '/plugins/lab-manager/members/'],
  ['成员详情', '/plugins/lab-manager/members/3/'],
  ['任务日历', '/plugins/lab-manager/calendar/'],
  ['通知中心', '/plugins/lab-manager/notifications/'],
  ['数据导出', '/plugins/lab-manager/export/'],
  ['智能体控制台', '/plugins/lab-manager/agent/'],
  ['签到打卡', '/plugins/lab-manager/checkins/new/'],
  ['任务看板', '/plugins/lab-manager/tasks/board/'],
  ['指挥舱', '/plugins/lab-manager/mission-control/'],
  ['设计系统', '/plugins/lab-manager/design-system/'],
];

const MEASURE = () => {
  const de = document.documentElement;
  const vh = window.innerHeight;
  const cards = [...document.querySelectorAll('.card')];
  const visibleCards = cards.filter(c => c.getBoundingClientRect().height > 0);
  const rows = document.querySelectorAll('table tbody tr').length;
  const pag = document.querySelector('.pagination, ul.pagination, .paginator, nav[aria-label*="page" i]');
  const pagerText = pag ? (pag.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60) : '';
  const pageSizeSel = document.querySelector('.per-page, select[name="per_page"], .pagesize, .page-size');
  // 主内容起点：第一个真实数据区域（表格或主要卡片）的顶部相对视口的位置
  const mainTable = document.querySelector('table');
  const firstCardAfterHeader = cards.find(c => c.querySelector('table, .list-group, form'));
  const anchor = mainTable || firstCardAfterHeader;
  const anchorTop = anchor ? Math.round(anchor.getBoundingClientRect().top) : null;
  const headers = [...document.querySelectorAll('h1, h2, .card-header')].filter(h => (h.textContent || '').trim()).length;
  const tabs = document.querySelectorAll('.nav-tabs .nav-link').length;
  const notices = document.querySelectorAll('.alert, .toast').length;
  const sumCardHeights = visibleCards.reduce((a, c) => a + c.getBoundingClientRect().height, 0);
  return {
    scrollH: de.scrollHeight,
    vh,
    screens: +(de.scrollHeight / vh).toFixed(1),
    cards: visibleCards.length,
    cardHSum: Math.round(sumCardHeights),
    rows,
    paginated: !!pag,
    pagerText,
    pageSizeControl: !!pageSizeSel,
    anchorTop,
    anchorPctIntoPage: anchorTop !== null ? +(anchorTop / vh).toFixed(2) : null,
    headers,
    tabs,
    horizOverflow: de.scrollWidth > de.clientWidth + 1,
    title: document.title.slice(0, 40),
  };
};

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const results = { desktop: [], mobile: [] };

  // HTTP 登录拿 cookie，避免登录页干扰
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

  for (const [vpName, vp, isMobile] of [['desktop', { width: 1440, height: 900 }, false],
                                        ['mobile', { width: 390, height: 844 }, true]]) {
    const ctx = await browser.newContext({ viewport: vp, isMobile, hasTouch: isMobile });
    await ctx.addCookies(cookies);
    const page = await ctx.newPage();
    for (const [name, path] of PAGES) {
      const r = await page.goto(BASE + path, { waitUntil: 'domcontentloaded', timeout: 40000 }).catch(() => null);
      await page.waitForTimeout(900);
      const m = await page.evaluate(MEASURE);
      results[vpName].push({ name, path, status: r ? r.status() : 'ERR', ...m });
    }
    await ctx.close();
  }

  require('fs').writeFileSync('C:/Users/PC/Documents/实验室/reports/qa/ui_metrics.json', JSON.stringify(results, null, 1), 'utf8');

  console.log('=== 桌面 1440x900（screens=滚动屏数, anchor=主内容起点占首屏比例, rows=表格行数）===');
  for (const x of results.desktop) {
    console.log(`${String(x.status).padEnd(4)} ${x.name.padEnd(6)} screens=${String(x.screens).padEnd(4)} 卡片=${String(x.cards).padEnd(3)} 卡片总高=${String(x.cardHSum).padEnd(5)} 行=${String(x.rows).padEnd(4)} 分页=${x.paginated ? 'Y' : 'N'} 页大小控件=${x.pageSizeControl ? 'Y' : 'N'} 主内容起点=${x.anchorTop}(${x.anchorPctIntoPage}屏) 标题=${x.headers} 标签页=${x.tabs}`);
  }
  console.log('\n=== 移动 390x844 ===');
  for (const x of results.mobile) {
    console.log(`${String(x.status).padEnd(4)} ${x.name.padEnd(6)} screens=${String(x.screens).padEnd(4)} 卡片=${String(x.cards).padEnd(3)} 行=${String(x.rows).padEnd(4)} 横向溢出=${x.horizOverflow ? 'Y' : 'N'} 主内容起点=${x.anchorTop}`);
  }
  const d = results.desktop;
  const noPag = d.filter(x => x.rows > 0 && !x.paginated);
  console.log('\n有数据但无分页的页面:', noPag.map(x => `${x.name}(${x.rows}行)`).join('、') || '（无）');
  console.log('滚动超过 3 屏的页面:', d.filter(x => x.screens > 3).map(x => `${x.name}(${x.screens}屏)`).join('、') || '（无）');
  console.log('主内容起点超过 1 屏的页面:', d.filter(x => x.anchorPctIntoPage > 1).map(x => `${x.name}(${x.anchorPctIntoPage})`).join('、') || '（无）');
  await browser.close();
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 300)); process.exit(1); });
