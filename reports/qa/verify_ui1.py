"""批次 UI-1 回归验证：分页/筛选/导出/命令面板/看板。"""
import json
import os
import re
import sys

import django

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

import requests  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402

from lab_manager.models import CheckInRecord, MemberOpenRecord, Notification, Task  # noqa: E402

BASE = 'http://127.0.0.1:8001'
U = get_user_model()
admin = U.objects.get(username='admin')
results = []


def check(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('  PASS ' if ok else '  FAIL ') + name + (f'  {detail}' if detail else ''))


s = requests.Session()
r = s.get(f'{BASE}/login/', timeout=20)
tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text).group(1)
s.post(f'{BASE}/login/', data={'username': 'admin', 'password': 'Lab-Manager@2026',
                               'csrfmiddlewaretoken': tok, 'next': '/plugins/lab-manager/'},
       headers={'Referer': BASE + '/login/'}, timeout=30)
CSRF = s.cookies.get('csrftoken')

print('== 1. 五个列表页分页（?per_page=1 强制多页）==')
for name, path, model in [('打卡记录', '/plugins/lab-manager/checkins/', CheckInRecord),
                          ('浏览记录', '/plugins/lab-manager/member-open-records/', MemberOpenRecord),
                          ('通知中心', '/plugins/lab-manager/notifications/', Notification),
                          ('成员列表', '/plugins/lab-manager/members/', U)]:
    total = model.objects.count()
    r = s.get(BASE + path + '?per_page=1', timeout=40)
    html = r.text
    rows = html.count('lm-table') and len(re.findall(r'<tbody', html))
    has_pager = 'lm-paginator' in html
    page_links = len(re.findall(r'\?page=\d+', html))
    detail = f'库内 {total} 条 / 状态 {r.status_code} / 分页器 {"Y" if has_pager else "N"} / page链接 {page_links}'
    check(f'{name} 已接入分页', r.status_code == 200 and (has_pager or total <= 1), detail)

print('== 2. 筛选 ==')
r = s.get(BASE + '/plugins/lab-manager/checkins/?username=huhan&date_from=2020-01-01&q=QA', timeout=30)
check('打卡筛选 200 且回填', r.status_code == 200 and 'value="huhan"' in r.text)
r = s.get(BASE + '/plugins/lab-manager/member-open-records/?target_type=checkin&date_from=2020-01-01', timeout=30)
check('浏览记录筛选 200', r.status_code == 200)
r = s.get(BASE + '/plugins/lab-manager/member-open-records/?username=不存在的用户xyz', timeout=30)
check('筛选无结果时显示空状态', r.status_code == 200 and 'lm-empty' in r.text)

print('== 3. CSV 导出 ==')
for path, label in [('/plugins/lab-manager/checkins/?export=csv', '打卡'),
                    ('/plugins/lab-manager/member-open-records/?export=csv', '浏览记录')]:
    r = s.get(BASE + path, timeout=40)
    ct = r.headers.get('Content-Type', '')
    cd = r.headers.get('Content-Disposition', '')
    check(f'{label} CSV 导出', r.status_code == 200 and 'text/csv' in ct and 'attachment' in cd,
          f'{ct} {cd[:40]}')

print('== 4. 命令面板索引 ==')
r = s.get(BASE + '/plugins/lab-manager/api/command-index/', timeout=30)
try:
    data = r.json()
    items = data.get('items', [])
except Exception:
    items = []
check('索引接口 200 且含导航项', r.status_code == 200 and len(items) > 15, f'{len(items)} 项')
groups = {i.get('group') for i in items}
check('索引包含动态对象', bool(groups & {'硬件', '任务', '我的任务'}), str(sorted(groups))[:60])

print('== 5. 任务看板 ==')
r = s.get(BASE + '/plugins/lab-manager/tasks/board/', timeout=30)
check('看板页 200', r.status_code == 200 and 'lm-kanban' in r.text)
task = Task.objects.first()
if task:
    old = task.status
    target = 'in_progress' if old != 'in_progress' else 'pending'
    r = s.post(BASE + '/plugins/lab-manager/api/board/status/',
               data=json.dumps({'pk': task.pk, 'status': target}),
               headers={'Content-Type': 'application/json', 'X-CSRFToken': CSRF, 'Referer': BASE + '/'}, timeout=30)
    task.refresh_from_db()
    check('拖拽改状态生效', r.status_code == 200 and task.status == target, f'{old} -> {task.status}')
    task.status = old
    task.save(update_fields=['status', 'last_updated'])
    r = s.post(BASE + '/plugins/lab-manager/api/board/status/',
               data=json.dumps({'pk': task.pk, 'status': 'not-a-status'}),
               headers={'Content-Type': 'application/json', 'X-CSRFToken': CSRF, 'Referer': BASE + '/'}, timeout=30)
    check('非法状态 -> 400', r.status_code == 400, f'实际 {r.status_code}')

print('== 6. 全站 UI 注入 ==')
html = s.get(BASE + '/plugins/lab-manager/', timeout=30).text
check('组件层 CSS 已注入', 'lm-components.css' in html)
check('命令面板与副驾驶已注入', 'lm-cmd' in html and 'lm-copilot' in html)
check('lm-ui.js 已注入', 'lm-ui.js' in html)

bad = [r for r in results if not r[1]]
print(f'\n总计 {len(results)} 项，通过 {len(results) - len(bad)}，失败 {len(bad)}')
for n, _, d in bad:
    print('   FAIL:', n, d)
sys.exit(1 if bad else 0)
