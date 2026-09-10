"""手感批次 2：把「特效」开关放到列表工具栏（可见），并收紧校验口径。"""
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
            failures.append(f'{rel}: 期望 1 次，实际 {n} 次 -> {old.strip().splitlines()[0][:58]!r}')
            continue
        src = src.replace(old, new)
        report.append(f'  ok {rel}: {old.strip().splitlines()[0][:56]}')
    if src != orig and APPLY:
        io.open(full, 'w', encoding='utf-8', newline='').write(src)


patch('lab_manager/templates/lab_manager/object_list.html', [(
    "        <button type=\"button\" class=\"btn btn-sm btn-outline-secondary\" data-lm-density-toggle\n"
    "                title=\"{% trans '切换表格密度（紧凑/舒适）' %}\" aria-pressed=\"false\">\n"
    "          <i class=\"mdi mdi-format-line-spacing\"></i> {% trans \"密度\" %}\n"
    "        </button>\n",
    "        <button type=\"button\" class=\"btn btn-sm btn-outline-secondary\" data-lm-density-toggle\n"
    "                title=\"{% trans '切换表格密度（紧凑/舒适）' %}\" aria-pressed=\"false\">\n"
    "          <i class=\"mdi mdi-format-line-spacing\"></i> {% trans \"密度\" %}\n"
    "        </button>\n"
    "        <button type=\"button\" class=\"btn btn-sm btn-outline-secondary\" data-lm-effects-toggle\n"
    "                title=\"{% trans '开启/关闭像素特效（默认关闭以保证流畅）' %}\">{% trans \"开启特效\" %}</button>\n",
)])

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
