/** 设计系统页显示诊断：CSS 是否加载、布局异常、溢出、区块顺序与高度 */
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

  for (const [label, vp, isMobile] of [['桌面', { width: 1440, height: 900 }, false],
                                       ['移动', { width: 390, height: 844 }, true]]) {
    const ctx = await browser.newContext({ viewport: vp, isMobile, hasTouch: isMobile });
    await ctx.addCookies(cookies);
    const page = await ctx.newPage();
    const errs = [];
    page.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 160)); });
    page.on('pageerror', e => errs.push('PAGEERROR ' + e.message.slice(0, 160)));
    await page.goto(BASE + '/plugins/lab-manager/design-system/', { waitUntil: 'networkidle', timeout: 40000 });
    await page.waitForTimeout(1200);

    const diag = await page.evaluate(() => {
      const sheets = [...document.styleSheets].map(s => (s.href || '(inline)').split('/').pop().split('?')[0]);
      const lmLoaded = sheets.some(s => s.includes('lm-components'));
      const probe = sel => {
        const e = document.querySelector(sel);
        if (!e) return { sel, missing: true };
        const cs = getComputedStyle(e); const r = e.getBoundingClientRect();
        return { sel, w: Math.round(r.width), h: Math.round(r.height), display: cs.display,
                 bg: cs.backgroundColor, border: cs.borderTopColor, radius: cs.borderTopLeftRadius,
                 pad: cs.padding, sticky: cs.position };
      };
      // 溢出与异常元素
      const overflow = [];
      document.querySelectorAll('.lm-page *').forEach(e => {
        if (e.scrollWidth > e.clientWidth + 3 && getComputedStyle(e).overflowX !== 'auto' && e.clientWidth > 0) {
          overflow.push({ cls: String(e.className).slice(0, 40), sw: e.scrollWidth, cw: e.clientWidth });
        }
      });
      const zeroH = [...document.querySelectorAll('.lm-page .lm-card, .lm-page .lm-kpi, .lm-page .lm-badge, .lm-page .lm-skeleton')]
        .filter(e => e.getBoundingClientRect().height < 2)
        .map(e => String(e.className).slice(0, 40));
      // 区块顺序
      const sections = [...document.querySelectorAll('.lm-page > *')].map(e => {
        const r = e.getBoundingClientRect();
        return { tag: e.tagName, cls: String(e.className).slice(0, 34),
                 title: (e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 26),
                 top: Math.round(r.top), h: Math.round(r.height), w: Math.round(r.width) };
      });
      const cards = [...document.querySelectorAll('.lm-card')].map(e => {
        const r = e.getBoundingClientRect();
        return { cls: String(e.className).slice(0, 26), w: Math.round(r.width), h: Math.round(r.height) };
      });
      return { lmLoaded, sheets, kpi: probe('.lm-kpi'), card: probe('.lm-card'), badge: probe('.lm-badge'),
               skeleton: probe('.lm-skeleton'), table: probe('.lm-table'), waterline: probe('.lm-waterline'),
               overflow: overflow.slice(0, 6), zeroH: zeroH.slice(0, 6), sections, cards: cards.slice(0, 18),
               scrollH: document.documentElement.scrollHeight, vh: window.innerHeight };
    });

    console.log(`\n===== ${label} =====`);
    console.log('lm-components.css 已加载:', diag.lmLoaded);
    console.log('样式表:', diag.sheets.join(', '));
    console.log('关键组件计算样式:');
    for (const k of ['kpi', 'card', 'badge', 'skeleton', 'table', 'waterline']) {
      const p = diag[k];
      console.log('  ', k.padEnd(10), p.missing ? '缺失' : `w=${p.w} h=${p.h} display=${p.display} bg=${p.bg} border=${p.border} radius=${p.radius}`);
    }
    console.log('溢出元素:', JSON.stringify(diag.overflow));
    console.log('零高度组件:', JSON.stringify(diag.zeroH));
    console.log('页面区块顺序（top / 高度 / 宽）:');
    for (const s of diag.sections) console.log(`   ${String(s.top).padStart(5)} h=${String(s.h).padStart(4)} w=${String(s.w).padStart(4)}  ${s.cls.padEnd(22)} ${s.title}`);
    console.log('卡片尺寸:', diag.cards.map(c => `${c.cls}(w${c.w} h${c.h})`).join(' '));
    console.log('页面高度:', diag.scrollH, '视口:', diag.vh, '控制台错误:', errs.length ? errs : '无');

    await page.screenshot({ path: `C:/Users/PC/Documents/实验室/reports/qa/ds-${label}.png`, fullPage: true });
    await ctx.close();
  }
  await browser.close();
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 300)); process.exit(1); });
