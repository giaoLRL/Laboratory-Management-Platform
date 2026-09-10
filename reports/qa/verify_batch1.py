"""批次1 回归验证：逐条检查修复是否生效。"""
import inspect
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
from django.db import transaction  # noqa: E402
from django.utils import timezone  # noqa: E402

from lab_manager.models import (  # noqa: E402
    Hardware, HardwareBorrowRecord, Notification, Task,
)

BASE = 'http://127.0.0.1:8001'
TOKEN = 'lab-manager-internal-token-change-me'
U = get_user_model()
admin = U.objects.get(username='admin')
huhan = U.objects.get(username='huhan')
results = []


def check(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('  PASS ' if ok else '  FAIL ') + name + ('  ' + str(detail) if detail else ''))


def login(u, p):
    s = requests.Session()
    r = s.get(f'{BASE}/login/', timeout=20)
    tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text).group(1)
    s.post(f'{BASE}/login/', data={'username': u, 'password': p, 'csrfmiddlewaretoken': tok,
                                   'next': '/plugins/lab-manager/'},
           headers={'Referer': f'{BASE}/login/'}, timeout=30)
    return s


def csrf(s, path):
    r = s.get(BASE + path, timeout=20)
    m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text)
    return m.group(1) if m else ''


s_admin = login('admin', 'Lab-Manager@2026')

print('== 1. 借出模块（P0-1 / P0-3）==')
hw = Hardware.objects.filter(quantity__gte=2).first()
q0 = hw.quantity
rec = HardwareBorrowRecord.objects.create(
    hardware=hw, borrower=huhan, purpose='QA-FIX-1',
    expected_return_date=timezone.now() - timezone.timedelta(days=1),
)
hw.refresh_from_db()
check('借出后库存 -1', hw.quantity == q0 - 1, f'{q0} -> {hw.quantity}')
check('is_overdue 不再抛异常', rec.is_overdue is True, f'is_overdue={rec.is_overdue}')
check('借出详情页 200', s_admin.get(f'{BASE}/plugins/lab-manager/borrow-records/{rec.pk}/', timeout=20).status_code == 200)
check('借用人成员页 200', s_admin.get(f'{BASE}/plugins/lab-manager/members/{huhan.pk}/', timeout=20).status_code == 200)
check('归还页 200', s_admin.get(f'{BASE}/plugins/lab-manager/borrow-records/{rec.pk}/return/', timeout=20).status_code == 200)

tok = csrf(s_admin, f'/plugins/lab-manager/borrow-records/{rec.pk}/return/')
r = s_admin.post(f'{BASE}/plugins/lab-manager/borrow-records/{rec.pk}/return/',
                 data={'csrfmiddlewaretoken': tok, 'notes': 'QA 归还'},
                 headers={'Referer': f'{BASE}/plugins/lab-manager/borrow-records/{rec.pk}/return/'},
                 timeout=20, allow_redirects=False)
rec.refresh_from_db()
hw.refresh_from_db()
check('归还 POST 生效', r.status_code == 302 and rec.status == 'returned',
      f'status_code={r.status_code} record.status={rec.status}')
check('归还后库存回补', hw.quantity == q0, f'{hw.quantity} (期望 {q0})')

print('== 2. 不存在的对象 -> 404（P0-8）==')
for path, expect in [(f'{BASE}/plugins/lab-manager/borrow-records/999999/return/', 404),
                     (f'{BASE}/plugins/lab-manager/notifications/999999/read/', 404),
                     (f'{BASE}/plugins/lab-manager/tasks/999999/complete/', 404)]:
    st = s_admin.get(path, timeout=20, allow_redirects=False).status_code
    check(f'{path.split("lab-manager")[1]} -> {expect}', st == expect, f'实际 {st}')

print('== 3. 评论视图 GET -> 405（P0-8）==')
st = s_admin.get(f'{BASE}/plugins/lab-manager/tasks/1/comment/', timeout=20, allow_redirects=False).status_code
check('GET 评论 -> 405', st == 405, f'实际 {st}')

print('== 4. read-all 不再接受 GET（P0-11）==')
st = s_admin.get(f'{BASE}/plugins/lab-manager/notifications/read-all/', timeout=20, allow_redirects=False).status_code
check('GET read-all -> 405', st == 405, f'实际 {st}')
tok = csrf(s_admin, '/plugins/lab-manager/notifications/')
st = s_admin.post(f'{BASE}/plugins/lab-manager/notifications/read-all/',
                  data={'csrfmiddlewaretoken': tok}, headers={'Referer': BASE + '/plugins/lab-manager/notifications/'},
                  timeout=20, allow_redirects=False).status_code
check('POST read-all -> 302', st == 302, f'实际 {st}')

print('== 5. 日历参数容错（P0-12）==')
for q in ['?year=abc', '?year=99999', '?year=', '?year=2026&month=99']:
    st = s_admin.get(f'{BASE}/plugins/lab-manager/calendar/{q}', timeout=20).status_code
    check(f'/calendar/{q} -> 200', st == 200, f'实际 {st}')
st = s_admin.get(f'{BASE}/plugins/lab-manager/members/{huhan.pk}/?cal_year=abc', timeout=20).status_code
check('members?cal_year=abc -> 200', st == 200, f'实际 {st}')

print('== 6. Agent API 非法 JSON（P0-7）==')
for body in ['[]', '1', '"x"']:
    r = requests.post(f'{BASE}/plugins/lab-manager/api/agent/hardware/search/', data=body,
                      headers={'X-Agent-Token': TOKEN, 'X-User-ID': str(admin.pk), 'Content-Type': 'application/json'},
                      timeout=20)
    check(f'body={body} -> 400', r.status_code == 400, f'实际 {r.status_code}')

print('== 7. 批量操作按钮（P0-9）==')
html = s_admin.get(f'{BASE}/plugins/lab-manager/agent-tools/', timeout=20).text
check('formaction 不再是 None', 'formaction="None"' not in html,
      re.findall(r'formaction="[^"]*"', html)[:3])
st = s_admin.get(f'{BASE}/plugins/lab-manager/agent-tools/bulk-delete/', timeout=20, allow_redirects=False).status_code
check('bulk-delete 路由可达（不再 500）', st in (200, 302, 405), f'实际 {st}')

print('== 8. 信号已注册（P0-2）==')
n0 = Notification.objects.count()
try:
    with transaction.atomic():
        t = Task.objects.create(title='QA-FIX-SIGNAL', description='qa', created_by=admin, assigned_to=huhan)
        n1 = Notification.objects.count()
        check('新建任务 -> 产生 1 条通知', n1 - n0 == 1, f'{n0} -> {n1}')
        h = Hardware.objects.create(name='QA-FIX-HW', quantity=1, submitted_by=huhan,
                                    approval_status='approved')
        n2 = Notification.objects.count()
        check('新建硬件（已通过）不重复通知', n2 - n1 == 0, f'{n1} -> {n2}')
        h.approval_note = '改个备注'
        h.save()
        n3 = Notification.objects.count()
        check('状态未变化时保存不发通知', n3 - n2 == 0, f'{n2} -> {n3}')
        h.approval_status = 'rejected'
        h.save()
        n4 = Notification.objects.count()
        check('状态变化时发通知', n4 - n3 == 1, f'{n3} -> {n4}')
        raise RuntimeError('rollback')
except RuntimeError:
    pass
check('事务回滚后通知数不变', Notification.objects.count() == n0)

# 清理
HardwareBorrowRecord.objects.filter(purpose__startswith='QA-FIX').delete()
HardwareBorrowRecord.objects.filter(pk=rec.pk).delete()

print()
bad = [r for r in results if not r[1]]
print(f'总计 {len(results)} 项，通过 {len(results) - len(bad)}，失败 {len(bad)}')
for n, _, d in bad:
    print('   FAIL:', n, d)
sys.exit(1 if bad else 0)
