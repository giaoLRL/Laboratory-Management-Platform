"""验证 borrow.py:83/91 的 AttributeError 影响面（借出详情/成员详情/归还/列表）。"""
import os
import re
import sys

import django

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

import requests  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402

from lab_manager.models import Hardware, HardwareBorrowRecord  # noqa: E402

BASE = 'http://127.0.0.1:8001'
U = get_user_model()
huhan = U.objects.get(username='huhan')


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


rec_pk = None
try:
    hw = Hardware.objects.first()
    rec = HardwareBorrowRecord.objects.create(hardware=hw, borrower=huhan, purpose='QA-归还测试')
    rec_pk = rec.pk
    print(f'测试借出记录 pk={rec_pk} status={rec.status} borrower={rec.borrower.username}')

    print()
    print('--- 模型属性直接调用 ---')
    try:
        print('   rec.is_overdue =', rec.is_overdue)
    except Exception as e:  # noqa: BLE001
        print(f'   rec.is_overdue 抛 {type(e).__name__}: {e}')
    try:
        rec.mark_returned(notes='qa')
        print('   mark_returned() 成功')
    except Exception as e:  # noqa: BLE001
        print(f'   mark_returned() 抛 {type(e).__name__}: {e}')

    admin = login('admin', 'Lab-Manager@2026')
    print()
    print('--- HTTP 实测（超管会话）---')
    checks = [
        ('借出记录列表', '/plugins/lab-manager/borrow-records/'),
        ('借出记录详情', f'/plugins/lab-manager/borrow-records/{rec_pk}/'),
        ('归还页面(GET)', f'/plugins/lab-manager/borrow-records/{rec_pk}/return/'),
        ('成员详情(借用人)', f'/plugins/lab-manager/members/{huhan.pk}/'),
        ('首页仪表板', '/plugins/lab-manager/'),
        ('借出记录编辑页', f'/plugins/lab-manager/borrow-records/{rec_pk}/edit/'),
    ]
    for name, path in checks:
        r = admin.get(BASE + path, timeout=30, allow_redirects=False)
        print(f'   {r.status_code}  {name:18s} {path}')

    # 归还页 GET 本身 500，拿不到 CSRF token；改从正常的列表页取 token
    tok = csrf(admin, '/plugins/lab-manager/borrow-records/')
    r = admin.post(BASE + f'/plugins/lab-manager/borrow-records/{rec_pk}/return/',
                   data={'csrfmiddlewaretoken': tok, 'notes': 'QA 归还备注'},
                   headers={'Referer': BASE + f'/plugins/lab-manager/borrow-records/{rec_pk}/return/'},
                   timeout=30, allow_redirects=False)
    rec.refresh_from_db()
    print(f'   POST 归还 -> {r.status_code}  归还后 status={rec.status} actual_return_date={rec.actual_return_date}')
finally:
    if rec_pk:
        HardwareBorrowRecord.objects.filter(pk=rec_pk).delete()
        print(f'\n已清理测试借出记录 pk={rec_pk}')
