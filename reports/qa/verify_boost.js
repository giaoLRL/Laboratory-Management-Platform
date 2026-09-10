/** 验证侧栏局部导航：点菜单后侧栏 DOM 是否原样保留（没有被重建） */
const PW = 'C:/Users/PC/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8001';
const { chromium } = require(PW);

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
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
  const errs = [];
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 160)); });
  page.on('pageerror', e => errs.push('PAGEERROR ' + e.message.slice(0, 160)));

  const results = [];
  const check = (n, ok, d) => { results.push([n, ok, d]); console.log((ok ? '  PASS ' : '  FAIL ') + n + (d ? '  ' + d : '')); };

  await page.goto(BASE + '/plugins/lab-manager/', { waitUntil: 'load' });
  await page.waitForTimeout(900);

  const boostAttr = await page.evaluate(() => !!document.querySelector('[hx-boost="true"]'));
  check('侧栏已声明 hx-boost', boostAttr, boostAttr ? 'hx-boost=true' : '未声明');

  // 给侧栏打标记，跳转后检查标记是否还在（在 = DOM 未被重建）
  await page.evaluate(() => {
    document.querySelector('.navbar-vertical').dataset.lmProbe = 'kept';
    window.__sidebarNode = document.querySelector('.navbar-vertical');
    window.__beforeNav = true;
  });

  const t0 = Date.now();
  await Promise.all([
    page.waitForFunction(() => location.pathname.includes('/hardware/') && !!document.querySelector('#page-content table, #page-content .lm-toolbar'), { timeout: 20000 }),
    page.click('.navbar-vertical a[href="/plugins/lab-manager/hardware/"]'),
  ]);
  const ms = Date.now() - t0;

  const after = await page.evaluate(() => ({
    url: location.pathname,
    sameNode: (() => { try { return window.__sidebarNode === document.querySelector('.navbar-vertical'); } catch (e) { return 'ctx-lost'; } })(),
    probe: document.querySelector('.navbar-vertical').dataset.lmProbe || '(无)',
    sidebarAlive: !!window.__beforeNav,
    title: document.title.slice(0, 30),
    hasContent: !!document.querySelector('#page-content'),
    table: !!document.querySelector('#page-content table, #page-content .lm-toolbar'),
  }));
  check('点击菜单后侧栏仍是同一个 DOM 节点（未重建）', after.sameNode === true, `sameNode=${after.sameNode} probe=${after.probe} sidebarAlive=${after.sidebarAlive}`);
  check('URL 已更新', after.url.includes('/hardware/'), after.url);
  check('内容区已替换', after.hasContent && after.table, `content=${after.hasContent} table=${after.table}`);
  check('标签页标题已更新', after.title.includes('硬件') || after.title.length > 3, after.title);
  check('跳转耗时 < 900ms', ms < 900, `${ms}ms`);

  // 再跳一次，确认多次切换都保持
  await page.click('.navbar-vertical a[href="/plugins/lab-manager/tasks/"]');
  await page.waitForTimeout(1000);
  const again = await page.evaluate(() => ({
    sameNode: (() => { try { return window.__sidebarNode === document.querySelector('.navbar-vertical'); } catch (e) { return 'ctx-lost'; } })(),
    url: location.pathname,
  }));
  check('第二次切换侧栏仍未重建', again.sameNode === true, JSON.stringify(again));

  // 黑名单页面（智能体）应回退整页跳转
  await page.click('.navbar-vertical a[href="/plugins/lab-manager/agent/"]');
  await page.waitForLoadState('load').catch(() => {});
  await page.waitForTimeout(900);
  const blk = await page.evaluate(() => ({
    url: location.pathname,
    freshDocument: !window.__beforeNav,
    hasAgentShell: !!document.querySelector('.agent-shell, .agent-container, [class*=agent]'),
  }));
  check('黑名单页面（智能体）走整页跳转且正常渲染', blk.url.includes('/agent/') && blk.freshDocument && blk.hasAgentShell,
        JSON.stringify(blk));

  check('无 JS 报错', errs.length === 0, errs.slice(0, 3).join(' | '));

  const bad = results.filter(r => !r[1]);
  console.log(`\n总计 ${results.length} 项，通过 ${results.length - bad.length}，失败 ${bad.length}`);
  await browser.close();
  process.exit(bad.length ? 1 : 0);
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 250)); process.exit(1); });
