/** 截图确认侧栏高亮的视觉呈现（浅色 / 深色） */
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
  await page.goto(BASE + '/plugins/lab-manager/', { waitUntil: 'load' });
  await page.waitForTimeout(700);

  const shot = async (label, url, theme) => {
    await page.click(`.navbar-vertical a[href="${url}"]`).catch(async () => { await page.goto(BASE + url); });
    await page.waitForTimeout(800);
    await page.evaluate(t => document.documentElement.setAttribute('data-bs-theme', t), theme);
    await page.waitForTimeout(250);
    const info = await page.evaluate(() => {
      const nav = document.querySelector('.navbar-vertical');
      const rows = [...nav.querySelectorAll('.dropdown-item.active')].map(el => {
        const a = el.querySelector('a[href]:not(.btn)');
        const cs = getComputedStyle(el);
        return { cur: !!el.querySelector('[aria-current="page"]'), href: a ? a.getAttribute('href') : null, text: el.textContent.trim().slice(0, 22), bg: cs.backgroundColor, shadow: cs.boxShadow.slice(0, 34) };
      });
      return { url: location.pathname, theme: document.documentElement.getAttribute('data-bs-theme'), rows };
    });
    console.log(label, JSON.stringify(info, null, 1).replace(/\n\s*/g, ' '));
    await page.locator('.navbar-vertical').screenshot({ path: `reports/qa/shots/nav_${label}.png` });
  };

  await shot('checkins_light', '/plugins/lab-manager/checkins/', 'light');
  await shot('checkins_dark', '/plugins/lab-manager/checkins/', 'dark');
  await shot('hardware_dark', '/plugins/lab-manager/hardware/', 'dark');
  await b.close();
})();
