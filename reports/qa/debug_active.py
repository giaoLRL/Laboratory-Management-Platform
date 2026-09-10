"""对比两个页面的侧栏 HTML，定位"当前项高亮"到底是哪个元素/类。"""
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


def sidebar(html):
    i = html.find('navbar-vertical')
    j = html.find('</aside>', i)
    return html[i:j]


def active_bits(html):
    seg = sidebar(html)
    out = []
    for m in re.finditer(r'<a [^>]*>', seg):
        tag = m.group(0)
        if 'active' in tag or 'aria-current' in tag:
            href = re.search(r'href="([^"]*)"', tag)
            out.append((href.group(1) if href else '?', re.sub(r'\s+', ' ', tag)[:150]))
    for m in re.finditer(r'<li [^>]*class="[^"]*active[^"]*"[^>]*>', seg):
        out.append(('(li)', re.sub(r'\s+', ' ', m.group(0))[:120]))
    return out


for path in ['/plugins/lab-manager/', '/plugins/lab-manager/tasks/', '/plugins/lab-manager/tasks/board/',
             '/plugins/lab-manager/hardware/', '/plugins/lab-manager/mission-control/']:
    html = s.get(BASE + path, timeout=30).text
    print(f'=== {path} ===')
    for href, tag in active_bits(html):
        print(f'   {href:44s} {tag}')
