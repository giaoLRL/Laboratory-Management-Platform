"""批次5 回归验证：会话删除 / 打卡表单 / 统计卡 / 导出 / N+1 / debug toolbar。"""
import io
import json
import os
import re
import subprocess
import sys

import django

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

import requests  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.db import connection  # noqa: E402
from django.test import Client  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from lab_manager.models import AgentConversation, AgentMessage, Hardware  # noqa: E402

BASE = 'http://127.0.0.1:8001'
U = get_user_model()
admin = U.objects.get(username='admin')
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


s_admin = login('admin', 'Lab-Manager@2026')
CSRF = s_admin.cookies.get('csrftoken')

print('== 1. 智能体会话删除（P1-3）==')
qa, _ = U.objects.get_or_create(username='qa_b5', defaults={'email': 'q5@example.com'})
qa.set_password('Qa-B5@2026'); qa.is_superuser = False; qa.save()
conv = AgentConversation.objects.create(user=qa, title='QA-B5 会话')
AgentMessage.objects.create(conversation=conv, role='user', content='hi')
try:
    s_qa = login('qa_b5', 'Qa-B5@2026')
    csrf_qa = s_qa.cookies.get('csrftoken')
    r = s_qa.post(f'{BASE}/plugins/lab-manager/agent-conversation/{conv.pk}/delete/',
                  headers={'X-CSRFToken': csrf_qa, 'Referer': BASE + '/plugins/lab-manager/agent/'}, timeout=20)
    check('会话归属者删除 -> 200', r.status_code == 200 and r.json().get('ok') is True,
          f'HTTP {r.status_code} {r.text[:60]}')
    check('会话与其消息已删除', not AgentConversation.objects.filter(pk=conv.pk).exists())
    conv2 = AgentConversation.objects.create(user=qa, title='QA-B5 会话2')
    r2 = s_admin.post(f'{BASE}/plugins/lab-manager/agent-conversation/{conv2.pk}/delete/',
                      headers={'X-CSRFToken': CSRF, 'Referer': BASE + '/plugins/lab-manager/agent/'}, timeout=20)
    check('他人（超管也不越权）删除 -> 404', r2.status_code == 404, f'HTTP {r2.status_code}')
    conv2.delete()
finally:
    AgentConversation.objects.filter(user=qa).delete()

print('== 2. 打卡表单（P1-2）==')
html = s_admin.get(f'{BASE}/plugins/lab-manager/checkins/new/', timeout=20).text
check('渲染了 tags 字段', 'name="tags"' in html, f"name=tags 出现 {html.count('name=\"tags\"')} 次")
check('提交条件包含照片校验', 'photoInput' in html and 'hasPhoto' in html)

print('== 3. 首页统计卡无 JS 也显示真实值（P1-4）==')
home = s_admin.get(f'{BASE}/plugins/lab-manager/', timeout=20).text
hw_total = str(Hardware.objects.count())
check(f'统计卡直接渲染数值（硬件总数={hw_total}）',
      f'data-target="{hw_total}">{hw_total}</h3>' in home,
      re.findall(r'data-target="\d+">[^<]*</h3>', home)[:3])

print('== 4. 导出命令支持新类型（P1-5）==')
env = dict(os.environ, DJANGO_SETTINGS_MODULE='netbox.settings')
outdir = r'C:\Users\PC\Documents\实验室\reports\qa'
for model in ['borrow_records', 'projects', 'hardware']:
    p = subprocess.run([sys.executable, 'manage.py', 'export_lab_data', '--model', model],
                       capture_output=True, text=True, timeout=180, env=env, cwd=os.getcwd())
    ok = p.returncode == 0
    check(f'--model {model} 执行成功', ok, (p.stdout or p.stderr).strip().splitlines()[-1][:70] if (p.stdout or p.stderr) else '')
for f in os.listdir(os.getcwd()):
    if f.startswith('lab_') and f.endswith('.csv'):
        os.remove(os.path.join(os.getcwd(), f))

print('== 5. 成员列表查询次数（P1-8 消除 N+1）==')
c = Client()
c.force_login(admin)
with CaptureQueriesContext(connection) as ctxq:
    resp = c.get('/plugins/lab-manager/members/')
n_queries = len(ctxq.captured_queries)
check('成员列表 200', resp.status_code == 200)
check('查询次数与成员数无关（<25）', n_queries < 25, f'实际 {n_queries} 次查询')

print('== 6. Debug Toolbar 已关闭（P1-7 / P1-9）==')
login_html = requests.get(f'{BASE}/login/', timeout=20).text
check('登录页无 djdt 面板', 'djdt' not in login_html and 'AlertsPanel' not in login_html)
p = subprocess.run([sys.executable, 'manage.py', 'test', 'lab_manager', '--keepdb'],
                   capture_output=True, text=True, timeout=300, env=env, cwd=os.getcwd())
check('manage.py test 不再因 debug_toolbar 报错',
      'debug_toolbar.E001' not in (p.stdout + p.stderr),
      (p.stdout + p.stderr).strip().splitlines()[-1][:80] if (p.stdout or p.stderr) else '')

U.objects.filter(username='qa_b5').delete()
bad = [r for r in results if not r[1]]
print(f'\n总计 {len(results)} 项，通过 {len(results) - len(bad)}，失败 {len(bad)}')
for n, _, d in bad:
    print('   FAIL:', n, d)
sys.exit(1 if bad else 0)
