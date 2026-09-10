"""批次1 机械替换：views.py 中 Model.objects.get(pk=...) -> get_object_or_404(...)

用法: python fix1_rewrite.py [--apply]
不带 --apply 时只打印将要修改的行（dry-run）。
"""
import re
import sys

VIEWS = r'C:\Users\PC\Documents\实验室\netbox-main\netbox\lab_manager\views.py'
APPLY = '--apply' in sys.argv

src = open(VIEWS, encoding='utf-8').read()
lines = src.split('\n')

PATTERNS = [
    (re.compile(r"(\b[A-Z]\w*)\.objects\.get\(pk=(self\.kwargs\['pk'\]|pk)\)"),
     lambda m: f"get_object_or_404({m.group(1)}, pk={m.group(2)})"),
    (re.compile(r"Notification\.objects\.get\(pk=pk, user=request\.user\)"),
     lambda m: "get_object_or_404(Notification, pk=pk, user=request.user)"),
]

changes = []
out = []
for i, line in enumerate(lines, 1):
    new = line
    for pat, rep in PATTERNS:
        new2 = pat.sub(rep, new)
        if new2 != new:
            changes.append((i, new.strip(), new2.strip()))
            new = new2
    out.append(new)

print(f'将修改 {len(changes)} 行:')
for ln, old, new in changes:
    print(f'  {ln}: {old}')
    print(f'      -> {new}')

if APPLY:
    open(VIEWS, 'w', encoding='utf-8', newline='').write('\n'.join(out))
    print('\n已写入 views.py')
else:
    print('\n(dry-run，未写入)')
