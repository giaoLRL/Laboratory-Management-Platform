/** 移动端专项复测（登录改用 waitForURL） */
const PW = 'C:/Users/PC/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8001';
const { chromium } = require(PW);

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2,
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
  });
  const page = await ctx.newPage();
  const errs = [];
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 150)); });
  page.on('pageerror', e => errs.push('PAGEERROR ' + e.message.slice(0, 150)));

  await page.goto(BASE + '/login/', { waitUntil: 'domcontentloaded' });
  console.log('登录页 title:', await page.title(), '| 表单元素:', await page.$$eval('input', a => a.map(x => x.name + ':' + x.type).join(',')));
  await page.fill('input[name=username]', 'admin');
  await page.fill('input[name=password]', 'Lab-Manager@2026');
  await page.click('button[type=submit], input[type=submit]');
  await page.waitForURL(u => !u.pathname.includes('login'), { timeout: 30000 }).catch(e => console.log('登录跳转失败:', e.message.slice(0, 80)));
  console.log('登录后 URL:', page.url());

  const pages = [['首页', '/plugins/lab-manager/'], ['任务列表', '/plugins/lab-manager/tasks/'],
                 ['硬件列表', '/plugins/lab-manager/hardware/'], ['智能体', '/plugins/lab-manager/agent/'],
                 ['签到页', '/plugins/lab-manager/checkins/new/']];
  for (const [name, path] of pages) {
    const r = await page.goto(BASE + path, { waitUntil: 'domcontentloaded', timeout: 40000 }).catch(e => ({ status: () => 'ERR' }));
    await page.waitForTimeout(1500);
    const m = await page.evaluate(() => {
      const de = document.documentElement;
      const o = { status: 0, pageScrollW: de.scrollWidth, viewportW: de.clientWidth, innerH: window.innerHeight,
                  horizOverflowPage: de.scrollWidth > de.clientWidth + 1 };
      const nav = document.querySelector('.navbar');
      if (nav) o.navbarH = Math.round(nav.getBoundingClientRect().height);
      const tr = document.querySelector('.table-responsive');
      if (tr) { o.tableScrollW = tr.scrollWidth; o.tableClientW = tr.clientWidth; o.tableCanScroll = tr.scrollWidth > tr.clientWidth + 1; }
      const foot = document.querySelector('.agent-panel-footer, .agent-composer, .agent-input-row, #agent-input');
      if (foot) { const b = foot.getBoundingClientRect(); o.footerTop = Math.round(b.top); o.footerBottom = Math.round(b.bottom); o.footerVisible = b.top >= 0 && b.bottom <= window.innerHeight + 1; }
      const shell = document.querySelector('.agent-shell, .agent-container');
      if (shell) { const b = shell.getBoundingClientRect(); o.shellH = Math.round(b.height); o.shellBottom = Math.round(b.bottom); }
      const burger = document.querySelector('.tp-mobile-nav-btn, .navbar-toggler');
      if (burger) { const b = burger.getBoundingClientRect(); o.burger = { top: Math.round(b.top), left: Math.round(b.left), w: Math.round(b.width), h: Math.round(b.height), visible: b.width > 0 && b.height > 0 }; }
      const side = document.querySelector('#sidebar, .sidebar, .tp-sidebar');
      if (side) { const b = side.getBoundingClientRect(); o.sidebar = { w: Math.round(b.width), left: Math.round(b.left), transform: getComputedStyle(side).transform }; }
      return o;
    });
    console.log(`  ${name.padEnd(6)} ${JSON.stringify(m)}`);
    await page.screenshot({ path: `C:/Users/PC/Documents/实验室/reports/qa/mobile-${name}.png` });
  }

  console.log('\n移动端 JS 错误:', JSON.stringify([...new Set(errs)].slice(0, 8)));
  await browser.close();
})().catch(e => { console.log('FATAL', e.message.slice(0, 200)); process.exit(1); });
