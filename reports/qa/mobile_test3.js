/** 移动端精测：.navbar 到底是什么、汉堡按钮是否存在、聊天输入框能否滚到 */
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
  // HTTP 登录后注入 cookie
  const resp = await fetch(BASE + '/login/');
  const csrf = ((await resp.text()).match(/name="csrfmiddlewaretoken" value="([^"]+)"/) || [])[1];
  const c1 = resp.headers.getSetCookie().map(c => c.split('; ')[0]);
  const r2 = await fetch(BASE + '/login/', { method: 'POST', redirect: 'manual', headers: { 'Content-Type': 'application/x-www-form-urlencoded', Cookie: c1.join('; '), Referer: BASE + '/login/' }, body: new URLSearchParams({ username: 'admin', password: 'Lab-Manager@2026', csrfmiddlewaretoken: csrf, next: '/plugins/lab-manager/' }) });
  const all = [...c1, ...r2.headers.getSetCookie().map(c => c.split('; ')[0])];
  await ctx.addCookies(all.map(s => { const i = s.indexOf('='); return { name: s.slice(0, i), value: s.slice(i + 1), domain: '127.0.0.1', path: '/' }; }));
  const page = await ctx.newPage();

  for (const [name, path] of [['任务列表', '/plugins/lab-manager/tasks/'], ['智能体', '/plugins/lab-manager/agent/']]) {
    await page.goto(BASE + path, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);
    const info = await page.evaluate(() => {
      const pick = sel => { const e = document.querySelector(sel); if (!e) return null; const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return { sel, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), position: cs.position, transform: cs.transform.slice(0, 40), display: cs.display, zIndex: cs.zIndex, overflow: cs.overflow }; };
      const navs = [...document.querySelectorAll('.navbar')].slice(0, 3).map(e => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return { cls: String(e.className).slice(0, 60), x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), position: cs.position, transform: cs.transform.slice(0, 30), display: cs.display }; });
      return {
        navbars: navs,
        sidebar: pick('#sidebar, .sidebar, .tp-sidebar, aside'),
        pageWrapper: pick('.page-wrapper, .page-body, main'),
        hamburgerInHtml: !!document.querySelector('.tp-mobile-nav-btn'),
        togglerInHtml: !!document.querySelector('.navbar-toggler'),
        hamburgerVisible: (() => { const b = document.querySelector('.tp-mobile-nav-btn, .navbar-toggler'); if (!b) return null; const r = b.getBoundingClientRect(); const cs = getComputedStyle(b); return { w: Math.round(r.width), h: Math.round(r.height), display: cs.display, visibility: cs.visibility, opacity: cs.opacity, x: Math.round(r.x), y: Math.round(r.y) }; })(),
        docScrollH: document.documentElement.scrollHeight,
        bodyScrollH: document.body.scrollHeight,
        canScrollY: document.documentElement.scrollHeight > window.innerHeight,
      };
    });
    console.log(`\n===== ${name} =====`);
    console.log(JSON.stringify(info, null, 1));
    if (name === '智能体') {
      const before = await page.evaluate(() => { const i = document.querySelector('#agent-input'); return i ? Math.round(i.getBoundingClientRect().bottom) : null; });
      await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
      await page.waitForTimeout(800);
      const after = await page.evaluate(() => {
        const i = document.querySelector('#agent-input');
        const f = document.querySelector('.agent-panel-footer, .agent-composer');
        return { inputBottom: i ? Math.round(i.getBoundingClientRect().bottom) : null, footerBottom: f ? Math.round(f.getBoundingClientRect().bottom) : null, scrollY: Math.round(window.scrollY), innerH: window.innerHeight };
      });
      console.log('  滚到底前输入框 bottom =', before, ' 滚到底后 =', JSON.stringify(after));
      await page.screenshot({ path: 'C:/Users/PC/Documents/实验室/reports/qa/mobile-agent-scrolled.png' });
    }
    const html = await page.content();
    console.log('  HTML 里 tp-mobile-nav-btn 次数:', (html.match(/tp-mobile-nav-btn/g) || []).length,
                '| navbar-toggler 次数:', (html.match(/navbar-toggler/g) || []).length);
  }
  await browser.close();
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 300)); process.exit(1); });
