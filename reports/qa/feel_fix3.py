"""消除"侧栏每次切换都刷新"的观感：跨文档 View Transitions + 侧栏滚动位置保持。"""
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


def patch(rel, pairs):
    src = read(rel)
    orig = src
    for old, new in pairs:
        n = src.count(old)
        if n != 1:
            failures.append(f'{rel}: 期望 1 次，实际 {n} 次 -> {old.strip().splitlines()[0][:58]!r}')
            continue
        src = src.replace(old, new)
        report.append(f'  ok {rel}: {old.strip().splitlines()[0][:56]}')
    if src != orig:
        write(rel, src)


# ── 1. CSS：跨文档视图过渡，把侧栏/顶栏"钉住" ──────────────────
css = read('lab_manager/static/lab_manager/lm-components.css')
if 'view-transition-name' not in css:
    css = css.rstrip('\n') + """

/* ═══════════════════════════════════════════════════════════════
   页面切换观感：跨文档 View Transitions
   问题：每次跳转都是整页重载，侧栏会跟着重绘/重放过渡（含图标回弹），
        视觉上非常显眼，像"菜单在刷新"。
   做法：给侧栏与顶栏声明 view-transition-name —— 浏览器会把新旧页面的
        这两块视为同一元素并直接替换（animation:none），因此看起来"没动"；
        内容区只做一次很短的淡入淡出。
   兼容：不支持的浏览器自动退化为普通跳转，无副作用。
   ═══════════════════════════════════════════════════════════════ */
@view-transition { navigation: auto; }

.tp-page .navbar-vertical { view-transition-name: lm-sidebar; }
.tp-page .navbar.sticky-top { view-transition-name: lm-topbar; }

/* 侧栏/顶栏不做过渡 —— 视觉上完全静止 */
::view-transition-old(lm-sidebar),
::view-transition-new(lm-sidebar),
::view-transition-old(lm-topbar),
::view-transition-new(lm-topbar) {
  animation: none;
  mix-blend-mode: normal;
}

/* 内容区：短促交叉淡入（比整页闪白舒服得多） */
::view-transition-old(root) { animation: lm-vt-out 110ms ease-out both; }
::view-transition-new(root) { animation: lm-vt-in 150ms ease-out both; }
@keyframes lm-vt-out { to { opacity: 0; } }
@keyframes lm-vt-in { from { opacity: 0; } }

/* 有视图过渡时，不要再叠加 .page-wrapper 的淡入（避免双重动画） */
@supports (view-transition-name: none) {
  .tp-page .page-wrapper { animation: none; }
}

@media (prefers-reduced-motion: reduce) {
  ::view-transition-group(*),
  ::view-transition-old(*),
  ::view-transition-new(*) { animation: none !important; }
}
"""
    write('lab_manager/static/lab_manager/lm-components.css', css)
    report.append('  ok lm-components.css: 追加跨文档视图过渡（侧栏/顶栏钉住）')
else:
    report.append('  -- lm-components.css: 已含视图过渡，跳过')

# ── 2. lm-ui.js：保持侧栏滚动位置（长菜单不再每次跳回顶部）────────
patch('lab_manager/static/lab_manager/lm-ui.js', [
    (
        "  /* ── 7. 悬停预取：鼠标移到链接上就预取目标页，点击后命中缓存（导航更跟手） ── */\n",
        "  /* ── 6b. 侧栏滚动位置保持：整页跳转也不会把菜单弹回顶部 ── */\n"
        "  function initSidebarScroll() {\n"
        "    var nav = document.querySelector('.navbar-vertical .navbar-collapse, .navbar-vertical');\n"
        "    if (!nav) return;\n"
        "    var KEY = 'lm_sidebar_scroll';\n"
        "    try {\n"
        "      var saved = parseInt(sessionStorage.getItem(KEY) || '0', 10);\n"
        "      if (saved > 0) nav.scrollTop = saved;\n"
        "    } catch (e) { /* ignore */ }\n"
        "    window.addEventListener('pagehide', function () {\n"
        "      try { sessionStorage.setItem(KEY, String(nav.scrollTop || 0)); } catch (e) { /* ignore */ }\n"
        "    });\n"
        "  }\n"
        "\n"
        "  /* ── 7. 悬停预取：鼠标移到链接上就预取目标页，点击后命中缓存（导航更跟手） ── */\n",
    ),
    (
        "    initPrefetch(); initEffects();\n",
        "    initPrefetch(); initEffects(); initSidebarScroll();\n",
    ),
])

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
