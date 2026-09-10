/** 找出真正生效的 .dropdown-item.active 背景/前景规则（含来源文件） */
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
  await page.goto(BASE + '/plugins/lab-manager/checkins/', { waitUntil: 'load' });
  await page.waitForTimeout(800);
  await page.evaluate(() => document.documentElement.setAttribute('data-bs-theme', 'dark'));
  await page.waitForTimeout(200);

  const out = await page.evaluate(() => {
    const row = document.querySelector('.navbar-vertical .dropdown-item.active');
    const a = row.querySelector('a[href]:not(.btn)');
    const hits = { row: [], link: [] };
    for (const ss of document.styleSheets) {
      let rules;
      try { rules = ss.cssRules; } catch (e) { continue; }
      const href = (ss.href || 'inline').split('/').slice(-1)[0];
      for (const r of rules) {
        if (!r.selectorText || !r.style) continue;
        const bg = r.style.getPropertyValue('background-color') || r.style.getPropertyValue('background');
        const col = r.style.getPropertyValue('color');
        const img = r.style.getPropertyValue('background-image');
        if (!bg && !col && !img) continue;
        let mRow = false, mLink = false;
        try { mRow = row.matches(r.selectorText); } catch (e) { continue; }
        try { mLink = a.matches(r.selectorText); } catch (e) { /* ignore */ }
        const imp = (p) => r.style.getPropertyPriority(p) === 'important' ? '!' : '';
        if (mRow && (bg || img)) hits.row.push(`${href} :: ${r.selectorText} => bg:${bg}${imp('background-color') || imp('background')} img:${img}${imp('background-image')}`);
        if (mLink && col) hits.link.push(`${href} :: ${r.selectorText} => color:${col}${imp('color')}`);
      }
    }
    return { rowCls: row.className, aCls: a.className, hits };
  });
  console.log('ROW', out.rowCls, '\nLINK', out.aCls);
  console.log('\n-- 背景规则（匹配该行的全部） --\n' + out.hits.row.join('\n'));
  console.log('\n-- 前景规则（匹配该链接的全部） --\n' + out.hits.link.join('\n'));
  await b.close();
})();
