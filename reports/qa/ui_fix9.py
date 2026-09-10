"""修复：object_list.html 的 controls 块在主题布局中不渲染 → 工具条移入 content 块。"""
import io
import os
import sys

BASE = r'C:\Users\PC\Documents\实验室\netbox-main\netbox'
APPLY = '--apply' in sys.argv
rel = 'lab_manager/templates/lab_manager/object_list.html'
full = os.path.join(BASE, rel)
src = io.open(full, encoding='utf-8').read()
report, failures = [], []

# 1) 从死块里移除密度按钮（controls 块不渲染，保留原样以免影响其它按钮定义）
old_btn = ("    {% plugin_list_buttons model %}\n"
           "    <button type=\"button\" class=\"btn btn-sm btn-outline-secondary\" data-lm-density-toggle\n"
           "            title=\"{% trans '切换表格密度' %}\" aria-pressed=\"false\">\n"
           "      <i class=\"mdi mdi-format-line-spacing\"></i>\n"
           "    </button>\n")
if src.count(old_btn) == 1:
    src = src.replace(old_btn, "    {% plugin_list_buttons model %}\n")
    report.append('  ok 移除 controls 块中的密度按钮（该块不参与渲染）')
else:
    failures.append(f'未找到 controls 块中的密度按钮（{src.count(old_btn)}）')

# 2) 在 content 块顶部插入真实渲染的工具条
anchor = ("  {# Object list tab #}\n"
          "  <div class=\"tab-pane show active\" id=\"object-list\" role=\"tabpanel\" aria-labelledby=\"object-list-tab\">\n")
toolbar = anchor + """
    {# ── 列表工具条：密度切换 + 结果计数（content 块参与渲染） ── #}
    <div class="lm-toolbar mb-2">
      <div class="lm-toolbar__group">
        <span class="text-muted small">{% trans "视图" %}</span>
        <button type="button" class="btn btn-sm btn-outline-secondary" data-lm-density-toggle
                title="{% trans '切换表格密度（紧凑/舒适）' %}" aria-pressed="false">
          <i class="mdi mdi-format-line-spacing"></i> {% trans "密度" %}
        </button>
      </div>
      <div class="lm-toolbar__group">
        <span class="lm-badge lm-badge--muted">
          {% if table.page.paginator.count %}{{ table.page.paginator.count }}{% else %}{{ total_count|default:"0" }}{% endif %}
          {% trans "条结果" %}
        </span>
      </div>
    </div>
"""
if src.count(anchor) == 1:
    src = src.replace(anchor, toolbar)
    report.append('  ok content 块内插入列表工具条（密度切换 + 结果计数）')
else:
    failures.append(f'未找到 content 锚点（{src.count(anchor)}）')

if APPLY and not failures:
    io.open(full, 'w', encoding='utf-8', newline='').write(src)

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
