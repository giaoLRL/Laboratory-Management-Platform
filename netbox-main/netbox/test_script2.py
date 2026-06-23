import os
import django
import sys
import json
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

from django.contrib.auth import get_user_model
from lab_manager.services.backend_agent_service import BackendAgentService
from lab_manager.services.dify_gateway import DifyGateway

try:
    User = get_user_model()
    user = User.objects.first()
    msg = '我想做一个智能温室监测系统，看看缺哪些硬件'
    res = BackendAgentService().process_message(user=user, message=msg)

    gw = DifyGateway()
    wf_res = gw.run_workflow(workflow_alias='site_workflow', parameters={'user_query': msg, 'hardware_items_str': res.answer_text}, user_id=str(user.pk))
    with open('debug_wf.json', 'w', encoding='utf-8') as f:
        json.dump(wf_res.payload, f, ensure_ascii=False, indent=2)
except Exception as e:
    with open('debug_wf.json', 'w', encoding='utf-8') as f:
        f.write(traceback.format_exc())

