"""最后一轮定点实测：非法输入 500、日历 year 参数、LLM 工具参数名不匹配、借出编辑越权。"""
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

from lab_manager.models import Hardware, HardwareBorrowRecord  # noqa: E402

BASE = 'http://127.0.0.1:8001'
TOKEN = 'lab-manager-internal-token-change-me'
U = get_user_model()
admin = U.objects.get(username='admin')
huhan = U.objects.get(username='huhan')


def s_login(u, p):
    s = requests.Session()
    r = s.get(f'{BASE}/login/', timeout=20)
    tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text).group(1)
    s.post(f'{BASE}/login/', data={'username': u, 'password': p, 'csrfmiddlewaretoken': tok,
                                   'next': '/plugins/lab-manager/'},
           headers={'Referer': f'{BASE}/login/'}, timeout=30)
    return s


admin_s = s_login('admin', 'Lab-Manager@2026')
H = {'X-Agent-Token': TOKEN, 'X-User-ID': str(admin.pk), 'Content-Type': 'application/json'}

print('=' * 92)
print('== 1. Agent API 传入非对象 JSON（应当 400，实际？）')
for label, body in [('数组 []', '[]'), ('数字 1', '1'), ('字符串 "x"', '"x"'), ('对象{}', '{}')]:
    r = requests.post(f'{BASE}/plugins/lab-manager/api/agent/hardware/search/', data=body,
                      headers=H, timeout=30)
    print(f'   body={label:12s} -> {r.status_code} {r.text[:120]}')

print()
print('=' * 92)
print('== 2. platform/query 非法日期过滤（应当 400，实际？）')
payload = {'model': 'hardware', 'filters': {'created__gte': 'abc'}, 'limit': 5}
r = requests.post(f'{BASE}/plugins/lab-manager/api/agent/platform/query/',
                  data=json.dumps(payload), headers=H, timeout=30)
print(f'   -> {r.status_code} {r.text[:200]}')

print()
print('=' * 92)
print('== 3. requirements 元素类型错误')
payload = {'requirements': ['开发板']}
r = requests.post(f'{BASE}/plugins/lab-manager/api/agent/hardware/gap-analysis/',
                  data=json.dumps(payload), headers=H, timeout=30)
print(f'   -> {r.status_code} {r.text[:200]}')

print()
print('=' * 92)
print('== 4. 日历 year 参数非法（应当回退，实际？）')
for q in ['?year=abc', '?year=99999', '?year=']:
    r = admin_s.get(f'{BASE}/plugins/lab-manager/calendar/{q}', timeout=30, allow_redirects=False)
    print(f'   /calendar/{q:14s} -> {r.status_code}')
r = admin_s.get(f'{BASE}/plugins/lab-manager/members/{huhan.pk}/?cal_year=abc', timeout=30, allow_redirects=False)
print(f'   /members/<pk>/?cal_year=abc -> {r.status_code}')

print()
print('=' * 92)
print('== 5. LLM 工具参数名：filters_json vs filters（直连工具层，只读）')
from lab_manager.services.tool_registry import execute_tool  # noqa: E402

hw_fields = {'status': 'scrapped'}
for key in ['filters_json', 'filters', 'fields_json', 'fields']:
    args = {'model': 'hardware', 'limit': 20}
    args[key] = json.dumps(hw_fields) if key.endswith('_json') else hw_fields
    try:
        res = execute_tool('platform_query', args, user=admin)
        data = res.get('data', res) if isinstance(res, dict) else res
        total = None
        if isinstance(data, dict):
            total = data.get('total', data.get('count'))
            items = data.get('items') or data.get('results') or []
            statuses = sorted({str(i.get('status')) for i in items if isinstance(i, dict)})[:4]
        else:
            statuses = []
        print(f'   {key:14s} -> ok={res.get("ok") if isinstance(res, dict) else "?"} total={total} statuses={statuses} err={str(res.get("error"))[:60] if isinstance(res, dict) else ""}')
    except Exception as e:  # noqa: BLE001
        print(f'   {key:14s} -> 异常 {type(e).__name__}: {e}')

print()
print('== 5b. get_record_detail 的 id vs record_id')
for key in ['id', 'record_id']:
    args = {'model': 'hardware', key: Hardware.objects.first().pk}
    try:
        res = execute_tool('platform_query', args, user=admin)
        print(f'   args={key:10s} -> ok={res.get("ok") if isinstance(res, dict) else "?"} err={str(res.get("error"))[:80] if isinstance(res, dict) else ""}')
    except Exception as e:  # noqa: BLE001
        print(f'   args={key:10s} -> 异常 {type(e).__name__}: {e}')

print()
print('=' * 92)
print('== 6. 借出记录编辑越权复测（非归属用户 POST，检查表单错误）')
qa, _ = U.objects.get_or_create(username='qa_member2', defaults={'email': 'qa2@example.com'})
qa.set_password('Qa-Member@2026')
qa.is_superuser = False
qa.save()
rec = HardwareBorrowRecord.objects.create(hardware=Hardware.objects.first(), borrower=huhan,
                                         purpose='QA-EDIT-IDOR', notes='ORIGINAL')
try:
    qs = s_login('qa_member2', 'Qa-Member@2026')
    r = qs.get(f'{BASE}/plugins/lab-manager/borrow-records/{rec.pk}/edit/', timeout=30)
    print(f'   GET 他人编辑页 -> {r.status_code}')
    tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text)
    fields = dict(re.findall(r'<input[^>]*name="(\w+)"[^>]*value="([^"]*)"', r.text))
    sel = dict(re.findall(r'<select[^>]*name="(\w+)"', r.text))
    print('   input 字段:', sorted(fields), ' select 字段:', sorted(sel))
    data = {'csrfmiddlewaretoken': tok.group(1) if tok else '',
            'hardware': str(rec.hardware_id), 'borrower': str(huhan.pk),
            'status': 'borrowed', 'notes': 'HACKED-BY-QA', 'q': ''}
    r2 = qs.post(f'{BASE}/plugins/lab-manager/borrow-records/{rec.pk}/edit/', data=data,
                 headers={'Referer': f'{BASE}/plugins/lab-manager/borrow-records/{rec.pk}/edit/'},
                 timeout=30, allow_redirects=False)
    rec.refresh_from_db()
    print(f'   POST -> {r2.status_code} location={r2.headers.get("Location", "")}')
    print(f'   notes: ORIGINAL -> {rec.notes!r}   >>> 越权{"成功" if rec.notes != "ORIGINAL" else "未生效"}')
    if r2.status_code == 200:
        errs = re.findall(r'<div class="invalid-feedback[^"]*">(.*?)</div>', r2.text, re.S)
        errs = [re.sub(r'<[^>]+>', '', e).strip()[:80] for e in errs]
        print('   表单错误:', errs[:6] or '（未捕获到）')
        print('   是否含 alert-danger:', 'alert-danger' in r2.text)
finally:
    HardwareBorrowRecord.objects.filter(pk=rec.pk).delete()
    U.objects.filter(username='qa_member2').delete()
    print('   已清理测试记录与账号')
