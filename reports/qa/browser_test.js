/**
 * 浏览器端实测（Playwright 驱动本机 Chrome）
 * 覆盖：控制台报错、统计卡可见性、历史消息 Markdown 渲染、移动端布局、打卡按钮启用条件
 */
const PW = 'C:/Users/PC/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8001';
const { chromium } = require(PW);

const out = [];
function log(...a) { const s = a.join(' '); out.push(s); console.log(s); }

function attach(page, bag) {
  page.on('console', m => { if (m.type() === 'error') bag.console.push(m.text().slice(0, 200)); });
  page.on('pageerror', e => bag.pageerror.push(String(e.message).slice(0, 200)));
  page.on('response', r => { if (r.status() >= 400) bag.http.push(r.status() + ' ' + r.url().replace(BASE, '')); });
}

async function login(page) {
  await page.goto(BASE + '/login/', { waitUntil: 'domcontentloaded' });
  await page.fill('#id_username', 'admin');
  await page.fill('#id_password', 'Lab-Manager@2026');
  await Promise.all([page.waitForNavigation({ waitUntil: 'domcontentloaded' }), page.click('button[type=submit]')]);
  log('登录后 URL:', page.url());
}

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });

  // ── A. 桌面端逐页巡检 ────────────────────────────────
  log('\n===== A. 桌面端页面巡检（1440x900）=====');
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const bag = { console: [], pageerror: [], http: [] };
  attach(page, bag);
  await login(page);

  const pages = [
    ['首页仪表板', '/plugins/lab-manager/'],
    ['硬件列表', '/plugins/lab-manager/hardware/'],
    ['任务列表', '/plugins/lab-manager/tasks/'],
    ['成员列表', '/plugins/lab-manager/members/'],
    ['打卡记录', '/plugins/lab-manager/checkins/'],
    ['签到页', '/plugins/lab-manager/checkins/new/'],
    ['日历', '/plugins/lab-manager/calendar/'],
    ['智能体控制台', '/plugins/lab-manager/agent/'],
  ];
  for (const [name, path] of pages) {
    const before = bag.console.length + bag.pageerror.length;
    const resp = await page.goto(BASE + path, { waitUntil: 'networkidle', timeout: 45000 }).catch(e => ({ status: () => 'ERR ' + e.message.slice(0, 60) }));
    await page.waitForTimeout(1200);
    const errs = (bag.console.length + bag.pageerror.length) - before;
    log(`  ${String(resp.status()).padEnd(5)} ${name.padEnd(12)} JS错误=${errs}  ${path}`);
  }

  log('\n--- 首页统计卡可见性 ---');
  const cards = await page.goto(BASE + '/plugins/lab-manager/', { waitUntil: 'networkidle' }).then(async () => {
    await page.waitForTimeout(1500);
    return page.evaluate(() => {
      const els = [...document.querySelectorAll('[class*="tp-stat"], .tp-count-up')];
      return els.slice(0, 10).map(e => ({
        cls: e.className.slice(0, 60),
        opacity: getComputedStyle(e).opacity,
        visible: !!(e.offsetWidth || e.offsetHeight),
        text: (e.textContent || '').trim().slice(0, 18),
      }));
    });
  });
  log('  ' + JSON.stringify(cards));

  log('\n--- 智能体控制台：历史消息是否被渲染成 HTML ---');
  await page.goto(BASE + '/plugins/lab-manager/agent/?conversation=66', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  const conv = await page.evaluate(() => {
    const b = [...document.querySelectorAll('.agent-message-bubble.assistant')];
    return {
      count: b.length,
      sampleHtml: (b[0] ? b[0].innerHTML : '').slice(0, 260),
      hasStrong: b.some(x => x.innerHTML.includes('<strong>')),
      hasTable: b.some(x => x.innerHTML.includes('<table')),
      rawMarkdownLeft: b.some(x => (x.textContent || '').includes('**')),
      hasDataRaw: b.some(x => x.hasAttribute('data-raw')),
    };
  });
  log('  ' + JSON.stringify(conv));
  log('  删除会话 JS 目标 URL 常量: ' + await page.evaluate(() => {
    const m = [...document.querySelectorAll('script')].map(s => s.textContent).join('\n').match(/agent-conversation\/[^\n]{0,80}/);
    return m ? m[0] : '(未找到)';
  }));

  log('\n--- 打卡页：未选照片时提交按钮状态 ---');
  await page.goto(BASE + '/plugins/lab-manager/checkins/new/', { waitUntil: 'networkidle' });
  const btn = await page.evaluate(() => {
    const lat = document.querySelector('input[name=latitude]');
    const lng = document.querySelector('input[name=longitude]');
    if (lat && lng) {
      lat.value = '39.9042'; lng.value = '116.4074';
      lat.dispatchEvent(new Event('input', { bubbles: true }));
      lng.dispatchEvent(new Event('input', { bubbles: true }));
    }
    const b = document.getElementById('submit-button');
    const ph = document.querySelector('input[name=photo]');
    return { disabledAfterLatLng: b ? b.disabled : null, photoRequired: ph ? ph.required : null,
             hasTagsField: !!document.querySelector('[name=tags]') };
  });
  log('  ' + JSON.stringify(btn));
  await page.screenshot({ path: 'C:/Users/PC/Documents/实验室/reports/qa/shot-checkin-desktop.png', fullPage: false });

  // ── B. 统计卡：屏蔽 animations.js ─────────────────────
  log('\n===== B. 屏蔽 animations.js 后统计卡是否可见 =====');
  const ctx2 = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx2.route('**/animations.js*', r => r.abort());
  const p2 = await ctx2.newPage();
  await login(p2);
  await p2.goto(BASE + '/plugins/lab-manager/', { waitUntil: 'domcontentloaded' });
  await p2.waitForTimeout(1500);
  const blocked = await p2.evaluate(() => {
    const els = [...document.querySelectorAll('[class*="tp-stat"], .tp-count-up')];
    return els.slice(0, 8).map(e => ({ opacity: getComputedStyle(e).opacity, text: (e.textContent || '').trim().slice(0, 14) }));
  });
  log('  ' + JSON.stringify(blocked));
  await p2.screenshot({ path: 'C:/Users/PC/Documents/实验室/reports/qa/shot-dashboard-nojs.png' });

  // ── C. 移动端 ─────────────────────────────────────────
  log('\n===== C. 移动端（390x844 iPhone 尺寸）=====');
  const ctx3 = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
  const p3 = await ctx3.newPage();
  const bag3 = { console: [], pageerror: [], http: [] };
  attach(p3, bag3);
  await login(p3);

  for (const [name, path] of [['首页', '/plugins/lab-manager/'], ['任务列表', '/plugins/lab-manager/tasks/'],
                              ['硬件列表', '/plugins/lab-manager/hardware/'], ['智能体', '/plugins/lab-manager/agent/']]) {
    await p3.goto(BASE + path, { waitUntil: 'networkidle' });
    await p3.waitForTimeout(1000);
    const m = await p3.evaluate(() => {
      const de = document.documentElement;
      const res = {
        pageScrollW: de.scrollWidth, viewportW: de.clientWidth,
        horizOverflow: de.scrollWidth > de.clientWidth + 1,
        innerH: window.innerHeight,
      };
      const tr = document.querySelector('.table-responsive');
      if (tr) { res.tableScrollW = tr.scrollWidth; res.tableClientW = tr.clientWidth; res.tableScrollable = tr.scrollWidth > tr.clientWidth; }
      const foot = document.querySelector('.agent-panel-footer, .agent-composer, .agent-input-row');
      if (foot) {
        const r = foot.getBoundingClientRect();
        res.footerTop = Math.round(r.top); res.footerBottom = Math.round(r.bottom);
        res.footerInViewport = r.bottom <= window.innerHeight + 1 && r.top >= 0;
      }
      const shell = document.querySelector('.agent-shell');
      if (shell) { const r = shell.getBoundingClientRect(); res.shellHeight = Math.round(r.height); }
      const nav = document.querySelector('.navbar.sticky-top, .navbar');
      if (nav) res.navbarHeight = Math.round(nav.getBoundingClientRect().height);
      return res;
    });
    log(`  ${name}: ${JSON.stringify(m)}`);
  }
  await p3.screenshot({ path: 'C:/Users/PC/Documents/实验室/reports/qa/shot-mobile-agent.png' });
  await p3.goto(BASE + '/plugins/lab-manager/tasks/', { waitUntil: 'networkidle' });
  await p3.screenshot({ path: 'C:/Users/PC/Documents/实验室/reports/qa/shot-mobile-tasks.png' });

  // ── D. 汇总 ───────────────────────────────────────────
  log('\n===== D. 控制台/网络错误汇总 =====');
  log('  console.errors: ' + JSON.stringify([...new Set(bag.console)].slice(0, 12)));
  log('  pageerrors    : ' + JSON.stringify([...new Set(bag.pageerror)].slice(0, 12)));
  log('  http>=400     : ' + JSON.stringify([...new Set(bag.http)].slice(0, 20)));
  log('  移动端 errors : ' + JSON.stringify([...new Set(bag3.console.concat(bag3.pageerror))].slice(0, 10)));
  log('  移动端 http   : ' + JSON.stringify([...new Set(bag3.http)].slice(0, 12)));

  await browser.close();
  require('fs').writeFileSync('C:/Users/PC/Documents/实验室/reports/qa/browser_report.txt', out.join('\n'), 'utf8');
})().catch(e => { console.log('FATAL', e.message); process.exit(1); });
