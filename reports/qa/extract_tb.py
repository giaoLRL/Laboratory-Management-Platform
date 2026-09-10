"""更稳地从 DEBUG 500 页面提取栈帧（文件名/行号/代码行）。"""
import glob
import os
import re
from html import unescape

HERE = os.path.dirname(os.path.abspath(__file__))
ERRDIR = os.path.join(HERE, 'errors')


def clean(s):
    return unescape(re.sub(r'<[^>]+>', '', s)).strip()


for path in sorted(glob.glob(os.path.join(ERRDIR, '*.html'))):
    html = open(path, encoding='utf-8', errors='replace').read()
    print('=' * 100)
    print('FILE:', os.path.basename(path))
    # Django debug 页面：每个栈帧一个 <li class="frame ...">，内部有 filename/lineno
    frames = []
    for fm in re.finditer(r'<li class="frame[^"]*"[^>]*>(.*?)</li>', html, re.S):
        block = fm.group(1)
        fn = re.search(r'<span class="filename">(.*?)</span>', block, re.S)
        ln = re.search(r'<span class="lineno">(\d+)</span>', block, re.S)
        code = re.findall(r'<pre[^>]*>(.*?)</pre>', block, re.S)
        if fn:
            frames.append((clean(fn.group(1)), ln.group(1) if ln else '?',
                           clean(code[-1])[:160] if code else ''))
    if not frames:  # 退路：直接找所有 filename/lineno
        for fn, ln in re.findall(r'<span class="filename">(.*?)</span>.*?<span class="lineno">(\d+)</span>', html, re.S):
            frames.append((clean(fn), ln, ''))
    print(f'frames: {len(frames)}')
    for fn, ln, code in frames[-14:]:
        print(f'  {fn}:{ln}')
        if code:
            print(f'      > {code[:150]}')
    m = re.search(r'<pre class="exception_value">(.*?)</pre>', html, re.S)
    if m:
        print('EXCEPTION:', clean(m.group(1))[:300])
    print()
