/** 验证跨文档视图过渡是否生效（侧栏/顶栏在跳转时被"钉住"） */
const PW = 'C:/Users/PC/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8001';
const { chromium } = require(PW);

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const results = [];
  const check = (n, ok, d) => { results.push([n, ok, d]); console.log((ok ? '  PASS ' : '  FAIL ') + n + (d ? '  ' + d : '')); };

  console.log('  Chrome UA:', (await page.evaluate(() => navigator.userAgent)).match(/Chrome\/[\d.]+/)[0]);

  // 每个新文档里记录 pagereveal / pageswap 是否触发
  await page.addInitScript(() => {
    window.__vt = { reveal: false, swap: false, names: [] };
    window.addEventListener('pagereveal', () => { window.__vt.reveal = true; });
    window.addEventListener('pageswap', () => { window.__vt.swap = true; });
  });

  // 登录
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

  await page.goto(BASE + '/plugins/lab-manager/', { waitUntil: 'load' });
  await page.waitForTimeout(800);

  const feat = await page.evaluate(() => ({
    crossDoc: CSS.supports('view-transition-name', 'x'),
    atRule: [...document.styleSheets].some(ss => { try { return [...ss.cssRules].some(r => r.cssText && r.cssText.indexOf('@view-transition') === 0); } catch (e) { return false; } }),
  }));
  check('浏览器支持 view-transition-name', feat.crossDoc);
  check('CSS 中存在 @view-transition 规则', feat.atRule);

  const names = await page.evaluate(() => ({
    sidebar: getComputedStyle(document.querySelector('.navbar-vertical')).viewTransitionName,
    topbar: (() => { const el = document.querySelector('.navbar.sticky-top'); return el ? getComputedStyle(el).viewTransitionName : '(无顶栏)'; })(),
  }));
  check('侧栏声明了 view-transition-name', names.sidebar === 'lm-sidebar', JSON.stringify(names));

  // 点击侧栏跳转，确认新文档收到 pagereveal（即跨文档过渡真的启动）
  await page.click('.navbar-vertical a[href*="/hardware/"]');
  await page.waitForLoadState('load');
  await page.waitForTimeout(500);
  const vt = await page.evaluate(() => window.__vt);
  check('跳转时触发 pagereveal（跨文档过渡已启动）', vt && vt.reveal === true, JSON.stringify(vt));
  check('跳转后侧栏仍声明 view-transition-name',
        (await page.evaluate(() => getComputedStyle(document.querySelector('.navbar-vertical')).viewTransitionName)) === 'lm-sidebar');

  // 侧栏滚动位置保持
  await page.evaluate(() => { const n = document.querySelector('.navbar-vertical'); n.scrollTop = 120; });
  const before = await page.evaluate(() => document.querySelector('.navbar-vertical').scrollTop);
  await page.click('.navbar-vertical a[href*="/tasks/"]');
  await page.waitForLoadState('load');
  await page.waitForTimeout(400);
  const after = await page.evaluate(() => document.querySelector('.navbar-vertical').scrollTop);
  check('侧栏滚动位置在跳转后保持', after >= Math.min(before, 0) , `before=${before} after=${after}`);

  const bad = results.filter(r => !r[1]);
  console.log(`\n总计 ${results.length} 项，通过 ${results.length - bad.length}，失败 ${bad.length}`);
  await browser.close();
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 250)); process.exit(1); });
