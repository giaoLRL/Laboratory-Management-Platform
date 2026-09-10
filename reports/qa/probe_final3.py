"""补测 2：工具层返回解析 + 借出编辑被拒原因。"""
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
BASE = 'http://127.0.0.1:8001'

print('=' * 92)
print('== 工具层参数名验证（execute_tool 返回 JSON 字符串）')
for key, val in [('filters', {'status': 'scrapped'}), ('filters_json', json.dumps({'status': 'scrapped'})),
                 ('fields', ['id', 'name'])]:
    args = {'model': 'hardware', 'limit': 20, key: val}
    raw = tr.execute_tool('platform_query', admin, args)
    try:
        res = json.loads(raw)
    except Exception:  # noqa: BLE001
        print(f'   {key:14s} 原始返回: {str(raw)[:160]}')
        continue
    data = res.get('data') or {}
    items = data.get('items') or data.get('results') or []
    st = sorted({str(i.get('status')) for i in items if isinstance(i, dict)})
    print(f'   {key:14s} ok={res.get("ok")} total={data.get("total")} status={st} '
          f'字段数={len(items[0].keys()) if items and isinstance(items[0], dict) else 0} err={str(res.get("error"))[:60]}')

for key in ['id', 'record_id']:
    args = {'model': 'hardware', 'action': 'get_record_detail', key: Hardware.objects.first().pk}
    raw = tr.execute_tool('platform_query', admin, args)
    try:
        res = json.loads(raw)
        print(f'   get_record_detail {key:10s} ok={res.get("ok")} err={str(res.get("error"))[:90]}')
    except Exception:  # noqa: BLE001
        print(f'   get_record_detail {key:10s} raw={str(raw)[:120]}')

print()
print('=' * 92)
print('== 借出编辑被拒的真实原因')


def s_login(u, p):
    s = requests.Session()
    r = s.get(f'{BASE}/login/', timeout=20)
    tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text).group(1)
    s.post(f'{BASE}/login/', data={'username': u, 'password': p, 'csrfmiddlewaretoken': tok,
                                   'next': '/plugins/lab-manager/'},
           headers={'Referer': f'{BASE}/login/'}, timeout=30)
    return s


qa, _ = U.objects.get_or_create(username='qa_member4', defaults={'email': 'qa4@example.com'})
qa.set_password('Qa-Member@2026'); qa.is_superuser = False; qa.save()
huhan = U.objects.get(username='huhan')
rec = HardwareBorrowRecord.objects.create(hardware=Hardware.objects.first(), borrower=huhan,
                                         purpose='QA-IDOR2', notes='ORIGINAL')
try:
    s = s_login('qa_member4', 'Qa-Member@2026')
    r = s.get(f'{BASE}/plugins/lab-manager/borrow-records/{rec.pk}/edit/', timeout=30)
    tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text)
    # 打印页面里所有 input/select 的 name + 当前值，弄清表单到底要什么
    print('   表单控件:')
    for m in re.finditer(r'<(input|select|textarea)[^>]*name="(\w+)"[^>]*>', r.text):
        tag = m.group(0)
        val = re.search(r'value="([^"]*)"', tag)
        print(f'      {m.group(1):8s} {m.group(2):22s} value={val.group(1) if val else ""}')
    data = {'csrfmiddlewaretoken': tok.group(1), 'hardware': str(rec.hardware_id),
            'borrower': str(huhan.pk), 'status': 'borrowed', 'notes': 'HACKED-BY-QA'}
    r2 = s.post(f'{BASE}/plugins/lab-manager/borrow-records/{rec.pk}/edit/', data=data,
                headers={'Referer': f'{BASE}/plugins/lab-manager/borrow-records/{rec.pk}/edit/'},
                timeout=30, allow_redirects=False)
    rec.refresh_from_db()
    print(f'   POST={r2.status_code} notes->{rec.notes!r}')
    alerts = [re.sub(r'<[^>]+>', '', a).strip()[:160] for a in
              re.findall(r'<div class="alert[^"]*"[^>]*>(.*?)</div>', r2.text, re.S)]
    print('   页面提示:', [a for a in alerts if a][:4])
    errs = [re.sub(r'<[^>]+>', '', e).strip()[:120] for e in
            re.findall(r'<div class="invalid-feedback[^"]*">(.*?)</div>', r2.text, re.S)]
    print('   字段错误:', [e for e in errs if e][:5])
    # 对照：超管做同样的 POST
    sa = s_login('admin', 'Lab-Manager@2026')
    ra = sa.get(f'{BASE}/plugins/lab-manager/borrow-records/{rec.pk}/edit/', timeout=30)
    toka = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', ra.text)
    r3 = sa.post(f'{BASE}/plugins/lab-manager/borrow-records/{rec.pk}/edit/',
                 data={'csrfmiddlewaretoken': toka.group(1), 'hardware': str(rec.hardware_id),
                       'borrower': str(huhan.pk), 'status': 'borrowed', 'notes': 'CHANGED-BY-ADMIN'},
                 headers={'Referer': f'{BASE}/plugins/lab-manager/borrow-records/{rec.pk}/edit/'},
                 timeout=30, allow_redirects=False)
    rec.refresh_from_db()
    print(f'   超管 POST={r3.status_code} notes->{rec.notes!r}')
finally:
    HardwareBorrowRecord.objects.filter(pk=rec.pk).delete()
    U.objects.filter(username='qa_member4').delete()
    print('   已清理')
