/** 交互层功能验证：命令面板 / AI 副驾驶 / 密度切换 / 投屏模式 */
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
  const errs = [];
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 140)); });
  page.on('pageerror', e => errs.push('PAGEERROR ' + e.message.slice(0, 140)));

  const results = [];
  const check = (name, ok, detail) => { results.push([name, ok, detail]); console.log((ok ? '  PASS ' : '  FAIL ') + name + (detail ? '  ' + detail : '')); };

  await page.goto(BASE + '/plugins/lab-manager/hardware/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(800);

  // 1. 命令面板
  await page.keyboard.press('Control+k');
  await page.waitForTimeout(1200);
  check('⌘K 打开面板', await page.evaluate(() => document.getElementById('lm-cmd').classList.contains('is-open')));
  const count = await page.evaluate(() => document.querySelectorAll('#lm-cmd-list .lm-cmd__item').length);
  check('索引加载并渲染条目', count > 10, `${count} 条`);
  await page.fill('#lm-cmd-input', '指挥舱');
  await page.waitForTimeout(300);
  const filtered = await page.evaluate(() => [...document.querySelectorAll('#lm-cmd-list .lm-cmd__item')].map(e => e.textContent.trim().slice(0, 20)));
  check('输入过滤生效', filtered.some(t => t.includes('指挥舱')), JSON.stringify(filtered.slice(0, 3)));
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Escape');
  check('Esc 关闭面板', !(await page.evaluate(() => document.getElementById('lm-cmd').classList.contains('is-open'))));

  // 2. 密度切换
  const before = await page.evaluate(() => document.body.classList.contains('lm-density--compact'));
  await page.click('button[data-lm-density-toggle]');
  await page.waitForTimeout(200);
  const after = await page.evaluate(() => document.body.classList.contains('lm-density--compact'));
  check('密度切换 (localStorage 持久化)', before !== after, `${before} -> ${after}`);
  const stored = await page.evaluate(() => localStorage.getItem('lm_table_density'));
  check('密度写入 localStorage', stored === (after ? 'compact' : 'comfortable'), String(stored));

  // 3. AI 副驾驶
  await page.click('#lm-copilot-btn');
  await page.waitForTimeout(500);
  check('副驾驶面板打开', await page.evaluate(() => document.getElementById('lm-copilot').classList.contains('is-open')));
  const ctxText = await page.evaluate(() => document.getElementById('lm-copilot-ctx').textContent || '');
  check('副驾驶显示页面上下文', ctxText.length > 3, ctxText.slice(0, 40));
  const bubbles = await page.evaluate(() => document.querySelectorAll('#lm-copilot-log .lm-copilot__msg').length);
  check('副驾驶首屏欢迎语', bubbles >= 1, `${bubbles} 条`);

  // 4. 投屏模式
  await page.goto(BASE + '/plugins/lab-manager/mission-control/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(600);
  await page.click('[data-lm-projector-toggle]');
  await page.waitForTimeout(400);
  check('投屏模式生效', await page.evaluate(() => document.body.classList.contains('lm-projector')));

  // 5. 看板拖拽后端已单独验证，这里验证卡片可拖
  await page.goto(BASE + '/plugins/lab-manager/tasks/board/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(600);
  check('看板卡片可拖拽', await page.evaluate(() => {
    const c = document.querySelector('.lm-kanban__card');
    return !!c && c.getAttribute('draggable') === 'true';
  }));

  check('无 JS 报错', errs.length === 0, errs.slice(0, 2).join(' | '));
  const bad = results.filter(r => !r[1]);
  console.log(`\n总计 ${results.length} 项，通过 ${results.length - bad.length}，失败 ${bad.length}`);
  await browser.close();
  process.exit(bad.length ? 1 : 0);
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 200)); process.exit(1); });
