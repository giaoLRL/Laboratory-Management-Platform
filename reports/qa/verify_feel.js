/** 手感验证：无限全屏动画数量 / 内容完全可见耗时 / 点击跳转延迟 / 长任务阻塞 / 毛玻璃数量 */
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

  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addCookies(cookies);
  const page = await ctx.newPage();

  const results = [];
  const check = (n, ok, d) => { results.push([n, ok, d]); console.log((ok ? '  PASS ' : '  FAIL ') + n + (d ? '  ' + d : '')); };

  // 1. 无限全屏动画与毛玻璃
  await page.goto(BASE + '/plugins/lab-manager/', { waitUntil: 'load' });
  await page.waitForTimeout(800);
  const audit = await page.evaluate(() => {
    const all = [...document.querySelectorAll('*')];
    const infinite = all.filter(e => {
      const cs = getComputedStyle(e);
      const r = e.getBoundingClientRect();
      return cs.animationIterationCount.split(',').some(v => v.trim() === 'infinite') && cs.animationName !== 'none' && r.width * r.height > 50000;
    }).map(e => ({ cls: String(e.className).slice(0, 28) || e.tagName, name: getComputedStyle(e).animationName }));
    const blur = all.filter(e => {
      const cs = getComputedStyle(e);
      const vis = e.getBoundingClientRect().height > 0 && cs.display !== 'none';
      return vis && ((cs.backdropFilter && cs.backdropFilter !== 'none') || (cs.webkitBackdropFilter && cs.webkitBackdropFilter !== 'none'));
    });
    return { infinite, blurCount: blur.length, blurCls: blur.map(e => String(e.className).slice(0, 24)) };
  });
  check('默认无全屏无限动画', audit.infinite.length === 0, audit.infinite.map(i => i.cls + ':' + i.name).join(', ') || '0 个');
  check('可见的毛玻璃元素', audit.blurCount <= 1, `${audit.blurCount} 处 ${JSON.stringify(audit.blurCls)}`);

  // 2. 内容完全可见耗时（首次 + 二次导航）
  async function timeToVisible() {
    const t0 = Date.now();
    await page.waitForFunction(() => {
      const els = [...document.querySelectorAll('.tp-stat-animate-in, .tp-count-up')];
      if (!els.length) return document.readyState === 'complete';
      return els.every(e => parseFloat(getComputedStyle(e).opacity) >= 0.99);
    }, { timeout: 8000 }).catch(() => {});
    return Date.now() - t0;
  }
  await page.goto(BASE + '/plugins/lab-manager/', { waitUntil: 'commit' });
  const first = await timeToVisible();
  await page.goto(BASE + '/plugins/lab-manager/tasks/', { waitUntil: 'commit' });
  const second = await timeToVisible();
  await page.goto(BASE + '/plugins/lab-manager/hardware/', { waitUntil: 'commit' });
  const third = await timeToVisible();
  check('首次加载内容可见耗时', first < 1500, `${first}ms`);
  check('二次导航内容可见耗时（应近似瞬时）', second < 400, `${second}ms`);
  check('三次导航内容可见耗时', third < 400, `${third}ms`);

  // 3. 点击跳转延迟（真实点击侧栏）
  await page.goto(BASE + '/plugins/lab-manager/', { waitUntil: 'load' });
  await page.waitForTimeout(500);
  for (const target of ['/tasks/', '/checkins/', '/members/']) {
    const t0 = Date.now();
    await Promise.all([
      page.waitForFunction(t => location.pathname.indexOf(t) !== -1, target, { timeout: 15000 }),
      page.click(`.navbar-vertical a[href*="${target}"]`).catch(() => {}),
    ]);
    const ms = Date.now() - t0;
    check(`点击跳转 ${target}`, ms < 900, `${ms}ms`);
    await page.waitForTimeout(200);
  }

  // 4. 长任务（主线程阻塞）
  const blocking = await page.evaluate(async () => {
    let total = 0; let count = 0;
    const po = new PerformanceObserver(list => {
      for (const e of list.getEntries()) { total += e.duration; count++; }
    });
    try { po.observe({ entryTypes: ['longtask'] }); } catch (e) { return { unsupported: true }; }
    for (let i = 0; i < 25; i++) { window.scrollBy(0, 200); await new Promise(r => setTimeout(r, 60)); }
    po.disconnect();
    return { totalMs: Math.round(total), count };
  });
  check('滚动期间主线程长任务少', blocking.unsupported || blocking.totalMs < 300,
        JSON.stringify(blocking));

  // 5. 特效开关可恢复动效
  await page.goto(BASE + '/plugins/lab-manager/hardware/', { waitUntil: 'load' });
  await page.waitForTimeout(600);
  await page.click('button[data-lm-effects-toggle]');
  await page.waitForTimeout(300);
  const reOn = await page.evaluate(() => document.documentElement.classList.contains('lm-effects'));
  const infiniteOn = await page.evaluate(() => [...document.querySelectorAll('*')].filter(e => {
    const cs = getComputedStyle(e);
    return cs.animationIterationCount.split(',').some(v => v.trim() === 'infinite') && cs.animationName !== 'none';
  }).length);
  check('开启特效后动画恢复', reOn && infiniteOn > 0, `lm-effects=${reOn}, 无限动画=${infiniteOn}`);
  await page.click('button[data-lm-effects-toggle]');
  await page.waitForTimeout(200);

  const bad = results.filter(r => !r[1]);
  console.log(`\n总计 ${results.length} 项，通过 ${results.length - bad.length}，失败 ${bad.length}`);
  await browser.close();
  process.exit(bad.length ? 1 : 0);
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 300)); process.exit(1); });
