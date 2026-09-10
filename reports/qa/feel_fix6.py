"""修正 2：黑名单链接用捕获阶段拦截强制整页跳转；静音 htmx OOB 诊断（纯提示，无功能影响）。"""
import io
import os
import sys

BASE = r'C:\Users\PC\Documents\实验室\netbox-main\netbox'
APPLY = '--apply' in sys.argv
report, failures = [], []


def patch(rel, pairs):
    full = os.path.join(BASE, rel)
    src = io.open(full, encoding='utf-8').read()
    orig = src
    for old, new in pairs:
        n = src.count(old)
        if n != 1:
            failures.append(f'{rel}: 期望 1 次，实际 {n} 次 -> {old.strip().splitlines()[0][:56]!r}')
            continue
        src = src.replace(old, new)
        report.append(f'  ok {rel}: {old.strip().splitlines()[0][:54]}')
    if src != orig and APPLY:
        io.open(full, 'w', encoding='utf-8', newline='').write(src)


patch('lab_manager/static/lab_manager/lm-ui.js', [
    # 1) 捕获阶段拦截黑名单链接（htmx 在 DOMContentLoaded 已绑定 boost，改属性来不及）
    (
        "    // 给不能局部替换的链接关闭 boost\n"
        "    qsa('.navbar-vertical a[href], a[data-no-boost]').forEach(function (a) {\n"
        "      var href = a.getAttribute('href') || '';\n"
        "      var blocked = a.hasAttribute('data-no-boost') || a.target === '_blank'\n"
        "        || BOOST_BLOCKLIST.some(function (p) { return href.indexOf(p) !== -1; });\n"
        "      if (blocked) a.setAttribute('hx-boost', 'false');\n"
        "    });\n",
        "    // 给不能局部替换的链接关闭 boost\n"
        "    qsa('.navbar-vertical a[href], a[data-no-boost]').forEach(function (a) {\n"
        "      var href = a.getAttribute('href') || '';\n"
        "      var blocked = a.hasAttribute('data-no-boost') || a.target === '_blank'\n"
        "        || BOOST_BLOCKLIST.some(function (p) { return href.indexOf(p) !== -1; });\n"
        "      if (blocked) a.setAttribute('hx-boost', 'false');\n"
        "    });\n"
        "\n"
        "    // htmx 在 DOMContentLoaded 时已绑定 boost 监听（bubble 阶段），\n"
        "    // 因此黑名单必须在捕获阶段拦截，直接走整页跳转。\n"
        "    document.addEventListener('click', function (e) {\n"
        "      var a = e.target.closest && e.target.closest('a[href]');\n"
        "      if (!a) return;\n"
        "      var href = a.getAttribute('href') || '';\n"
        "      var blocked = a.hasAttribute('data-no-boost') || a.target === '_blank'\n"
        "        || BOOST_BLOCKLIST.some(function (p) { return href.indexOf(p) !== -1; });\n"
        "      if (!blocked) return;\n"
        "      e.stopPropagation();     // 阻止 htmx 局部替换\n"
        "      e.preventDefault();\n"
        "      window.location.href = a.href;\n"
        "    }, true);\n"
        "\n"
        "    // 只换内容区时，NetBox 的 OOB 片段（通知角标等）找不到目标会打印诊断，\n"
        "    // 属纯提示、不影响功能，这里精确静音，避免刷控制台。\n"
        "    var _consoleError = console.error;\n"
        "    console.error = function () {\n"
        "      var first = String((arguments && arguments[0]) || '');\n"
        "      if (first.indexOf('htmx:oobErrorNoTarget') !== -1) return;\n"
        "      return _consoleError.apply(console, arguments);\n"
        "    };\n",
    ),
])

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
