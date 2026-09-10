"""解析 DEBUG 技术 500 页面，提取异常与关键栈帧。"""
import glob
import os
import re
import sys
from html import unescape

HERE = os.path.dirname(os.path.abspath(__file__))
ERRDIR = os.path.join(HERE, 'errors')

for path in sorted(glob.glob(os.path.join(ERRDIR, '*.html'))):
    html = open(path, encoding='utf-8', errors='replace').read()
    print('=' * 100)
    print('FILE:', os.path.basename(path), f'({len(html)} bytes)')
    title = re.search(r'<title>(.*?)</title>', html, re.S)
    print('TITLE:', unescape(title.group(1)).strip() if title else '?')
    # 异常类型与消息
    m = re.search(r'<h2>(.*?)</h2>', html, re.S)
    if m:
        print('EXC  :', unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()[:400])
    # 请求路径
    m = re.search(r'<th>Request URL:</th>\s*<td>(.*?)</td>', html, re.S)
    if m:
        print('URL  :', re.sub(r'<[^>]+>', '', m.group(1)).strip()[:200])
    # 栈帧里的本地文件与代码行
    frames = re.findall(
        r'<div class="context" id="[^"]*">(.*?)</div>\s*</div>', html, re.S)
    # 更稳妥：抓取所有 filename + lineno
    locs = re.findall(r'<span class="filename">(.*?)</span>.*?<span class="lineno">(\d+)</span>', html, re.S)
    seen = []
    for fn, ln in locs:
        fn_clean = unescape(re.sub(r'<[^>]+>', '', fn)).strip()
        if 'lab_manager' in fn_clean or 'netbox' in fn_clean.lower():
            seen.append(f'{fn_clean}:{ln}')
    if seen:
        print('FRAMES (last 12):')
        for s in seen[-12:]:
            print('   ', s)
    # 异常所在代码行
    for m in re.finditer(r'<pre class="exception_value">(.*?)</pre>', html, re.S):
        print('VALUE:', unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()[:300])
    print()
