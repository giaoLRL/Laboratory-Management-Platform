/** 抓取问题页面的全页截图（本地证据，不入库） */
const PW = 'C:/Users/PC/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8001';
const { chromium } = require(PW);

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

  const shots = [
    ['desktop-dashboard', '/plugins/lab-manager/', { width: 1440, height: 900 }, false],
    ['desktop-member-open-records', '/plugins/lab-manager/member-open-records/', { width: 1440, height: 900 }, false],
    ['desktop-task-detail', '/plugins/lab-manager/tasks/1/', { width: 1440, height: 900 }, false],
    ['mobile-dashboard', '/plugins/lab-manager/', { width: 390, height: 844 }, true],
    ['mobile-member-detail', '/plugins/lab-manager/members/3/', { width: 390, height: 844 }, true],
  ];
  for (const [name, path, vp, isMobile] of shots) {
    const ctx = await browser.newContext({ viewport: vp, isMobile, hasTouch: isMobile });
    await ctx.addCookies(cookies);
    const page = await ctx.newPage();
    await page.goto(BASE + path, { waitUntil: 'domcontentloaded', timeout: 40000 });
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `C:/Users/PC/Documents/实验室/reports/qa/ui-${name}.png`, fullPage: true });
    console.log('已截图', name, path);
    await ctx.close();
  }
  await browser.close();
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 200)); process.exit(1); });
