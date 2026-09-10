"""批次2 回归验证：媒体鉴权 / Agent API 鉴权与 CSRF / 文件类型校验 / SSRF。"""
import io
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
from django.core.exceptions import ValidationError  # noqa: E402
from netbox.plugins.utils import get_plugin_config  # noqa: E402

from lab_manager.models import CheckInRecord, Task, TaskAttachment  # noqa: E402
from lab_manager.services.web_search import WebSearchService  # noqa: E402
from lab_manager.validators import validate_attachment_type, validate_image_type  # noqa: E402

BASE = 'http://127.0.0.1:8001'
U = get_user_model()
admin = U.objects.get(username='admin')
huhan = U.objects.get(username='huhan')
TOKEN = get_plugin_config('lab_manager', 'agent_api_token', '')
OLD_TOKEN = 'lab-manager-internal-token-change-me'
results = []


def check(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('  PASS ' if ok else '  FAIL ') + name + (f'  {detail}' if detail else ''))


def login(u, p):
    s = requests.Session()
    r = s.get(f'{BASE}/login/', timeout=20)
    tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text).group(1)
    s.post(f'{BASE}/login/', data={'username': u, 'password': p, 'csrfmiddlewaretoken': tok,
                                   'next': '/plugins/lab-manager/'},
           headers={'Referer': f'{BASE}/login/'}, timeout=30)
    return s


print('== 1. 媒体文件鉴权（P0-5）==')
rec = CheckInRecord.objects.exclude(photo='').first()
path = rec.photo.name if rec else 'checkins/photos/DSC_0000085.jpg'
owner = rec.user.username if rec else '?'
print(f'   样例: {path}  归属={owner}')
r_anon = requests.get(f'{BASE}/media/{path}', timeout=20, allow_redirects=False)
check('匿名 -> 302 跳登录（不返回文件）', r_anon.status_code == 302 and '/login/' in r_anon.headers.get('Location', ''),
      f'实际 {r_anon.status_code} {r_anon.headers.get("Location", "")}')
s_admin = login('admin', 'Lab-Manager@2026')
check('超管 -> 200', s_admin.get(f'{BASE}/media/{path}', timeout=20).status_code == 200)

qa, _ = U.objects.get_or_create(username='qa_media', defaults={'email': 'qm@example.com'})
qa.set_password('Qa-Media@2026'); qa.is_superuser = False; qa.save()
try:
    s_other = login('qa_media', 'Qa-Media@2026')
    if rec and rec.user_id != qa.pk:
        st = s_other.get(f'{BASE}/media/{path}', timeout=20).status_code
        check('非归属成员访问他人打卡照片 -> 404', st == 404, f'实际 {st}')
    att = TaskAttachment.objects.first()
    if att:
        st_anon = requests.get(f'{BASE}/media/{att.file.name}', timeout=20, allow_redirects=False).status_code
        st_other = s_other.get(f'{BASE}/media/{att.file.name}', timeout=20).status_code
        check('任务附件：匿名 302 / 非归属成员 404',
              st_anon == 302 and st_other == 404, f'实际 anon={st_anon} member={st_other}')
        hw_img = None
        from lab_manager.models import Hardware
        h = Hardware.objects.exclude(image='').exclude(image__isnull=True).first()
        if h and h.image:
            st = s_other.get(f'{BASE}/media/{h.image.name}', timeout=20).status_code
            check('硬件图片：非归属成员按审批可见性判定', st in (200, 404), f'实际 {st}（审批状态={h.approval_status}）')
finally:
    U.objects.filter(username='qa_media').delete()

print('== 2. Agent API 鉴权（P0-4）==')
ep = f'{BASE}/plugins/lab-manager/api/agent/members/search/'
r = requests.post(ep, json={'keyword': ''}, headers={'X-Agent-Token': OLD_TOKEN, 'X-User-ID': str(admin.pk)}, timeout=20)
check('旧占位令牌 -> 401', r.status_code == 401, f'实际 {r.status_code}')
r = requests.post(ep, json={'keyword': ''}, headers={'X-Agent-Token': TOKEN, 'X-User-ID': str(admin.pk)}, timeout=20)
check('新令牌冒充超管 -> 403', r.status_code == 403, f'实际 {r.status_code} {r.text[:80]}')
r = requests.post(ep, json={'keyword': ''}, headers={'X-Agent-Token': TOKEN, 'X-User-ID': str(huhan.pk)}, timeout=20)
check('新令牌冒充普通成员 -> 200', r.status_code == 200, f'实际 {r.status_code}')
r = requests.post(f'{BASE}/plugins/lab-manager/api/agent/member-open-records/search/', json={},
                  headers={'X-Agent-Token': TOKEN, 'X-User-ID': str(admin.pk)}, timeout=20)
check('超管专属端点经令牌 -> 403', r.status_code == 403, f'实际 {r.status_code}')

print('== 3. 会话鉴权请求必须过 CSRF ==')
r = s_admin.post(ep, data=json.dumps({'keyword': ''}),
                 headers={'Content-Type': 'text/plain'}, timeout=20)
check('会话 + text/plain 无 CSRF -> 403', r.status_code == 403, f'实际 {r.status_code} {r.text[:70]}')
tok = s_admin.cookies.get('csrftoken')
r = s_admin.post(ep, data=json.dumps({'keyword': ''}),
                 headers={'Content-Type': 'application/json', 'X-CSRFToken': tok, 'Referer': BASE + '/'}, timeout=20)
check('会话 + 带 CSRF -> 200', r.status_code == 200, f'实际 {r.status_code}')

print('== 4. 文件类型校验（P1-6）==')


class FakeFile:
    def __init__(self, name):
        self.name = name


for name, fn, should_pass in [('a.png', validate_image_type, True), ('a.svg', validate_image_type, False),
                              ('a.html', validate_attachment_type, False), ('a.pdf', validate_attachment_type, True),
                              ('x.svg', validate_attachment_type, False)]:
    try:
        fn(FakeFile(name))
        ok = should_pass
        detail = '未拒绝'
    except ValidationError:
        ok = not should_pass
        detail = '已拒绝'
    check(f'{name} -> {"通过" if should_pass else "拒绝"}', ok, detail)

print('== 5. SSRF 防护（P2）==')
ws = WebSearchService()
for url, expect in [('http://127.0.0.1/admin', False), ('http://localhost/x', False),
                    ('http://169.254.169.254/latest/meta-data/', False), ('file:///etc/passwd', False),
                    ('http://10.0.0.1/', False), ('https://example.com/page', True)]:
    got = ws.is_safe_public_url(url)
    check(f'{url} -> {"允许" if expect else "拒绝"}', got == expect, f'实际 {got}')

print()
bad = [r for r in results if not r[1]]
print(f'总计 {len(results)} 项，通过 {len(results) - len(bad)}，失败 {len(bad)}')
for n, _, d in bad:
    print('   FAIL:', n, d)
sys.exit(1 if bad else 0)
