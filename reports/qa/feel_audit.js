/** 使用手感量化：页面加载耗时 / 资源体积 / 入场动画 / 固定层 / 滚动帧率 / 跳转延迟 / 输入延迟 */
const PW = 'C:/Users/PC/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8001';
const { chromium } = require(PW);

const PAGES = [
  ['仪表板', '/plugins/lab-manager/'],
  ['硬件列表', '/plugins/lab-manager/hardware/'],
  ['任务列表', '/plugins/lab-manager/tasks/'],
  ['打卡记录', '/plugins/lab-manager/checkins/'],
  ['浏览记录', '/plugins/lab-manager/member-open-records/'],
  ['指挥舱', '/plugins/lab-manager/mission-control/'],
  ['智能体', '/plugins/lab-manager/agent/'],
];

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

  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addCookies(cookies);
  const page = await ctx.newPage();

  // 资源体积统计
  const resStats = { css: 0, js: 0, other: 0, count: 0, blockingJs: 0 };
  page.on('response', async r => {
    try {
      const url = r.url();
      const len = Number(r.headers()['content-length'] || 0);
      resStats.count++;
      if (url.endsWith('.css')) resStats.css += len;
      else if (url.endsWith('.js')) resStats.js += len;
      else resStats.other += len;
    } catch (e) { /* ignore */ }
  });

  console.log('=== 每个页面的加载与渲染开销 ===');
  console.log('页面       TTFB  DCL   load   资源数   CSS(KB) JS(KB)  DOM节点  动画元素  最长动画(ms)  固定层  backdrop-filter');
  for (const [name, path] of PAGES) {
    resStats.css = resStats.js = resStats.other = 0; resStats.count = 0;
    const t0 = Date.now();
    await page.goto(BASE + path, { waitUntil: 'load', timeout: 60000 });
    const wall = Date.now() - t0;
    await page.waitForTimeout(1200); // 等动画跑完
    const m = await page.evaluate(() => {
      const nav = performance.getEntriesByType('navigation')[0] || {};
      const anims = [...document.querySelectorAll('*')].map(e => {
        const cs = getComputedStyle(e);
        const dur = parseFloat(cs.animationDuration) + parseFloat(cs.transitionDuration);
        return (dur > 0.05 && (cs.animationName !== 'none' || cs.transitionProperty !== 'all')) ||
               e.classList.contains('tp-stat-animate-in') || e.classList.contains('tp-count-up') ? { dur } : null;
      }).filter(Boolean);
      const fixed = [...document.querySelectorAll('*')].filter(e => {
        const cs = getComputedStyle(e);
        return (cs.position === 'fixed' || cs.position === 'absolute') && e.getBoundingClientRect().height > 200;
      });
      const blur = [...document.querySelectorAll('*')].filter(e => {
        const cs = getComputedStyle(e);
        return (cs.backdropFilter && cs.backdropFilter !== 'none') || (cs.webkitBackdropFilter && cs.webkitBackdropFilter !== 'none');
      });
      return {
        ttfb: Math.round(nav.responseStart || 0), dcl: Math.round(nav.domContentLoadedEventEnd || 0),
        load: Math.round(nav.loadEventEnd || 0), nodes: document.querySelectorAll('*').length,
        animCount: anims.length, maxAnim: Math.round(Math.max(0, ...anims.map(a => a.dur)) * 1000),
        fixedCount: fixed.length, blurCount: blur.length,
        htmlSize: document.documentElement.outerHTML.length,
      };
    });
    console.log(`${name.padEnd(8)} ${String(m.ttfb).padStart(5)} ${String(m.dcl).padStart(5)} ${String(m.load).padStart(6)} ${String(resStats.count).padStart(6)} ${String(Math.round(resStats.css / 1024)).padStart(8)} ${String(Math.round(resStats.js / 1024)).padStart(6)} ${String(m.nodes).padStart(8)} ${String(m.animCount).padStart(9)} ${String(m.maxAnim).padStart(11)} ${String(m.fixedCount).padStart(6)} ${String(m.blurCount).padStart(6)}   (wall=${wall}ms, html=${Math.round(m.htmlSize / 1024)}KB)`);
  }

  // 滚动帧率
  console.log('\n=== 滚动帧率（越高越顺，60 为满帧）===');
  await page.goto(BASE + '/plugins/lab-manager/member-open-records/', { waitUntil: 'load' });
  await page.waitForTimeout(1000);
  const fps = await page.evaluate(async () => {
    const frames = [];
    let last = performance.now();
    let running = true;
    const tick = () => { const n = performance.now(); frames.push(n - last); last = n; if (running) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
    for (let i = 0; i < 40; i++) { window.scrollBy(0, 120); await new Promise(r => setTimeout(r, 40)); }
    running = false;
    const avg = frames.reduce((a, b) => a + b, 0) / Math.max(frames.length, 1);
    const long = frames.filter(f => f > 33).length;
    return { avgFrame: +avg.toFixed(1), fps: +(1000 / avg).toFixed(1), longFrames: long, samples: frames.length };
  });
  console.log('  ', JSON.stringify(fps));

  // 点击导航延迟
  console.log('\n=== 点击侧栏跳转的延迟 ===');
  await page.goto(BASE + '/plugins/lab-manager/', { waitUntil: 'load' });
  await page.waitForTimeout(800);
  const nav = await page.evaluate(async () => {
    const link = [...document.querySelectorAll('.navbar-vertical a')].find(a => (a.getAttribute('href') || '').includes('/hardware/'));
    if (!link) return { error: '未找到链接' };
    const t0 = performance.now();
    link.click();
    await new Promise(res => {
      const check = () => { if (document.readyState === 'complete' && location.pathname.includes('/hardware/')) res(); else setTimeout(check, 10); };
      check();
    });
    return { clickToLoad: Math.round(performance.now() - t0), url: location.pathname };
  });
  console.log('  ', JSON.stringify(nav));

  // 输入延迟（命令面板 / 搜索框）
  console.log('\n=== 输入延迟（按键 → 下一帧）===');
  const input = await page.evaluate(async () => {
    const el = document.querySelector('#lm-cmd-input') || document.querySelector('input[type=search]') || document.querySelector('input');
    if (!el) return { error: '无输入框' };
    const samples = [];
    for (let i = 0; i < 12; i++) {
      const t0 = performance.now();
      el.value = 'a'.repeat(i + 1);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      await new Promise(r => requestAnimationFrame(() => r()));
      samples.push(performance.now() - t0);
    }
    return { avg: +(samples.reduce((a, b) => a + b, 0) / samples.length).toFixed(1), max: +Math.max(...samples).toFixed(1) };
  });
  console.log('  ', JSON.stringify(input));

  await browser.close();
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 300)); process.exit(1); });
