"""批次 UI-4：移动端卡片压缩（避免卡片化后行高爆炸）+ 手写列表默认页大小 25。"""
import io
import os
import sys

BASE = r'C:\Users\PC\Documents\实验室\netbox-main\netbox'
APPLY = '--apply' in sys.argv
report, failures = [], []


def read(rel):
    return io.open(os.path.join(BASE, rel), encoding='utf-8').read()


def write(rel, src):
    if APPLY:
        io.open(os.path.join(BASE, rel), 'w', encoding='utf-8', newline='').write(src)


def patch(rel, pairs, allow=1):
    src = read(rel)
    orig = src
    for old, new in pairs:
        n = src.count(old)
        if n != allow:
            failures.append(f'{rel}: 期望 {allow} 次，实际 {n} 次 -> {old.strip().splitlines()[0][:60]!r}')
            continue
        src = src.replace(old, new)
        report.append(f'  ok {rel}: {old.strip().splitlines()[0][:58]}')
    if src != orig:
        write(rel, src)


# 1) 移动端卡片：更紧凑 + 支持隐藏低价值字段
css = read('lab_manager/static/lab_manager/lm-components.css')
if 'data-compact="hide"' not in css:
    css = css.replace(
        """  .lm-table--cards tbody td::before {
    content: attr(data-label); color: var(--lm-text-muted);
    font-size: var(--lm-font-11); text-transform: uppercase; letter-spacing: .04em; text-align: left;
  }""",
        """  .lm-table--cards tbody td::before {
    content: attr(data-label); color: var(--lm-text-muted);
    font-size: var(--lm-font-11); text-transform: uppercase; letter-spacing: .04em; text-align: left;
  }
  /* 移动端隐藏低价值字段，避免整页被长成几十屏 */
  .lm-table--cards tbody td[data-compact="hide"] { display: none; }
  .lm-table--cards tbody td { padding: 2px 0; }
  .lm-table--cards tbody tr { padding: var(--lm-space-1) var(--lm-space-2); }""", 1)
    write('lab_manager/static/lab_manager/lm-components.css', css)
    report.append('  ok lm-components.css: 移动端卡片压缩 + data-compact 隐藏支持')
else:
    report.append('  -- lm-components.css: 已有压缩规则，跳过')

# 2) 打卡记录：精度列在移动端隐藏
patch('lab_manager/templates/lab_manager/checkin_list.html', [
    (
        "            <td data-label=\"{% trans '精度' %}\">{{ record.accuracy|default:'-' }}</td>\n",
        "            <td data-label=\"{% trans '精度' %}\" data-compact=\"hide\">{{ record.accuracy|default:'-' }}</td>\n",
    ),
])

# 3) 浏览记录：路径与 IP 在移动端隐藏
patch('lab_manager/templates/lab_manager/member_open_record_list.html', [
    (
        "            <td data-label=\"{% trans '路径' %}\" class=\"text-break\">{{ record.path|truncatechars:40 }}</td>\n",
        "            <td data-label=\"{% trans '路径' %}\" class=\"text-break\" data-compact=\"hide\">{{ record.path|truncatechars:40 }}</td>\n",
    ),
    (
        "            <td data-label=\"{% trans 'IP' %}\">{{ record.ip_address|default:'-' }}</td>\n",
        "            <td data-label=\"{% trans 'IP' %}\" data-compact=\"hide\">{{ record.ip_address|default:'-' }}</td>\n",
    ),
])

# 4) 默认页大小：手写列表 25（原 50/100），避免一屏灌入过多行
patch('lab_manager/views.py', [
    (
        "        page_obj = add_pagination(ctx, request, records)\n"
        "        ctx['records'] = page_obj.object_list\n"
        "        ctx['is_superuser'] = request.user.is_superuser\n",
        "        page_obj = add_pagination(ctx, request, records, default_size=25)\n"
        "        ctx['records'] = page_obj.object_list\n"
        "        ctx['is_superuser'] = request.user.is_superuser\n",
    ),
    (
        "        page_obj = add_pagination(ctx, self.request, records, default_size=100)\n",
        "        page_obj = add_pagination(ctx, self.request, records, default_size=25)\n",
    ),
])

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
