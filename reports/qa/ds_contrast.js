/** 视觉可用性诊断：主题令牌解析值 + 文本对比度 + 字号 + 重叠检测（暗/亮两种主题） */
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

  const AUDIT = () => {
    const root = getComputedStyle(document.documentElement);
    const tokens = ['--lm-surface-1', '--lm-text-primary', '--lm-text-muted', '--lm-accent',
                    '--lm-border-subtle', '--tp-card-bg', '--tp-card-text', '--tp-text-muted',
                    '--tp-card-border', '--tp-nav-accent'];
    const resolved = {};
    tokens.forEach(t => { resolved[t] = root.getPropertyValue(t).trim() || '(未定义)'; });

    const parse = c => {
      const m = (c || '').match(/rgba?\(([^)]+)\)/);
      if (!m) return null;
      const p = m[1].split(',').map(Number);
      return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
    };
    const lum = c => {
      const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
      return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
    };
    const blend = (fg, bg) => ({ r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a),
                                 b: fg.b * fg.a + bg.b * (1 - fg.a), a: 1 });
    const contrast = (fg, bg) => {
      const f = blend(fg, bg); const l1 = lum(f), l2 = lum(bg);
      return +(((Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05))).toFixed(2);
    };
    const bgOf = el => {
      let e = el;
      while (e) {
        const c = parse(getComputedStyle(e).backgroundColor);
        if (c && c.a > 0) return c;
        e = e.parentElement;
      }
      return { r: 255, g: 255, b: 255, a: 1 };
    };

    const targets = [
      ['.lm-kpi__label', 'KPI 标签'], ['.lm-kpi__hint', 'KPI 提示'], ['.lm-kpi__value', 'KPI 数值'],
      ['.lm-section__title', '分区标题'], ['.lm-card__header', '卡片标题'], ['.lm-badge--muted', '弱化徽标'],
      ['.lm-empty__desc', '空状态描述'], ['.lm-paginator', '分页器文字'], ['.lm-cmd__item small', '命令面板副标题'],
      ['.lm-todo__meta', '待办副文本'], ['.lm-heatmap__legend', '热力图图例'], ['.text-muted', 'Bootstrap 弱文本'],
      ['.lm-waterline__text', '水位条文字'], ['.lm-timeline__time', '时间线时间'],
    ];
    const out = [];
    for (const [sel, name] of targets) {
      const el = document.querySelector(sel);
      if (!el) { out.push({ name, sel, missing: true }); continue; }
      const cs = getComputedStyle(el);
      const fg = parse(cs.color); const bg = bgOf(el);
      const cr = fg ? contrast(fg, bg) : null;
      out.push({ name, sel, color: cs.color, bg: `rgb(${Math.round(bg.r)},${Math.round(bg.g)},${Math.round(bg.b)})`,
                 font: cs.fontSize, weight: cs.fontWeight, contrast: cr,
                 ok: cr === null ? null : cr >= 4.5 ? 'AA' : cr >= 3 ? 'AA-large only' : 'FAIL' });
    }
    const tiny = [...document.querySelectorAll('.lm-page *')]
      .filter(e => e.children.length === 0 && (e.textContent || '').trim())
      .map(e => ({ cls: String(e.className).slice(0, 30), fs: parseFloat(getComputedStyle(e).fontSize) }))
      .filter(x => x.fs < 10);
    return { resolved, rows: out, tiny: tiny.slice(0, 8) };
  };

  for (const theme of ['dark', 'light']) {
    await page.goto(BASE + '/plugins/lab-manager/design-system/', { waitUntil: 'domcontentloaded' });
    await page.evaluate(t => document.documentElement.setAttribute('data-bs-theme', t), theme);
    await page.waitForTimeout(600);
    const r = await page.evaluate(AUDIT);
    console.log(`\n========== 主题: ${theme} ==========`);
    console.log('令牌解析值:');
    for (const [k, v] of Object.entries(r.resolved)) console.log(`   ${k.padEnd(22)} ${v}`);
    console.log('文本对比度（WCAG: 正文需 ≥4.5，大字 ≥3）:');
    for (const row of r.rows) {
      if (row.missing) { console.log(`   ${row.name.padEnd(14)} 未在页面出现`); continue; }
      console.log(`   ${row.name.padEnd(14)} ${String(row.contrast).padStart(5)} :1  ${row.ok.padEnd(14)} ${row.font} ${row.color} on ${row.bg}`);
    }
    console.log('小于 10px 的文本:', JSON.stringify(r.tiny));
  }
  await browser.close();
})().catch(e => { console.log('FATAL', String(e.message).slice(0, 300)); process.exit(1); });
