"""修正 4：用 MutationObserver 监听内容区替换（不依赖 htmx 事件名）来重新绑定交互。"""
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
        "    // 换页后：重新执行内容区内联脚本 + 重新初始化组件\n"
        "    document.body.addEventListener('htmx:afterSwap', function () {\n"
        "      qsa('#page-content script').forEach(function (old) {\n"
        "        var s = document.createElement('script');\n"
        "        if (old.src) s.src = old.src; else s.textContent = old.textContent;\n"
        "        old.replaceWith(s);\n"
        "      });\n"
        "      initDensity(); initEffects(); initRowLinks(); initKanban();\n"
        "    });\n",
        "    // 换页后：重新执行内容区内联脚本 + 重新初始化组件\n"
        "    var rebind = function () {\n"
        "      qsa('#page-content script').forEach(function (old) {\n"
        "        var s = document.createElement('script');\n"
        "        if (old.src) s.src = old.src; else s.textContent = old.textContent;\n"
        "        old.replaceWith(s);\n"
        "      });\n"
        "      initDensity(); initEffects(); initRowLinks(); initKanban();\n"
        "    };\n"
        "    document.body.addEventListener('htmx:afterSwap', rebind);\n"
        "    document.body.addEventListener('htmx:afterSettle', rebind);\n"
        "    // 兜底：不依赖 htmx 的具体事件名/实现，直接观察内容区被替换\n"
        "    var content = document.getElementById('page-content');\n"
        "    if (content && window.MutationObserver) {\n"
        "      new MutationObserver(function (muts) {\n"
        "        for (var i = 0; i < muts.length; i++) {\n"
        "          if (muts[i].addedNodes && muts[i].addedNodes.length) { rebind(); return; }\n"
        "        }\n"
        "      }).observe(content, { childList: true });\n"
        "    }\n",
    ),
])

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
