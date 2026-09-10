"""主要页面健康检查：状态码 + 侧栏存在性 + 关键组件标记。"""
import os
import re
import sys

import django

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

import requests  # noqa: E402

BASE = 'http://127.0.0.1:8001'
PAGES = [
    ('/plugins/lab-manager/', ['需要我处理', 'tp-stat-row']),
    ('/plugins/lab-manager/hardware/', ['lm-toolbar', 'data-lm-density-toggle', 'lm-waterline']),
    ('/plugins/lab-manager/tasks/', ['lm-toolbar']),
    ('/plugins/lab-manager/borrow-records/', ['lm-toolbar']),
    ('/plugins/lab-manager/projects/', ['lm-toolbar']),
    ('/plugins/lab-manager/agent-tools/', ['lm-toolbar']),
    ('/plugins/lab-manager/checkins/', ['lm-filters', 'lm-paginator', 'lm-table--cards']),
    ('/plugins/lab-manager/member-open-records/', ['lm-kpi-row', 'lm-paginator', 'lm-table--cards']),
    ('/plugins/lab-manager/members/', ['lm-paginator']),
    ('/plugins/lab-manager/notifications/', ['lm-paginator']),
    ('/plugins/lab-manager/calendar/', ['calendar']),
    ('/plugins/lab-manager/agent/', ['agent-shell', 'agent-message-list']),
    ('/plugins/lab-manager/tasks/board/', ['lm-kanban', 'data-lm-kanban']),
    ('/plugins/lab-manager/mission-control/', ['lm-mission', 'lm-heatmap', 'lm-todo', 'lm-kpi-row']),
    ('/plugins/lab-manager/design-system/', ['lm-kpi', 'lm-badge', 'lm-waterline', 'lm-empty', 'lm-skeleton']),
    ('/plugins/lab-manager/export/', ['export']),
    ('/plugins/lab-manager/my-tasks/', ['lm-']),
]

s = requests.Session()
r = s.get(f'{BASE}/login/', timeout=20)
tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text).group(1)
s.post(f'{BASE}/login/', data={'username': 'admin', 'password': 'Lab-Manager@2026',
                               'csrfmiddlewaretoken': tok, 'next': '/plugins/lab-manager/'},
       headers={'Referer': BASE + '/login/'}, timeout=30)

import re as _re

bad = 0
for path, markers in PAGES:
    resp = s.get(BASE + path, timeout=40)
    html = resp.text
    missing = [m for m in markers if m not in html]
    nav = 'navbar-vertical' in html
    flag = ''
    if resp.status_code != 200 or missing or not nav:
        flag = '  <<< 异常'
        bad += 1
    print(f'{resp.status_code}  {path:46s} 侧栏={nav} 缺失标记={missing}{flag}')
print()
print('异常页面数:', bad)
sys.exit(1 if bad else 0)
