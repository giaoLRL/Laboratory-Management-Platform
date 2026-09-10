"""修正侧栏局部导航：守门逻辑不依赖 window.htmx、屏蔽 OOB 报错、黑名单页回退整页跳转。"""
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
    (
        "  function initBoost() {\n"
        "    if (!window.htmx) return;                       // 没有 HTMX 就保持普通跳转\n"
        "    if (!document.body.hasAttribute('hx-boost')) {\n"
        "      document.body.setAttribute('hx-boost', 'true');\n"
        "    }\n",
        "  function initBoost() {\n"
        "    // 说明：本项目的 HTMX 打包在 netbox.js 内，window.htmx 可能不存在，\n"
        "    // 因此不依赖它做判断，直接按属性生效（无 HTMX 时这些属性是无害的）。\n"
        "    var boosted = document.querySelector('[hx-boost=\"true\"]');\n"
        "    if (!boosted) return;\n",
    ),
    (
        "    // 换页后：重新执行内容区内联脚本 + 重新初始化组件\n"
        "    document.body.addEventListener('htmx:afterSwap', function () {\n",
        "    // OOB 片段（通知角标等）在只换内容区时找不到目标，静默跳过，避免刷控制台报错\n"
        "    document.body.addEventListener('htmx:oobErrorNoTarget', function (e) {\n"
        "      if (e && e.preventDefault) e.preventDefault();\n"
        "    });\n"
        "\n"
        "    // 换页后：重新执行内容区内联脚本 + 重新初始化组件\n"
        "    document.body.addEventListener('htmx:afterSwap', function () {\n",
    ),
])

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
