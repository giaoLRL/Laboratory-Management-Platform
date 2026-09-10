"""确认通知页为什么没有渲染分页器。"""
import os
import re
import sys

import django

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

import requests  # noqa: E402

BASE = 'http://127.0.0.1:8001'
s = requests.Session()
r = s.get(f'{BASE}/login/', timeout=20)
tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text).group(1)
s.post(f'{BASE}/login/', data={'username': 'admin', 'password': 'Lab-Manager@2026',
                               'csrfmiddlewaretoken': tok, 'next': '/plugins/lab-manager/'},
       headers={'Referer': BASE + '/login/'}, timeout=30)

html = s.get(f'{BASE}/plugins/lab-manager/notifications/', timeout=30).text
for marker in ['lm-paginator', 'per_page', '暂无通知', 'lm-empty', '共 <strong>', 'notification']:
    print(f'  {marker!r}: {html.count(marker)}')
i = html.find('暂无通知')
print('\n空状态附近 HTML:')
print(re.sub(r'\s+', ' ', html[max(0, i - 400):i + 400]))
