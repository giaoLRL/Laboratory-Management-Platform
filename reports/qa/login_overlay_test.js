/** 登录页在窄屏下按钮/输入框是否被遮挡（覆盖层探测） */
const PW = 'C:/Users/PC/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8001';
const { chromium } = require(PW);

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  for (const [w, h, mobile, label] of [[390, 844, true, 'iPhone 390 (isMobile)'], [390, 844, false, '390 普通上下文'], [768, 1024, false, 'iPad 768'], [1440, 900, false, '桌面 1440']]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, isMobile: mobile, hasTouch: mobile });
    const page = await ctx.newPage();
    await page.goto(BASE + '/login/', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1000);
    const r = await page.evaluate(() => {
      const probe = sel => {
        const e = document.querySelector(sel);
        if (!e) return null;
        const b = e.getBoundingClientRect();
        const pts = [[b.x + b.width / 2, b.y + b.height / 2], [b.x + 5, b.y + 5]];
        return { sel, rect: { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) },
                 hits: pts.map(([x, y]) => { const t = document.elementFromPoint(x, y); return t ? t.tagName + '.' + String(t.className).slice(0, 40) : null; }),
                 selfHit: pts.map(([x, y]) => { const t = document.elementFromPoint(x, y); return t === e || e.contains(t); }) };
      };
      const panels = [...document.querySelectorAll('.AlertsPanel, [class*=Alert], [class*=overlay], [class*=scanline], [class*=particles]')]
        .map(e => { const b = e.getBoundingClientRect(); const cs = getComputedStyle(e);
          return { tag: e.tagName, cls: String(e.className).slice(0, 50), rect: { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) },
                   position: cs.position, zIndex: cs.zIndex, pointerEvents: cs.pointerEvents, display: cs.display }; })
        .filter(x => x.rect.w > 0 && x.rect.h > 0);
      return { button: probe('button[type=submit]'), user: probe('input[name=username]'), pass: probe('input[name=password]'), overlays: panels.slice(0, 6) };
    });
    console.log(`\n===== ${label} =====`);
    console.log(JSON.stringify(r, null, 1));
    await ctx.close();
  }
  await browser.close();
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 200)); process.exit(1); });
