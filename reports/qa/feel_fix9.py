"""移除与 NetBox 自带 View Transitions 冲突的自定义 VT 规则（局部导航已解决侧栏刷新问题）。"""
import io
import os
import re
import sys

BASE = r'C:\Users\PC\Documents\实验室\netbox-main\netbox'
APPLY = '--apply' in sys.argv
path = os.path.join(BASE, 'lab_manager/static/lab_manager/lm-components.css')
src = io.open(path, encoding='utf-8').read()

start = src.find('/* ═══════════════════════════════════════════════════════════════\n   页面切换观感：跨文档 View Transitions')
if start == -1:
    print('未找到自定义 VT 段落（可能已移除）')
    sys.exit(0)

end_marker = '@media (prefers-reduced-motion: reduce) {\n  ::view-transition-group(*),\n  ::view-transition-old(*),\n  ::view-transition-new(*) { animation: none !important; }\n}\n'
end = src.find(end_marker, start)
if end == -1:
    print('!! 未找到 VT 段落结束标记')
    sys.exit(1)
end += len(end_marker)

replacement = """/* 页面切换观感说明：
   侧栏"每次切换都刷新"的问题已由 HTMX 局部导航解决（见 base/layout.html 的 hx-boost），
   侧栏 DOM 不再重建，因此不需要跨文档 View Transitions。
   实测本环境 NetBox 自带页面过渡逻辑，自定义的过渡声明会与之冲突
   （控制台出现 Transition was skipped），故此文件不声明任何页面过渡规则。
   内容区替换后的重新绑定由 lm-ui.js 的 rebind() + MutationObserver 负责。 */
"""
src = src[:start] + replacement + src[end:]
leftover = re.findall(r'[^\n]*(@view-transition|::view-transition|view-transition-name:)[^\n]*', src)
if leftover:
    print('!! 仍残留过渡规则:', leftover[:3])
    sys.exit(1)
if APPLY:
    io.open(path, 'w', encoding='utf-8', newline='').write(src)
    print('已移除自定义 VT 规则（避免与 NetBox 自带视图过渡冲突）')
else:
    print('DRY-RUN：将移除自定义 VT 规则')
