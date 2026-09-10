"""批次4 回归验证：工具参数归一化 / 非法输入 400 / 导入并发与校验 / 工具权限 / 消息分页。"""
import json
import os
import sys

import django

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

import requests  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402

from lab_manager.models import AgentMessage, AgentTool, Hardware, HardwareImportBatch  # noqa: E402
from lab_manager.services.tool_registry import execute_tool  # noqa: E402

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
    import re
    tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text).group(1)
    s.post(f'{BASE}/login/', data={'username': u, 'password': p, 'csrfmiddlewaretoken': tok,
                                   'next': '/plugins/lab-manager/'},
           headers={'Referer': f'{BASE}/login/'}, timeout=30)
    return s


s_admin = login('admin', 'Lab-Manager@2026')
CSRF = s_admin.cookies.get('csrftoken')


def post_json(path, payload):
    return s_admin.post(BASE + path, data=json.dumps(payload),
                        headers={'Content-Type': 'application/json', 'X-CSRFToken': CSRF,
                                 'Referer': BASE + '/'}, timeout=60)


print('== 1. 工具参数归一化（P0-6）==')
for key, val in [('filters', {'status': 'scrapped'}), ('filters_json', '{"status":"scrapped"}')]:
    raw = execute_tool('platform_query', admin, {'model': 'hardware', 'action': 'list_records',
                                                 'limit': 20, key: val})
    data = json.loads(raw)
    total = data.get('total')
    check(f'{key} 过滤生效', total == 1, f'total={total}（期望 1）')
raw = json.loads(execute_tool('platform_query', admin, {'model': 'hardware', 'action': 'get_record_detail',
                                                        'record_id': Hardware.objects.first().pk}))
check('record_id 归一化为 id', raw.get('item', {}).get('id') == Hardware.objects.first().pk,
      f"item={str(raw.get('item'))[:60]}")
raw = json.loads(execute_tool('platform_query', admin, {'model': 'hardware', 'filters_json': '{bad'}))
check('非法 JSON 返回明确错误', raw.get('ok') is False and 'JSON' in str(raw.get('error')),
      str(raw.get('error'))[:60])

print('== 2. 非法输入返回 400（P0-7）==')
r = post_json('/plugins/lab-manager/api/agent/platform/query/',
              {'model': 'hardware', 'filters': {'created__gte': 'abc'}, 'limit': 5})
check('非法日期过滤 -> 400', r.status_code == 400, f'实际 {r.status_code} {r.text[:80]}')
r = post_json('/plugins/lab-manager/api/agent/hardware/gap-analysis/', {'requirements': ['开发板']})
check('requirements 元素非对象 -> 400', r.status_code == 400, f'实际 {r.status_code} {r.text[:80]}')

print('== 3. 导入提交：并发保护与整批校验（P0-3/P1）==')
batch = HardwareImportBatch.objects.create(
    created_by=admin, source_type='json', status='validated',
    validated_payload={'valid_items': [{'name': 'QA-IMPORT-A', 'category': 'mcu', 'quantity': 2,
                                        'status': 'in_use'}]},
)
r1 = post_json('/plugins/lab-manager/api/agent/hardware/import/commit/',
               {'import_action': 'commit', 'confirm': True, 'batch_id': batch.batch_id})
created = Hardware.objects.filter(name='QA-IMPORT-A').count()
check('首次 commit 成功并入库', r1.status_code == 200 and created == 1,
      f'HTTP {r1.status_code} created={created}')
r2 = post_json('/plugins/lab-manager/api/agent/hardware/import/commit/',
               {'import_action': 'commit', 'confirm': True, 'batch_id': batch.batch_id})
check('重复 commit -> 409', r2.status_code == 409, f'实际 {r2.status_code}')
check('重复提交未重复入库', Hardware.objects.filter(name='QA-IMPORT-A').count() == 1,
      f"count={Hardware.objects.filter(name='QA-IMPORT-A').count()}")

bad_batch = HardwareImportBatch.objects.create(
    created_by=admin, source_type='json', status='validated',
    validated_payload={'valid_items': [
        {'name': 'QA-IMPORT-B', 'category': 'mcu', 'quantity': 1},
        {'name': 'QA-IMPORT-BAD', 'category': 'NOT_A_CATEGORY', 'quantity': 1},
    ]},
)
r3 = post_json('/plugins/lab-manager/api/agent/hardware/import/commit/',
               {'import_action': 'commit', 'confirm': True, 'batch_id': bad_batch.batch_id})
bad_batch.refresh_from_db()
check('含非法数据的批次 -> 422 且整批回滚',
      r3.status_code == 422 and Hardware.objects.filter(name='QA-IMPORT-B').count() == 0
      and bad_batch.status != 'imported',
      f'HTTP {r3.status_code} 已写入={Hardware.objects.filter(name="QA-IMPORT-B").count()} batch={bad_batch.status}')

print('== 4. 工具权限与成员隐私（P1-10）==')
inactive, _ = U.objects.get_or_create(username='qa_inactive', defaults={'email': 'qi@example.com'})
inactive.is_active = False
inactive.set_password('x')
inactive.save()
members = json.loads(execute_tool('find_members', admin, {'keyword': 'qa_inactive'}))
check('停用账号不出现在成员检索', members.get('total') == 0, f"total={members.get('total')}")

tool = AgentTool.objects.create(name='qa_super_tool', display_name='QA', tool_type='data_query',
                                execution_key='find_members', is_enabled=True, requires_superuser=True,
                                parameters_schema={}, default_args={})
try:
    qa_user, _ = U.objects.get_or_create(username='qa_member_tool', defaults={'email': 'qt@example.com'})
    qa_user.set_password('Qa-Tool@2026'); qa_user.is_superuser = False; qa_user.save()
    raw = json.loads(execute_tool('find_members', qa_user, {'keyword': ''}))
    check('requires_superuser 在直连路径生效', raw.get('ok') is False, str(raw.get('error'))[:60])
    raw_admin = json.loads(execute_tool('find_members', admin, {'keyword': ''}))
    check('管理员仍可调用', raw_admin.get('ok') is True, f"total={raw_admin.get('total')}")
    check('管理员结果含 email', 'email' in (raw_admin.get('members') or [{}])[0],
          str((raw_admin.get('members') or [{}])[0])[:60])
finally:
    tool.delete()
    U.objects.filter(username__in=['qa_inactive', 'qa_member_tool']).delete()

print('== 5. 智能体会话消息分页（P1-8）==')
conv_id = (AgentMessage.objects.order_by('-pk').values_list('conversation_id', flat=True).first())
r = s_admin.get(f'{BASE}/plugins/lab-manager/agent/?conversation={conv_id}', timeout=30)
check(f'长会话页面 200（conv={conv_id}）', r.status_code == 200, f'实际 {r.status_code}')

print()
print('== 清理 ==')
Hardware.objects.filter(name__startswith='QA-IMPORT-').delete()
HardwareImportBatch.objects.filter(batch_id__in=[batch.batch_id, bad_batch.batch_id]).delete()
print('   已清理导入测试数据')

bad = [r for r in results if not r[1]]
print(f'\n总计 {len(results)} 项，通过 {len(results) - len(bad)}，失败 {len(bad)}')
for n, _, d in bad:
    print('   FAIL:', n, d)
sys.exit(1 if bad else 0)
