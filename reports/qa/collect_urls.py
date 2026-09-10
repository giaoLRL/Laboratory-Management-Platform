"""枚举 lab_manager 插件的全部 URL 端点。

用法（工作目录必须是 netbox-main/netbox）：
    ..\\venv\\Scripts\\python.exe <此脚本绝对路径>
"""
import json
import os
import re
import sys

import django

# 脚本不在 manage.py 目录下，需把手动工作目录（netbox-main/netbox）加入 sys.path
sys.path.insert(0, os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

from django.urls import URLPattern, URLResolver, get_resolver  # noqa: E402

ROWS = []


def walk(patterns, prefix, in_lm, ns_chain):
    for p in patterns:
        if isinstance(p, URLResolver):
            ns = p.namespace or ''
            walk(
                p.url_patterns,
                prefix + str(p.pattern),
                in_lm or ns == 'lab_manager',
                ns_chain + ([ns] if ns else []),
            )
        else:
            if in_lm:
                ROWS.append({
                    'name': p.name,
                    'pattern': prefix + str(p.pattern),
                    'namespaces': '.'.join(ns_chain),
                    'module': getattr(p.callback, '__module__', ''),
                    'qualname': getattr(p.callback, '__qualname__', ''),
                })


walk(get_resolver().url_patterns, '', False, [])


def to_url(pattern):
    """把正则 pattern 粗化成可请求的具体 URL。"""
    s = pattern
    s = s.replace('^', '').replace('$', '')
    # 命名分组 → 占位值
    s = re.sub(r'\(\?P<(\w+)>\[0-9\]\+\)', '1', s)
    s = re.sub(r'\(\?P<\w+>\[[^\]]*\][^)]*\)', '1', s)
    s = re.sub(r'\(\?P<\w+>[^)]*\)', '1', s)
    # 匿名分组
    s = re.sub(r'\(\[0-9\]\+\)', '1', s)
    s = re.sub(r'\([^)]*\)', '1', s)
    s = s.replace('?', '')
    if not s.startswith('/'):
        s = '/' + s
    return s


for r in ROWS:
    r['url'] = to_url(r['pattern'])

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plugin_urls.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(ROWS, f, ensure_ascii=False, indent=1)

print(f'collected {len(ROWS)} lab_manager url patterns -> {out}')
for r in ROWS:
    print(f"{r['name']!s:42s} {r['url']}")
sys.stdout.flush()
