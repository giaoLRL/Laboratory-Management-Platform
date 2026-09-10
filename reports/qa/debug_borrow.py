"""调试：成员借出登记 POST 为何未创建记录。"""
import os
import sys

import django

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.test import Client  # noqa: E402

from lab_manager.models import Hardware, HardwareBorrowRecord  # noqa: E402

U = get_user_model()
qa, _ = U.objects.get_or_create(username='qa_dbg', defaults={'email': 'd@example.com'})
qa.set_password('Qa-Dbg@2026'); qa.is_superuser = False; qa.save()
hw = Hardware.objects.filter(quantity__gte=3).first()
print('硬件', hw.pk, 'quantity=', hw.quantity)
try:
    c = Client(raise_request_exception=False)
    c.force_login(qa)
    r = c.post('/plugins/lab-manager/borrow-records/add/',
               {'hardware': hw.pk, 'purpose': 'QA-DBG2', 'notes': '', 'expected_return_date': ''})
    print('status:', r.status_code)
    ctx = r.context
    if ctx and 'form' in ctx:
        print('form errors:', dict(ctx['form'].errors))
        print('non-field:', ctx['form'].non_field_errors())
        print('instance:', ctx['form'].instance.pk, 'borrower:', getattr(ctx['form'].instance, 'borrower_id', None))
    else:
        print('context keys:', list(ctx.keys()) if ctx else None)
        print('redirect to:', r.headers.get('Location'))
    print('记录数:', HardwareBorrowRecord.objects.filter(purpose='QA-DBG2').count())
finally:
    HardwareBorrowRecord.objects.filter(purpose='QA-DBG2').delete()
    U.objects.filter(username='qa_dbg').delete()
