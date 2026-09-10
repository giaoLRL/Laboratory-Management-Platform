"""批次 UI-1c：修复三个回归（模板缺 static 载入、通知页分页器位置、看板接口被 DRF 路由吞掉）。"""
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
            failures.append(f'{rel}: 期望 1 次，实际 {n} 次 -> {old.strip().splitlines()[0][:66]!r}')
            continue
        src = src.replace(old, new)
        report.append(f'  ok {rel}: {old.strip().splitlines()[0][:64]}')
    if src != orig and APPLY:
        io.open(full, 'w', encoding='utf-8', newline='').write(src)


# 1) 浏览记录模板需要 {% load static %}（底部用了 {% static %}）
patch('lab_manager/templates/lab_manager/member_open_record_list.html', [
    ("{% load i18n humanize lm_ui %}", "{% load i18n humanize static lm_ui %}"),
])

# 2) 通知页分页器从 javascript block 移回内容区
patch('lab_manager/templates/lab_manager/notification_list.html', [
    (
        "        {% endif %}\n"
        "    </div>\n"
        "</div>\n"
        "{% endblock %}\n"
        "\n"
        "{% block javascript %}\n"
        "{% include 'lab_manager/inc/paginator.html' %}\n"
        "{% endblock %}\n",
        "        {% endif %}\n"
        "    </div>\n"
        "</div>\n"
        "{% if page_obj %}<div class=\"px-2\">{% include 'lab_manager/inc/paginator.html' %}</div>{% endif %}\n"
        "{% endblock %}\n",
    ),
])

# 3) 看板状态接口：避开 DRF 的 api/tasks/<pk>/ 路由
patch('lab_manager/urls.py', [
    (
        "    path('api/tasks/status/', views.TaskStatusUpdateView.as_view(), name='task_status_update'),\n",
        "    # 注意：不要放在 api/tasks/ 下，否则会被 DRF 的 api/tasks/<pk>/ 抢先匹配（POST → 405）\n"
        "    path('api/board/status/', views.TaskStatusUpdateView.as_view(), name='task_status_update'),\n",
    ),
])

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
