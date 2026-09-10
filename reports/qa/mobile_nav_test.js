/** 移动端导航入口是否可达：列出所有可能打开菜单的控件 + 相关 CSS 规则 */
const PW = 'C:/Users/PC/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8001';
const { chromium } = require(PW);

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  for (const [w, h, label] of [[390, 844, 'iPhone 390'], [768, 1024, 'iPad 768'], [1440, 900, '桌面 1440']]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h } });
    const resp = await fetch(BASE + '/login/');
    const csrf = ((await resp.text()).match(/name="csrfmiddlewaretoken" value="([^"]+)"/) || [])[1];
    const c1 = resp.headers.getSetCookie().map(c => c.split('; ')[0]);
    const r2 = await fetch(BASE + '/login/', { method: 'POST', redirect: 'manual', headers: { 'Content-Type': 'application/x-www-form-urlencoded', Cookie: c1.join('; '), Referer: BASE + '/login/' }, body: new URLSearchParams({ username: 'admin', password: 'Lab-Manager@2026', csrfmiddlewaretoken: csrf, next: '/plugins/lab-manager/' }) });
    await ctx.addCookies([...c1, ...r2.headers.getSetCookie().map(c => c.split('; ')[0])].map(s => { const i = s.indexOf('='); return { name: s.slice(0, i), value: s.slice(i + 1), domain: '127.0.0.1', path: '/' }; }));
    const page = await ctx.newPage();
    await page.goto(BASE + '/plugins/lab-manager/tasks/', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1200);
    const info = await page.evaluate(() => {
      const cand = ['#tp-mobile-nav-btn', '.tp-mobile-nav-btn', '.navbar-toggler', '[data-bs-toggle="offcanvas"]', '.navbar-vertical'];
      const found = {};
      for (const sel of cand) {
        found[sel] = [...document.querySelectorAll(sel)].map(e => {
          const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
          const cx = r.x + r.width / 2, cy = r.y + r.height / 2;
          const top = document.elementFromPoint(cx, cy);
          return { cls: String(e.className).slice(0, 50), w: Math.round(r.width), h: Math.round(r.height), x: Math.round(r.x), y: Math.round(r.y),
                   display: cs.display, visibility: cs.visibility, clickableAtCenter: top === e || e.contains(top) };
        });
      }
      const rules = [];
      for (const ss of document.styleSheets) {
        let list; try { list = ss.cssRules; } catch { continue; }
        const walk = (rl, media) => {
          for (const r of rl) {
            if (r.media) walk(r.cssRules, r.media.mediaText);
            else if (r.selectorText && r.selectorText.includes('tp-mobile-nav-btn')) rules.push({ media: media || 'all', sel: r.selectorText.slice(0, 60), display: r.style.display, minH: r.style.minHeight });
          }
        };
        walk(list, '');
      }
      const btn = document.querySelector('#tp-mobile-nav-btn');
      return { found, rules: rules.slice(0, 12), htmlClass: document.documentElement.className, bodyClass: document.body.className,
               hasOpenNav: typeof window.openNav === 'function', parentChain: btn ? (() => { const a = []; let p = btn; while (p && a.length < 4) { const cs = getComputedStyle(p); a.push(p.tagName + '.' + String(p.className).slice(0, 30) + ' display=' + cs.display); p = p.parentElement; } return a; })() : null };
    });
    console.log(`\n===== ${label} (${w}x${h}) =====`);
    console.log(JSON.stringify(info, null, 1));
    await ctx.close();
  }
  await browser.close();
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 300)); process.exit(1); });
