/** 1) 侧栏加载后是否重放过渡（采样 computed style）  2) VT 在特性开关/有头模式下是否生效 */
const PW = 'C:/Users/PC/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8001';
const { chromium } = require(PW);

async function login(ctx) {
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
}

async function trial(label, launchOpts) {
  const browser = await chromium.launch({ executablePath: CHROME, ...launchOpts });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await login(ctx);
  const page = await ctx.newPage();
  await page.addInitScript(() => {
    window.__vt = { reveal: false };
    window.addEventListener('pagereveal', () => { window.__vt.reveal = true; });
  });
  await page.goto(BASE + '/plugins/lab-manager/', { waitUntil: 'load' });
  await page.waitForTimeout(600);
  // 采样侧栏激活项在加载后的样式变化
  const sample = await page.evaluate(async () => {
    const el = document.querySelector('.navbar-vertical a.nav-link.active') || document.querySelector('.navbar-vertical a.nav-link');
    if (!el) return null;
    const read = () => { const cs = getComputedStyle(el); return [cs.transform, cs.paddingLeft, cs.backgroundColor, cs.color].join('|'); };
    const seen = new Set();
    for (let i = 0; i < 30; i++) { seen.add(read()); await new Promise(r => setTimeout(r, 20)); }
    return { distinctStates: seen.size, states: [...seen].slice(0, 3) };
  });
  // 触发一次真实跳转并检查 pagereveal
  await page.click('.navbar-vertical a[href="/plugins/lab-manager/hardware/"]').catch(async () => {
    await page.evaluate(() => { const a = document.querySelector('.navbar-vertical a[href="/plugins/lab-manager/hardware/"]'); a && a.click(); });
  });
  await page.waitForLoadState('load').catch(() => {});
  await page.waitForTimeout(500);
  const vt = await page.evaluate(() => window.__vt).catch(() => null);
  console.log(`\n[${label}]`);
  console.log('  侧栏激活项加载后样式状态数:', sample ? sample.distinctStates : 'n/a', sample ? JSON.stringify(sample.states) : '');
  console.log('  pagereveal 触发:', vt ? vt.reveal : 'n/a');
  await browser.close();
}

(async () => {
  await trial('无头 + 特性开关', { headless: true, args: ['--enable-features=ViewTransitionOnNavigation'] });
  await trial('有头（真实窗口）', { headless: false });
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 200)); process.exit(1); });
