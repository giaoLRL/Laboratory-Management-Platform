"""核实：批量操作路由名、导入链接出处、历史消息渲染路径、打卡表单 JS 校验。"""
import os
import re
import sys

import django

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.test import Client  # noqa: E402
from django.urls import get_resolver  # noqa: E402

admin = get_user_model().objects.filter(is_superuser=True).first()
c = Client(raise_request_exception=False)
c.force_login(admin)

PLUGIN = r'C:\Users\PC\Documents\实验室\netbox-main\netbox\lab_manager'


def show(title):
    print()
    print('#' * 90)
    print('#', title)


show('1. 所有含 bulk 的已注册路由名（插件命名空间）')
names = []


def walk(resolver, ns=''):
    for key, val in resolver.reverse_dict.items():
        if isinstance(key, str):
            names.append((ns, key, val))


walk(get_resolver())
for ns, key, val in sorted(names):
    if 'bulk' in key and 'lab_manager' in str(ns):
        print(f'   ns={ns!r} name={key!r}')
bulk_all = sorted(k for _, k, _ in names if isinstance(k, str) and 'bulk' in k and 'agenttool' in k)
print('   含 agenttool+bulk 的名字:', bulk_all or '（无）')
print('   全部 lab_manager 命名空间下的名字数量:',
      len([1 for ns, k, _ in names if 'lab_manager' in str(ns)]))

show('2. agent-tools 列表页 bulk-action-buttons 容器内容')
r = c.get('/plugins/lab-manager/agent-tools/')
html = r.content.decode('utf-8', 'replace')
i = html.find('bulk-action-buttons')
print(re.sub(r'\s+', ' ', html[max(0, i - 400):i + 900]))

show('3. 17 个 import 链接出现在页面的什么位置')
i = html.find('/extras/tags/import/')
print(re.sub(r'\s+', ' ', html[max(0, i - 700):i + 150]))
print('   --- 这些链接是否在 <nav>/sidebar 内？就近查找容器 class ---')
seg = html[:i]
for m in list(re.finditer(r'<(nav|aside|div)[^>]*class="([^"]*)"[^>]*>', seg))[-6:]:
    print('   ', m.group(1), m.group(2)[:120])

show('4. 智能体控制台：历史消息渲染路径')
from lab_manager.models import AgentConversation, AgentMessage  # noqa: E402

target = None
for m in AgentMessage.objects.filter(role='assistant').order_by('-pk'):
    if re.search(r'\*\*|^\|.*\|', m.content or '', re.M):
        target = m
        break
if target:
    print(f'   选中消息 #{target.pk} conv={target.conversation_id} 长度={len(target.content)}')
    print('   原始内容片段:', repr(target.content[:160]))
    page = c.get(f'/plugins/lab-manager/agent/?conversation={target.conversation_id}')
    ph = page.content.decode('utf-8', 'replace')
    print('   页面状态:', page.status_code)
    # 该消息原文是否以转义后的原始 markdown 出现在 HTML 里
    snippet = target.content[:40]
    print('   原始 markdown 片段直接出现在 HTML 中?', snippet in ph)
    print('   该片段是否被 <strong> 包裹?', ('<strong>' in ph and snippet.replace('**', '') in ph))
    # 统计气泡
    print('   assistant 气泡数:', len(re.findall(r'agent-message-bubble assistant', ph)))
    print('   页面内 <table> 数:', len(re.findall(r'<table', ph)))
else:
    print('   未找到含 markdown 的 assistant 消息')

show('5. 打卡表单 JS 的提交按钮启用条件')
r = c.get('/plugins/lab-manager/checkins/new/')
h = r.content.decode('utf-8', 'replace')
for m in re.finditer(r'function\s+(\w+)\s*\([^)]*\)\s*\{', h):
    print('   函数:', m.group(1))
for m in re.finditer(r'[^\n]*(submitButton|submit-button)[^\n]*', h):
    line = m.group(0).strip()
    if line:
        print('   JS:', line[:160])
print('   --- 是否校验 photo ---')
print('   出现 photo.files:', 'photo.files' in h, '| 出现 files.length:', 'files.length' in h)

show('6. 导航菜单里指向 import 的入口')
from lab_manager.navigation.menu import *  # noqa: F401,F403,E402
import lab_manager.navigation.menu as menu_mod  # noqa: E402

src = open(os.path.join(PLUGIN, 'navigation', 'menu.py'), encoding='utf-8').read()
print('   menu.py 里 import 出现次数:', len(re.findall(r'import', src)))
