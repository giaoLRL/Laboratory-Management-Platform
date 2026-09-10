/** 移动端：登录按钮可点性诊断 + 应用页布局测量 */
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
  await page.goto(BASE + '/login/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);

  console.log('=== A. 登录按钮诊断（390x844）===');
  const diag = await page.evaluate(() => {
    const btns = [...document.querySelectorAll('button[type=submit], input[type=submit]')];
    return btns.map(b => {
      const r = b.getBoundingClientRect();
      const cx = Math.round(r.left + r.width / 2), cy = Math.round(r.top + r.height / 2);
      const top = document.elementFromPoint(cx, cy);
      const cs = getComputedStyle(b);
      return {
        text: (b.textContent || b.value || '').trim().slice(0, 20),
        rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
        center: { cx, cy },
        inViewport: r.top >= 0 && r.bottom <= window.innerHeight,
        topElementAtCenter: top ? (top.tagName + '.' + String(top.className).slice(0, 60)) : null,
        isSelf: top === b || b.contains(top),
        pointerEvents: cs.pointerEvents, visibility: cs.visibility, display: cs.display, opacity: cs.opacity,
        zIndex: cs.zIndex,
      };
    });
  });
  console.log(JSON.stringify(diag, null, 1));

  // 试着真实点击（带 force 看是否只是被遮挡）
  const clicked = await page.click('button[type=submit]', { timeout: 6000 }).then(() => 'normal-ok').catch(e => 'normal-fail: ' + e.message.split('\n')[0]);
  console.log('普通点击:', clicked);
  const forced = await page.click('button[type=submit]', { force: true, timeout: 6000 }).then(() => 'force-ok').catch(e => 'force-fail');
  console.log('强制点击:', forced);
  await page.waitForTimeout(2000);
  console.log('点击后 URL:', page.url());

  console.log('\n=== B. 用 HTTP 登录绕过登录页，测应用页布局 ===');
  const resp = await fetch(BASE + '/login/');
  const html = await resp.text();
  const csrf = (html.match(/name="csrfmiddlewaretoken" value="([^"]+)"/) || [])[1];
  const cookieHdr = resp.headers.getSetCookie().map(c => c.split(';')[0]).join('; ');
  const body = new URLSearchParams({ username: 'admin', password: 'Lab-Manager@2026', csrfmiddlewaretoken: csrf, next: '/plugins/lab-manager/' });
  const r2 = await fetch(BASE + '/login/', { method: 'POST', body, redirect: 'manual',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded', Cookie: cookieHdr, Referer: BASE + '/login/' } });
  const setCookies = r2.headers.getSetCookie();
  const cookies = [...cookieHdr.split('; '), ...setCookies.map(c => c.split(';')[0])]
    .map(s => { const i = s.indexOf('='); return { name: s.slice(0, i), value: s.slice(i + 1), domain: '127.0.0.1', path: '/' }; })
    .filter(c => c.name);
  console.log('  登录响应:', r2.status, ' cookie 数:', cookies.length);
  await ctx.addCookies(cookies);
  const who = await ctx.newPage();
  await who.goto(BASE + '/plugins/lab-manager/', { waitUntil: 'domcontentloaded' });
  console.log('  验证登录态 URL:', who.url());
  await who.close();

  const pages = [['首页', '/plugins/lab-manager/'], ['任务列表', '/plugins/lab-manager/tasks/'],
                 ['硬件列表', '/plugins/lab-manager/hardware/'], ['日历', '/plugins/lab-manager/calendar/'],
                 ['智能体', '/plugins/lab-manager/agent/'], ['签到页', '/plugins/lab-manager/checkins/new/']];
  for (const [name, path] of pages) {
    await page.goto(BASE + path, { waitUntil: 'domcontentloaded', timeout: 40000 }).catch(() => {});
    await page.waitForTimeout(1500);
    const m = await page.evaluate(() => {
      const de = document.documentElement;
      const o = { pageScrollW: de.scrollWidth, viewportW: de.clientWidth, innerH: window.innerHeight,
                  horizOverflowPage: de.scrollWidth > de.clientWidth + 1 };
      const nav = document.querySelector('.navbar');
      if (nav) o.navH = Math.round(nav.getBoundingClientRect().height);
      const tr = document.querySelector('.table-responsive');
      if (tr) { o.tableScrollW = tr.scrollWidth; o.tableClientW = tr.clientWidth; o.tableCanScroll = tr.scrollWidth - tr.clientWidth; }
      const foot = document.querySelector('.agent-panel-footer, .agent-composer, .agent-input-row');
      if (foot) { const b = foot.getBoundingClientRect(); o.footerTop = Math.round(b.top); o.footerBottom = Math.round(b.bottom); o.footerVisible = b.top >= 0 && b.bottom <= window.innerHeight + 1; }
      const inp = document.querySelector('#agent-input');
      if (inp) { const b = inp.getBoundingClientRect(); o.inputBottom = Math.round(b.bottom); o.inputVisible = b.top >= 0 && b.bottom <= window.innerHeight + 1; }
      const shell = document.querySelector('.agent-shell, .agent-container, .agent-page');
      if (shell) { const b = shell.getBoundingClientRect(); o.shellH = Math.round(b.height); o.shellBottom = Math.round(b.bottom); }
      const burger = document.querySelector('.tp-mobile-nav-btn, .navbar-toggler');
      if (burger) { const b = burger.getBoundingClientRect(); o.burger = { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height), clickable: !!document.elementFromPoint(b.x + 4, b.y + 4) }; }
      const side = document.querySelector('#sidebar, .sidebar, .tp-sidebar');
      if (side) { const b = side.getBoundingClientRect(); o.sidebar = { w: Math.round(b.width), x: Math.round(b.x) }; }
      return o;
    });
    console.log(`  ${name.padEnd(6)} ${JSON.stringify(m)}`);
    await page.screenshot({ path: `C:/Users/PC/Documents/实验室/reports/qa/mobile-${name}.png` });
  }
  await browser.close();
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 300)); process.exit(1); });
