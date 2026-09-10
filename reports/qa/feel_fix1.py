"""手感优化批次：全屏无限动画默认静音 / 入场动画提速且每会话仅一次 / 悬停预取 / 特效开关。"""
import io
import os
import sys

BASE = r'C:\Users\PC\Documents\实验室\netbox-main\netbox'
APPLY = '--apply' in sys.argv
report, failures = [], []


def read(rel):
    return io.open(os.path.join(BASE, rel), encoding='utf-8').read()


def write(rel, src):
    if APPLY:
        io.open(os.path.join(BASE, rel), 'w', encoding='utf-8', newline='').write(src)


def patch(rel, pairs, allow=1):
    src = read(rel)
    orig = src
    for old, new in pairs:
        n = src.count(old)
        if n != allow:
            failures.append(f'{rel}: 期望 {allow} 次，实际 {n} 次 -> {old.strip().splitlines()[0][:60]!r}')
            continue
        src = src.replace(old, new)
        report.append(f'  ok {rel}: {old.strip().splitlines()[0][:56]}')
    if src != orig:
        write(rel, src)


# ── 1. CSS：默认静音无限动画 + 去大面毛玻璃 + 页面淡入 ──────────
css = read('lab_manager/static/lab_manager/lm-components.css')
if 'lm-effects' not in css:
    css = css.rstrip('\n') + """

/* ═══════════════════════════════════════════════════════════════
   手感与性能层
   问题：主题的扫描线（1.5s 无限循环）与粒子（22s/28s 无限）都是全屏动画，
   页面会持续重绘；滚动与低端设备上表现为"发滞、手感怪"。
   策略：默认静止（保留静态质感），用户可在命令面板开启「特效」找回动效。
   ═══════════════════════════════════════════════════════════════ */
html:not(.lm-effects) .tp-scanlines,
html:not(.lm-effects) .tp-particles::before,
html:not(.lm-effects) .tp-particles::after,
html:not(.lm-effects) .tp-countdown-card,
html:not(.lm-effects) .tp-countdown-icon {
  animation: none !important;
}
/* 尊重系统设置：任何情况下都不播无限动画 */
@media (prefers-reduced-motion: reduce) {
  .tp-scanlines, .tp-particles::before, .tp-particles::after,
  .tp-countdown-card, .tp-countdown-icon { animation: none !important; }
}

/* 大面毛玻璃（侧栏/顶栏）在滚动时开销高 → 默认改为实底 */
html:not(.lm-effects) .tp-page .navbar-vertical,
html:not(.lm-effects) .tp-page .navbar.sticky-top,
html:not(.lm-effects) .tp-page .tp-sidebar {
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
}

/* 页面切换淡入：只做 opacity，避免合成层与布局抖动 */
@keyframes lm-page-in { from { opacity: 0; } to { opacity: 1; } }
.tp-page .page-wrapper { animation: lm-page-in 140ms ease-out both; }
@media (prefers-reduced-motion: reduce) {
  .tp-page .page-wrapper { animation: none; }
}
html.lm-effects .tp-page .page-wrapper { animation-duration: 260ms; }
"""
    write('lab_manager/static/lab_manager/lm-components.css', css)
    report.append('  ok lm-components.css: 追加手感与性能层')
else:
    report.append('  -- lm-components.css: 已含手感层，跳过')

# ── 2. animations.js：时长与错峰大幅缩短 + 每会话仅播一次 ────────
patch('lab_manager/static/lab_manager/animations.js', [
    (
        "  var isMobile = window.innerWidth < 768;\n"
        "  var prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;\n"
        "  var DURATION = prefersReduced ? 0 : (isMobile ? 400 : 800);\n"
        "  var FRAME_RATE = 16;      // ~60fps\n"
        "  var BAR_DELAY = prefersReduced ? 0 : (isMobile ? 15 : 30);  // 移动端交错延迟减半\n",
        "  var isMobile = window.innerWidth < 768;\n"
        "  var prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;\n"
        "  // 入场动画只在本次会话的首次页面加载播放：翻页/返回时立即呈现内容，避免\"每次都等动画\"\n"
        "  var firstVisit = false;\n"
        "  try {\n"
        "    firstVisit = !sessionStorage.getItem('lm_anim_played');\n"
        "    sessionStorage.setItem('lm_anim_played', '1');\n"
        "  } catch (e) { firstVisit = true; }\n"
        "  var SKIP = prefersReduced || !firstVisit;\n"
        "  // 时长从 800ms 收紧到 260ms（移动 200ms），错峰同步收紧\n"
        "  var DURATION = SKIP ? 0 : (isMobile ? 200 : 260);\n"
        "  var FRAME_RATE = 16;      // ~60fps\n"
        "  var BAR_DELAY = SKIP ? 0 : (isMobile ? 6 : 10);\n",
    ),
    (
        "        card.style.transition = 'opacity 0.4s ease-out, transform 0.4s ease-out';\n"
        "        card.style.transitionDelay = (index * 60) + 'ms';\n",
        "        card.style.transition = 'opacity 0.22s ease-out, transform 0.22s ease-out';\n"
        "        card.style.transitionDelay = (index * 18) + 'ms';\n",
    ),
])

# ── 3. lm-ui.js：悬停预取 + 特效开关 ───────────────────────────
patch('lab_manager/static/lab_manager/lm-ui.js', [
    (
        "  document.addEventListener('DOMContentLoaded', function () {\n"
        "    initDensity(); initPalette(); initCopilot(); initKanban(); initProjector(); initRowLinks();\n"
        "  });\n",
        "  /* ── 7. 悬停预取：鼠标移到链接上就预取目标页，点击后命中缓存（导航更跟手） ── */\n"
        "  function initPrefetch() {\n"
        "    if (!('prefetch' in document.createElement('link'))) return;\n"
        "    var seen = Object.create(null);\n"
        "    document.addEventListener('mouseover', function (e) {\n"
        "      var a = e.target.closest && e.target.closest('a[href]');\n"
        "      if (!a) return;\n"
        "      var href = a.getAttribute('href') || '';\n"
        "      if (!href || href.charAt(0) !== '/' || a.target === '_blank' || seen[href]) return;\n"
        "      if (a.hasAttribute('data-bs-toggle') || href.indexOf('#') === 0) return;\n"
        "      seen[href] = 1;\n"
        "      var link = document.createElement('link');\n"
        "      link.rel = 'prefetch';\n"
        "      link.href = href;\n"
        "      document.head.appendChild(link);\n"
        "    }, { passive: true });\n"
        "  }\n"
        "\n"
        "  /* ── 8. 特效开关（默认关闭全屏无限动画） ── */\n"
        "  function initEffects() {\n"
        "    var KEY = 'lm_effects';\n"
        "    var on = false;\n"
        "    try { on = localStorage.getItem(KEY) === '1'; } catch (e) { /* ignore */ }\n"
        "    document.documentElement.classList.toggle('lm-effects', on);\n"
        "    qsa('[data-lm-effects-toggle]').forEach(function (btn) {\n"
        "      btn.textContent = on ? '关闭特效' : '开启特效';\n"
        "      btn.addEventListener('click', function () {\n"
        "        on = !document.documentElement.classList.contains('lm-effects');\n"
        "        document.documentElement.classList.toggle('lm-effects', on);\n"
        "        try { localStorage.setItem(KEY, on ? '1' : '0'); } catch (e) { /* ignore */ }\n"
        "        btn.textContent = on ? '关闭特效' : '开启特效';\n"
        "      });\n"
        "    });\n"
        "  }\n"
        "\n"
        "  document.addEventListener('DOMContentLoaded', function () {\n"
        "    initDensity(); initPalette(); initCopilot(); initKanban(); initProjector(); initRowLinks();\n"
        "    initPrefetch(); initEffects();\n"
        "  });\n",
    ),
])

# ── 4. 命令面板底部提示里加入特效开关 ──────────────────────────
patch('lab_manager/templates/lab_manager/inc/global_ui.html', [
    (
        "    <span data-lm-density-toggle role=\"button\" tabindex=\"0\">{% trans \"切换表格密度\" %}</span>\n",
        "    <span data-lm-density-toggle role=\"button\" tabindex=\"0\">{% trans \"切换表格密度\" %}</span> ·\n"
        "    <span data-lm-effects-toggle role=\"button\" tabindex=\"0\">{% trans \"特效\" %}</span>\n",
    ),
])

# ── 5. 首屏内联脚本：尽早读取特效开关，避免闪一下动画 ──────────
patch('templates/base/layout.html', [
    (
        "  <script>document.body&&document.body.classList.add('tp-body')</script>\n",
        "  <script>\n"
        "    document.body && document.body.classList.add('tp-body');\n"
        "    // 尽早应用\"特效\"开关（默认关闭全屏无限动画，保证滚动与翻页跟手）\n"
        "    try {\n"
        "      if (localStorage.getItem('lm_effects') === '1') {\n"
        "        document.documentElement.classList.add('lm-effects');\n"
        "      }\n"
        "    } catch (e) { /* localStorage 不可用时保持默认 */ }\n"
        "  </script>\n",
    ),
])

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
