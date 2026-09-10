/** 导出「打卡管理」菜单组的真实 HTML，确认 active 落在哪个元素 */
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

  for (const url of ['/plugins/lab-manager/checkins/', '/plugins/lab-manager/member-open-records/', '/plugins/lab-manager/hardware/']) {
    const page = await ctx.newPage();
    await page.goto(BASE + url, { waitUntil: 'load' });
    await page.waitForTimeout(400);
    const html = await page.evaluate(() => {
      const nav = document.querySelector('.navbar-vertical');
      const act = [...nav.querySelectorAll('.active')];
      const groups = [...nav.querySelectorAll('.dropdown')].filter(d => d.querySelector('.active'));
      return {
        path: location.pathname,
        activeEls: act.map(e => ({ tag: e.tagName, cls: e.className, href: e.getAttribute('href'), text: e.textContent.trim().slice(0, 30) })),
        groupHtml: groups.map(g => g.outerHTML.replace(/></g, '>\n<')).join('\n---\n'),
      };
    });
    console.log('=== ' + html.path);
    console.log(JSON.stringify(html.activeEls, null, 1));
    if (url.endsWith('/checkins/')) require('fs').writeFileSync('reports/qa/shots/checkins_group.html', html.groupHtml);
    console.log(html.groupHtml.split('\n').slice(0, 60).join('\n'));
    await page.close();
  }
  await b.close();
})();
