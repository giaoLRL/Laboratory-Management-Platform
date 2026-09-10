"""针对性页面探测：批量操作入口、导入页、智能体控制台、打卡表单字段。"""
import os
import re
import sys

import django

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.test import Client  # noqa: E402
from django.urls import NoReverseMatch, reverse  # noqa: E402

admin = get_user_model().objects.filter(is_superuser=True).first()
c = Client()
c.force_login(admin)


def get(p):
    r = c.get(p)
    return r, r.content.decode('utf-8', 'replace')


print('#' * 90)
print('# 1. agent-tools 列表页的批量操作入口')
r, html = get('/plugins/lab-manager/agent-tools/')
print('status', r.status_code, 'len', len(html))
found = sorted(set(re.findall(r'[^\s"\']{0,50}bulk[^\s"\'<>]{0,60}', html)))
for s in found[:25]:
    print('   ', s)
print('   -- 页面里出现的 bulk 次数:', len(re.findall(r'bulk', html)))

print()
print('#' * 90)
print('# 2. 尝试 reverse 批量操作 URL 名')
for name in ['agenttool_bulk_delete', 'agenttool_bulk_edit', 'agenttool_list', 'agenttool_add']:
    try:
        print(f'   plugins:lab_manager:{name} -> {reverse("plugins:lab_manager:" + name)}')
    except NoReverseMatch as e:
        print(f'   plugins:lab_manager:{name} -> NoReverseMatch')

print()
print('#' * 90)
print('# 3. 全部 import 页面状态')
imports = [
    '/users/users/import/', '/users/groups/import/', '/users/tokens/import/',
    '/users/owners/import/', '/users/owner-groups/import/',
    '/extras/tags/import/', '/extras/custom-fields/import/', '/extras/custom-links/import/',
    '/extras/webhooks/import/', '/extras/event-rules/import/', '/extras/config-context-profiles/import/',
    '/extras/export-templates/import/', '/extras/saved-filters/import/',
    '/extras/notification-groups/import/', '/extras/journal-entries/import/',
    '/extras/custom-field-choices/import/', '/core/data-sources/import/',
    '/dcim/devices/import/', '/ipam/prefixes/import/',
    '/plugins/lab-manager/hardware/import/',
]
for p in imports:
    try:
        rr = c.get(p)
        tag = '' if rr.status_code < 500 else '   <== 500'
        print(f'   {rr.status_code}  {p}{tag}')
    except Exception as e:  # noqa: BLE001
        print(f'   EXC  {p}  {type(e).__name__}: {e}')

print()
print('#' * 90)
print('# 4. 智能体控制台：删除会话的 JS 目标 URL 是否存在')
r, html = get('/plugins/lab-manager/agent/')
print('agent console status', r.status_code)
for m in sorted(set(re.findall(r'agent-conversation[^\s"\')]*', html))):
    print('   JS/HTML 引用:', m)
try:
    print('   reverse agent_conversation_delete ->', reverse('plugins:lab_manager:agent_conversation_delete', args=[1]))
except NoReverseMatch:
    print('   reverse agent_conversation_delete -> NoReverseMatch（路由不存在）')
rr = c.post('/plugins/lab-manager/agent-conversation/1/delete/')
print('   POST /plugins/lab-manager/agent-conversation/1/delete/ ->', rr.status_code)

print()
print('# 5. 历史消息是否服务端渲染 Markdown')
from lab_manager.models import AgentConversation, AgentMessage  # noqa: E402
convs = AgentConversation.objects.all()[:5]
print('   会话数:', AgentConversation.objects.count(), ' 消息数:', AgentMessage.objects.count())
for conv in convs:
    msgs = conv.messages.all()
    print(f'   conv#{conv.pk} 消息 {msgs.count()} 条')
markdown_like = 0
for m in AgentMessage.objects.all()[:200]:
    if re.search(r'\*\*|^\|.*\||```|^- ', m.content or '', re.M):
        markdown_like += 1
print('   含 Markdown 语法的消息数:', markdown_like)
print('   AgentMessage 字段:', [f.name for f in AgentMessage._meta.fields])

print()
print('#' * 90)
print('# 6. 打卡表单字段')
r, html = get('/plugins/lab-manager/checkins/new/')
print('status', r.status_code)
names = re.findall(r'<(?:input|select|textarea)[^>]*name="([^"]+)"', html)
print('   表单字段:', sorted(set(names)))
print('   含 tags 字段?', any('tags' in n for n in names))
for m in re.findall(r'<button[^>]*id="submit-button"[^>]*>', html):
    print('   submit 按钮:', m)
print('   照片字段 required?', 'name="photo"' in html and 'required' in html)
