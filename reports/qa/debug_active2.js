/** 对比两个页面的侧栏链接"外观差异"，定位高亮是怎么产生的 */
const PW = 'C:/Users/PC/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8001';
const { chromium } = require(PW);

const SNAP = () => {
  const out = [];
  document.querySelectorAll('.navbar-vertical a[href], .navbar-vertical li, .navbar-vertical .dropdown-item').forEach(function (el) {
    const cs = getComputedStyle(el);
    out.push({
      tag: el.tagName, href: el.getAttribute('href') || '',
      cls: String(el.className).slice(0, 70),
      aria: el.getAttribute('aria-current') || '',
      bg: cs.backgroundColor, color: cs.color, borderLeft: cs.borderLeftColor + ' ' + cs.borderLeftWidth,
      fw: cs.fontWeight,
    });
  });
  return out;
};

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
  const snaps = {};
  for (const [name, path] of [['硬件', '/plugins/lab-manager/hardware/'], ['任务', '/plugins/lab-manager/tasks/']]) {
    await page.goto(BASE + path, { waitUntil: 'load' });
    await page.waitForTimeout(1200);
    snaps[name] = await page.evaluate(SNAP);
  }

  const a = snaps['硬件'], t = snaps['任务'];
  console.log('=== 两个页面侧栏元素数量 ===', a.length, t.length);
  const n = Math.min(a.length, t.length);
  let diff = 0;
  for (let i = 0; i < n; i++) {
    const x = a[i], y = t[i];
    const keys = ['cls', 'aria', 'bg', 'color', 'borderLeft', 'fw'];
    const changed = keys.filter(k => x[k] !== y[k]);
    if (changed.length) {
      diff++;
      if (diff <= 12) {
        console.log(`[${i}] ${x.href || x.tag}`);
        for (const k of changed) console.log(`      ${k}: 硬件="${x[k]}"  任务="${y[k]}"`);
      }
    }
  }
  console.log('差异元素总数:', diff);

  // 再打印"看起来像高亮"的元素（背景色非透明）
  console.log('\n=== 任务页中背景色非透明的侧栏元素 ===');
  t.filter(e => e.bg && e.bg !== 'rgba(0, 0, 0, 0)').slice(0, 8).forEach(e =>
    console.log(`   ${e.href || e.tag} cls="${e.cls}" bg=${e.bg} color=${e.color} fw=${e.fw} border=${e.borderLeft}`));

  await b.close();
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 200)); process.exit(1); });
