"""修正 3：局部换页后重新绑定内容区按钮（密度/特效/行点击），并保证重复初始化幂等。"""
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
    # 密度切换：幂等绑定（局部换页后会再调用一次）
    (
        "    qsa('[data-lm-density-toggle]').forEach(function (btn) {\n"
        "      btn.addEventListener('click', function () {\n",
        "    qsa('[data-lm-density-toggle]').forEach(function (btn) {\n"
        "      if (btn.dataset.lmBound === '1') return;   // 幂等：局部换页会再次初始化\n"
        "      btn.dataset.lmBound = '1';\n"
        "      btn.addEventListener('click', function () {\n",
    ),
    # 特效开关：幂等绑定
    (
        "    qsa('[data-lm-effects-toggle]').forEach(function (btn) {\n"
        "      btn.textContent = on ? '关闭特效' : '开启特效';\n"
        "      btn.addEventListener('click', function () {\n",
        "    qsa('[data-lm-effects-toggle]').forEach(function (btn) {\n"
        "      btn.textContent = on ? '关闭特效' : '开启特效';\n"
        "      if (btn.dataset.lmBound === '1') return;   // 幂等\n"
        "      btn.dataset.lmBound = '1';\n"
        "      btn.addEventListener('click', function () {\n",
    ),
    # 行点击：幂等绑定
    (
        "    qsa('[data-lm-href]').forEach(function (el) {\n"
        "      el.style.cursor = 'pointer';\n",
        "    qsa('[data-lm-href]').forEach(function (el) {\n"
        "      if (el.dataset.lmBound === '1') return;    // 幂等\n"
        "      el.dataset.lmBound = '1';\n"
        "      el.style.cursor = 'pointer';\n",
    ),
    # 换页后重新绑定内容区交互（这是局部导航最容易漏掉的一步）
    (
        "      initRowLinks(); initKanban();\n"
        "    });\n",
        "      initDensity(); initEffects(); initRowLinks(); initKanban();\n"
        "    });\n",
    ),
])

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !! {f}')
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
