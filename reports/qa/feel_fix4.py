"""侧栏局部导航（HTMX boost）：只替换内容区，侧栏 DOM 完全不动，因此不再有"菜单刷新"观感。"""
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


# ── 1. 侧栏容器开启 hx-boost，只换 #page-content ────────────────
patch('templates/base/layout.html', [
    (
        "    <aside class=\"navbar navbar-vertical navbar-expand-lg d-print-none\">\n",
        "    {# 侧栏局部导航：点击菜单只替换 #page-content，侧栏 DOM 不重建 #}\n"
        "    <aside class=\"navbar navbar-vertical navbar-expand-lg d-print-none\"\n"
        "           hx-boost=\"true\" hx-target=\"#page-content\" hx-select=\"#page-content\"\n"
        "           hx-swap=\"innerHTML show:window:top\" hx-push-url=\"true\">\n",
    ),
])

# ── 2. lm-ui.js：boost 白名单/黑名单 + 换页后重新初始化 ──────────
patch('lab_manager/static/lab_manager/lm-ui.js', [
    (
        "  document.addEventListener('DOMContentLoaded', function () {\n"
        "    initDensity(); initPalette(); initCopilot(); initKanban(); initProjector(); initRowLinks();\n"
        "    initPrefetch(); initEffects(); initSidebarScroll();\n"
        "  });\n",
        "  /* ── 9. 侧栏局部导航（HTMX boost 的守门与善后） ─────────────────\n"
        "     目标：点击左侧菜单时只替换内容区，侧栏 DOM 完全不动（不再\"菜单刷新\"）。\n"
        "     风险控制：对含内联脚本或文件上传的页面禁用 boost，退回整页跳转；\n"
        "             换页后重新执行内容区脚本并重新初始化交互组件。 ── */\n"
        "  var BOOST_BLOCKLIST = ['/agent/', '/checkins/new/', '/logout/', '/login/'];\n"
        "\n"
        "  function initBoost() {\n"
        "    if (!window.htmx) return;                       // 没有 HTMX 就保持普通跳转\n"
        "    if (!document.body.hasAttribute('hx-boost')) {\n"
        "      document.body.setAttribute('hx-boost', 'true');\n"
        "    }\n"
        "    // 给不能局部替换的链接关闭 boost\n"
        "    qsa('.navbar-vertical a[href], a[data-no-boost]').forEach(function (a) {\n"
        "      var href = a.getAttribute('href') || '';\n"
        "      var blocked = a.hasAttribute('data-no-boost') || a.target === '_blank'\n"
        "        || BOOST_BLOCKLIST.some(function (p) { return href.indexOf(p) !== -1; });\n"
        "      if (blocked) a.setAttribute('hx-boost', 'false');\n"
        "    });\n"
        "\n"
        "    // 用响应里的 <title> 更新标签页标题（hx-select 只取内容区，标题不在其中）\n"
        "    document.body.addEventListener('htmx:beforeSwap', function (e) {\n"
        "      var xhr = e.detail.xhr;\n"
        "      if (!xhr || !xhr.responseText) return;\n"
        "      var m = xhr.responseText.match(/<title>([\\s\\S]*?)<\\/title>/i);\n"
        "      if (m) document.title = m[1].trim();\n"
        "    });\n"
        "\n"
        "    // 换页后：重新执行内容区内联脚本 + 重新初始化组件\n"
        "    document.body.addEventListener('htmx:afterSwap', function () {\n"
        "      qsa('#page-content script').forEach(function (old) {\n"
        "        var s = document.createElement('script');\n"
        "        if (old.src) s.src = old.src; else s.textContent = old.textContent;\n"
        "        old.replaceWith(s);\n"
        "      });\n"
        "      initRowLinks(); initKanban();\n"
        "    });\n"
        "  }\n"
        "\n"
        "  document.addEventListener('DOMContentLoaded', function () {\n"
        "    initDensity(); initPalette(); initCopilot(); initKanban(); initProjector(); initRowLinks();\n"
        "    initPrefetch(); initEffects(); initSidebarScroll(); initBoost();\n"
        "  });\n",
    ),
])

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
