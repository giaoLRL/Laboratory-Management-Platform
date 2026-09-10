"""最后一测：工具层 filters vs filters_json 原始输出对比。"""
import json
import os
import sys

import django

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

import lab_manager.services.tool_registry as tr  # noqa: E402

admin = get_user_model().objects.get(username='admin')
print('可用硬件状态分布:', list(
    __import__('lab_manager.models', fromlist=['Hardware']).Hardware.objects.values_list('status', flat=True)))

for key, val in [('filters', {'status': 'scrapped'}),
                 ('filters_json', json.dumps({'status': 'scrapped'}))]:
    raw = tr.execute_tool('platform_query', admin, {'model': 'hardware', 'action': 'list_records', 'limit': 20, key: val})
    s = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
    print(f'\n--- {key} ---')
    print(s[:700])

raw = tr.execute_tool('platform_query', admin, {'model': 'hardware', 'action': 'get_record_detail', 'id': 3})
print('\n--- get_record_detail id=3 ---')
print((raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False))[:500])
