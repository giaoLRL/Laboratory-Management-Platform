"""代码级事实核对：信号注册、库存扣减、导出选项、未用校验器、鉴权网关等。

只读，不改任何项目文件。所有结论带 文件:行号。
"""
import os
import re

PLUGIN = r'C:\Users\PC\Documents\实验室\netbox-main\netbox\lab_manager'
NETBOX = r'C:\Users\PC\Documents\实验室\netbox-main\netbox'


def read(p):
    try:
        return open(p, encoding='utf-8', errors='replace').read()
    except OSError:
        return ''


def show(title):
    print()
    print('=' * 92)
    print('==', title)


def grepline(roots, pattern, exts=('.py', '.html'), label=''):
    hits = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in {'__pycache__', 'node_modules', '.git'}]
            for fn in filenames:
                if not fn.endswith(exts):
                    continue
                p = os.path.join(dirpath, fn)
                for i, line in enumerate(read(p).splitlines(), 1):
                    if re.search(pattern, line):
                        rel = os.path.relpath(p, NETBOX)
                        hits.append(f'{rel}:{i}: {line.strip()[:150]}')
    print(f'   命中 {len(hits)} 处' + (f'  [{label}]' if label else ''))
    for h in hits[:25]:
        print('   ', h)
    if len(hits) > 25:
        print(f'    ...（其余 {len(hits) - 25} 处省略）')
    return hits


show('A. signals 是否被注册（__init__.py 是否 import signals）')
print(read(os.path.join(PLUGIN, '__init__.py')))
sig = read(os.path.join(PLUGIN, 'signals.py'))
print('signals.py 中的接收器:')
for m in re.finditer(r'@receiver\(([^)]*)\)\s*\ndef\s+(\w+)', sig):
    print(f'   @receiver({m.group(1)}) -> def {m.group(2)}')
grepline([NETBOX], r'import\s+signals|from\s+\.\s*import\s+signals|from\s+lab_manager\s+import\s+signals', ('.py',), 'signals import')

show('B. Hardware.quantity 是否存在写路径（扣减库存）')
grepline([PLUGIN], r'quantity\s*(=|\+=|-=)|\.quantity\s*[-+]=|quantity\s*-\s*', ('.py',), 'quantity 赋值')

show('C. 通知创建点')
grepline([PLUGIN], r'Notification\.objects\.create|send_notification\(', ('.py',), 'Notification 创建')

show('D. export.html 选项 vs export_lab_data 命令 choices')
h = read(os.path.join(PLUGIN, 'templates', 'lab_manager', 'export.html'))
for m in re.finditer(r'<(option|input)[^>]*>', h):
    if 'model' in m.group(0) or 'value=' in m.group(0):
        print('   html:', m.group(0).strip()[:160])
cmd = [os.path.join(PLUGIN, 'management', 'commands', f) for f in os.listdir(os.path.join(PLUGIN, 'management', 'commands')) if f.endswith('.py')]
for p in cmd:
    src = read(p)
    m = re.search(r'choices\s*=\s*\[([^\]]*)\]', src)
    print(f'   {os.path.basename(p)}: choices={m.group(1) if m else "?"}')
    m2 = re.search(r"add_argument\('--model'[^)]*\)", src, re.S)
    if m2:
        print('      add_argument:', re.sub(r'\s+', ' ', m2.group(0))[:200])

show('E. OVERDUE 状态是否有赋值路径')
grepline([PLUGIN], r'OVERDUE|overdue', ('.py',), 'overdue')

show('F. tests 目录是否存在')
tp = os.path.join(PLUGIN, 'tests')
print('   tests 目录存在:', os.path.isdir(tp))
files = sorted(os.listdir(PLUGIN))
print('   插件根目录:', files)

show('G. validators 是否被使用')
grepline([PLUGIN], r'validate_image_type|validate_attachment_type|validate_file_size', ('.py',), 'validators')

show('H. agent_api 鉴权（token / X-User-ID）')
src = read(os.path.join(PLUGIN, 'api', 'agent_api.py'))
for m in re.finditer(r'.{0,120}(X-Agent-Token|X-User-ID|csrf_exempt|agent_api_token).{0,160}', src):
    print('   ', re.sub(r'\s+', ' ', m.group(0))[:270])

show('I. CreateTaskAPIView 的 deadline 解析')
i = src.find('class CreateTaskAPIView')
seg = src[i:i + 3000]
for m in re.finditer(r'.{0,80}(parse_date|combine|deadline).{0,120}', seg):
    print('   ', re.sub(r'\s+', ' ', m.group(0))[:220])

show('J. 视图权限覆写一览（has_permission / test_func）')
views = read(os.path.join(PLUGIN, 'views.py'))
for m in re.finditer(r'class\s+(\w+)\s*\(([^)]*)\)', views):
    cls, base = m.group(1), m.group(2)
    seg = views[m.end():m.end() + 1500]
    perm = 'is_authenticated' if 'is_authenticated' in seg[:1200] else ('is_superuser' if 'is_superuser' in seg[:1200] else '?')
    if any(k in cls for k in ['View', 'ListView']) and 'View' in cls:
        print(f'   {cls:42s} base={base[:45]:45s} 首段权限={perm}')
