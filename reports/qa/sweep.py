"""lab_manager 插件动态 HTTP 扫描。

- 管理员会话全量 GET 扫描（并在 DEBUG 下捕获 500 技术页/traceback）
- 匿名会话对照扫描（权限/登录跳转）
- 页面内链接爬取（发现路由表之外的页面）
- 错误响应落盘，结果写 JSON

用法（工作目录 netbox-main/netbox）：
    ..\\venv\\Scripts\\python.exe <此脚本绝对路径>
"""
import json
import os
import re
import sys
import time
from collections import Counter

import django

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

import requests  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402

BASE = 'http://127.0.0.1:8001'
HERE = os.path.dirname(os.path.abspath(__file__))
ERRDIR = os.path.join(HERE, 'errors')
os.makedirs(ERRDIR, exist_ok=True)

ADMIN_USER, ADMIN_PASS = 'admin', 'Lab-Manager@2026'


# ── 1. 收集 URL ────────────────────────────────────────────
with open(os.path.join(HERE, 'plugin_urls.json'), encoding='utf-8') as f:
    raw = json.load(f)

# 去掉 DRF format-suffix 与正则残留
urls = sorted({r['url'] for r in raw if 'drf_format_suffix' not in r['pattern']})
urls = [u for u in urls if '\\.' not in u and not re.search(r'[\\^$()?*]', u)]

# ── 2. 为 <int:pk> 找真实主键 ──────────────────────────────
from lab_manager.models import (  # noqa: E402
    AgentConversation, AgentMessage, AgentTool, CheckInRecord, Hardware,
    HardwareBorrowRecord, HardwareImportBatch, LabProject, MemberOpenRecord,
    Notification, Task, TaskAttachment, TaskComment,
)

PK_SOURCE = [
    ('/attachments/', TaskAttachment),
    ('/notifications/', Notification),
    ('/member-open-records/', MemberOpenRecord),
    ('/checkins/', CheckInRecord),
    ('/borrow-records/', HardwareBorrowRecord),
    ('/projects/', LabProject),
    ('/agent-tools/', AgentTool),
    ('/members/', get_user_model()),
    ('/tasks/', Task),
    ('/hardware/', Hardware),
    ('/api/task-comments/', TaskComment),
    ('/api/task-attachments/', TaskAttachment),
    ('/api/checkin-records/', CheckInRecord),
    ('/api/member-open-records/', MemberOpenRecord),
    ('/api/import-batches/', HardwareImportBatch),
    ('/api/agent-tools/', AgentTool),
    ('/api/projects/', LabProject),
    ('/api/borrow-records/', HardwareBorrowRecord),
    ('/api/conversations/', AgentConversation),
    ('/api/messages/', AgentMessage),
    ('/api/tasks/', Task),
    ('/api/hardware/', Hardware),
]


def pk_for(url):
    for prefix, model in PK_SOURCE:
        if url.startswith('/plugins/lab-manager' + prefix):
            obj = model.objects.order_by('pk').first()
            if obj is not None:
                return obj.pk
    return 1


expanded = []
for u in urls:
    if '<int:pk>' in u:
        expanded.append(u.replace('<int:pk>', str(pk_for(u))))
    else:
        expanded.append(u)
expanded = sorted(set(expanded))

# ── 3. 登录 ────────────────────────────────────────────────
def login(username, password):
    s = requests.Session()
    r = s.get(f'{BASE}/login/', timeout=20)
    m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text)
    token = m.group(1) if m else s.cookies.get('csrftoken')
    r2 = s.post(
        f'{BASE}/login/',
        data={'username': username, 'password': password,
              'csrfmiddlewaretoken': token, 'next': '/plugins/lab-manager/'},
        headers={'Referer': f'{BASE}/login/'},
        timeout=30, allow_redirects=True,
    )
    return s, r2


results = []
anon_ct = Counter()
admin_ct = Counter()
err_bodies = {}


def fetch(session, url, label):
    t0 = time.time()
    try:
        r = session.get(BASE + url, timeout=30, allow_redirects=False)
    except Exception as e:  # noqa: BLE001
        return {'url': url, 'label': label, 'status': 'EXC', 'err': f'{type(e).__name__}: {e}',
                'ms': int((time.time() - t0) * 1000)}
    ms = int((time.time() - t0) * 1000)
    body = r.text if r.headers.get('content-type', '').startswith('text') or 'json' in r.headers.get('content-type', '') else ''
    sig = ''
    if r.status_code >= 500:
        m = re.search(r'<title>(.*?)</title>', body, re.S)
        sig = (m.group(1).strip() if m else '')[:300]
        m2 = re.search(r'(?:exception_value|Exception Value)[^<]*</td>\s*<td[^>]*>(.{0,400})', body, re.S)
        if m2:
            sig += ' || ' + re.sub(r'<[^>]+>', '', m2.group(1)).strip()[:400]
        err_bodies.setdefault(f'{label}_{r.status_code}_{url.strip("/").replace("/", "_")}.html', body)
    return {'url': url, 'label': label, 'status': r.status_code, 'len': len(body or ''),
            'ms': ms, 'sig': sig, 'loc': r.headers.get('Location', '')}


print(f'== 管理员会话扫描 {len(expanded)} 个 URL ==')
admin_session, login_resp = login(ADMIN_USER, ADMIN_PASS)
print(f'login POST status={login_resp.status_code} final={login_resp.url}')
for u in expanded:
    res = fetch(admin_session, u, 'admin')
    results.append(res)
    admin_ct[res['status']] += 1

print('== 匿名会话扫描 ==')
anon_session = requests.Session()
for u in expanded:
    res = fetch(anon_session, u, 'anon')
    results.append(res)
    anon_ct[res['status']] += 1

# ── 4. 页面内链接爬取（补充路由表外的页面）─────────────────
crawl_seed = [u for u in expanded if u.startswith('/plugins/lab-manager/') and '<' not in u]
found_links = set()
for u in crawl_seed:
    try:
        r = admin_session.get(BASE + u, timeout=30)
    except Exception:  # noqa: BLE001
        continue
    for href in re.findall(r'href="(/[^"#?]*)"', r.text):
        if href.startswith(('/plugins/lab-manager', '/dcim', '/api', '/user', '/account')) and href not in set(expanded):
            found_links.add(href)

extra = sorted(found_links)
print(f'== 路由表外新发现链接 {len(extra)} 个 ==')
for u in extra:
    res = fetch(admin_session, u, 'crawl')
    results.append(res)
    admin_ct[res['status']] += 1

# ── 5. 异常响应落盘 + 汇总 ─────────────────────────────────
for name, body in err_bodies.items():
    with open(os.path.join(ERRDIR, name), 'w', encoding='utf-8') as f:
        f.write(body or '')

out = os.path.join(HERE, 'sweep_results.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump({'generated': time.strftime('%Y-%m-%d %H:%M:%S'),
               'admin_status_counts': dict(admin_ct),
               'anon_status_counts': dict(anon_ct),
               'results': results,
               'crawl_discovered': extra}, f, ensure_ascii=False, indent=1)

print('\n===== 管理员会话 状态码分布 =====')
for k, v in sorted(admin_ct.items(), key=lambda x: str(x[0])):
    print(f'  {k}: {v}')
print('===== 匿名会话 状态码分布 =====')
for k, v in sorted(anon_ct.items(), key=lambda x: str(x[0])):
    print(f'  {k}: {v}')

print('\n===== 非 2xx/3xx（管理员） =====')
for r in results:
    if r['label'] != 'anon' and not (isinstance(r['status'], int) and 200 <= r['status'] < 400):
        print(f"  [{r['status']}] {r['url']}  {r.get('sig','')}")
print('\n===== 5xx 明细 =====')
for r in results:
    if isinstance(r['status'], int) and r['status'] >= 500:
        print(f"  {r['label']} {r['status']} {r['url']} :: {r.get('sig','')[:200]}")

print('\n===== 匿名可访问（200/204，未登录就能看） =====')
for r in results:
    if r['label'] == 'anon' and r['status'] == 200:
        print(f"  {r['url']}")

print(f'\n结果已写入: {out}')
