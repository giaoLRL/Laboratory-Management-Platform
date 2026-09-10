"""补测：工具层参数名、借出编辑越权 POST。"""
import inspect
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

import lab_manager.services.tool_registry as tr  # noqa: E402
from lab_manager.models import Hardware, HardwareBorrowRecord  # noqa: E402

U = get_user_model()
admin = U.objects.get(username='admin')
print('execute_tool 签名:', inspect.signature(tr.execute_tool))
print('TOOL_REGISTRY keys:', list(tr.TOOL_REGISTRY))

print()
print('=' * 92)
print('== 工具层：filters / filters_json 是否等效')
for key, val in [('filters', {'status': 'scrapped'}), ('filters_json', json.dumps({'status': 'scrapped'})),
                 ('fields', ['id', 'name']), ('fields_json', json.dumps(['id', 'name']))]:
    args = {'model': 'hardware', 'limit': 20, key: val}
    try:
        res = tr.execute_tool('platform_query', args=args, user=admin)
        data = res.get('data') if isinstance(res, dict) else None
        total = data.get('total') if isinstance(data, dict) else None
        items = (data.get('items') or data.get('results') or []) if isinstance(data, dict) else []
        st = sorted({str(i.get('status')) for i in items if isinstance(i, dict)})
        keys = sorted(items[0].keys()) if items and isinstance(items[0], dict) else []
        print(f'   {key:14s} ok={res.get("ok")} total={total} status={st} 首行字段数={len(keys)}')
        if not res.get('ok'):
            print('        error:', str(res.get('error'))[:120])
    except Exception as e:  # noqa: BLE001
        print(f'   {key:14s} 异常 {type(e).__name__}: {e}')

print()
print('== 工具层：get_record_detail 的 id / record_id')
for key in ['id', 'record_id']:
    args = {'model': 'hardware', 'action': 'get_record_detail', key: Hardware.objects.first().pk}
    try:
        res = tr.execute_tool('platform_query', args=args, user=admin)
        print(f'   {key:11s} ok={res.get("ok")} error={str(res.get("error"))[:100]}')
    except Exception as e:  # noqa: BLE001
        print(f'   {key:11s} 异常 {type(e).__name__}: {e}')

print()
print('=' * 92)
print('== 借出编辑越权 POST 复测')


def s_login(u, p):
    s = requests.Session()
    r = s.get('http://127.0.0.1:8001/login/', timeout=20)
    tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text).group(1)
    s.post('http://127.0.0.1:8001/login/', data={'username': u, 'password': p, 'csrfmiddlewaretoken': tok,
                                                 'next': '/plugins/lab-manager/'},
           headers={'Referer': 'http://127.0.0.1:8001/login/'}, timeout=30)
    return s


qa, _ = U.objects.get_or_create(username='qa_member3', defaults={'email': 'qa3@example.com'})
qa.set_password('Qa-Member@2026'); qa.is_superuser = False; qa.save()
rec = HardwareBorrowRecord.objects.create(hardware=Hardware.objects.first(), borrower=U.objects.get(username='huhan'),
                                         purpose='QA-IDOR', notes='ORIGINAL')
try:
    s = s_login('qa_member3', 'Qa-Member@2026')
    r = s.get(f'http://127.0.0.1:8001/plugins/lab-manager/borrow-records/{rec.pk}/edit/', timeout=30)
    tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text)
    data = {'csrfmiddlewaretoken': tok.group(1), 'hardware': str(rec.hardware_id),
            'borrower': str(rec.borrower_id), 'status': 'borrowed', 'notes': 'HACKED-BY-QA'}
    r2 = s.post(f'http://127.0.0.1:8001/plugins/lab-manager/borrow-records/{rec.pk}/edit/', data=data,
                headers={'Referer': f'http://127.0.0.1:8001/plugins/lab-manager/borrow-records/{rec.pk}/edit/'},
                timeout=30, allow_redirects=False)
    rec.refresh_from_db()
    print(f'   GET={r.status_code} POST={r2.status_code} location={r2.headers.get("Location", "")}')
    print(f'   notes: ORIGINAL -> {rec.notes!r}  >>> 越权{"成功（能改他人记录）" if rec.notes != "ORIGINAL" else "未生效"}')
    if r2.status_code == 200:
        errs = [re.sub(r'<[^>]+>', '', e).strip()[:90] for e in
                re.findall(r'<div class="invalid-feedback[^"]*">(.*?)</div>', r2.text, re.S)]
        print('   表单错误:', [e for e in errs if e][:5] or '（未捕获）')
        print('   alert 区块:', bool(re.search(r'alert-(danger|warning)', r2.text)))
finally:
    HardwareBorrowRecord.objects.filter(pk=rec.pk).delete()
    U.objects.filter(username='qa_member3').delete()
    print('   已清理')
