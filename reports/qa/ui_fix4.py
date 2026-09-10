"""批次 UI-2（P1）：移动端 KPI 横滑、框架表格粘性表头、库存水位条、
低库存横幅、硬件列表精简默认列、导航补看板入口。"""
import io
import os
import re
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
            failures.append(f'{rel}: 期望 {allow} 次，实际 {n} 次 -> {old.strip().splitlines()[0][:64]!r}')
            continue
        src = src.replace(old, new)
        report.append(f'  ok {rel}: {old.strip().splitlines()[0][:62]}')
    if src != orig:
        write(rel, src)


# ── 1. 组件层 CSS：移动端 KPI 横滑 + 框架表格粘性表头 ──────────
css = read('lab_manager/static/lab_manager/lm-components.css')
if '.tp-stat-row' not in css:
    css = css.rstrip('\n') + """

/* ═══ 仪表板：Bootstrap 统计行在移动端横向滚动（无需改 HTML） ═══ */
@media (max-width: 767.98px) {
  .tp-stat-row {
    display: flex; flex-wrap: nowrap; overflow-x: auto; scroll-snap-type: x mandatory;
    gap: var(--lm-space-2); margin-left: 0; margin-right: 0; padding-bottom: var(--lm-space-2);
    -webkit-overflow-scrolling: touch; scrollbar-width: none;
  }
  .tp-stat-row::-webkit-scrollbar { display: none; }
  .tp-stat-row > [class*="col-"] {
    flex: 0 0 58%; max-width: 58%; scroll-snap-align: start; padding-left: 0; padding-right: 0;
  }
  .tp-stat-row .card { height: 100%; }
}

/* ═══ 框架渲染的表格（django-tables2）也享受粘性表头与密度 ═══ */
.tp-page .htmx-container .table-responsive { max-height: 72vh; overflow: auto; }
.tp-page .htmx-container table { font-size: var(--lm-font-13); }
.tp-page .htmx-container table thead th {
  position: sticky; top: 0; z-index: 2;
  background: var(--lm-surface-3); color: var(--lm-text-muted);
  font-size: var(--lm-font-11); text-transform: uppercase; letter-spacing: .05em;
  border-bottom: 1px solid var(--lm-border-subtle);
}
.tp-page .htmx-container table tbody tr:hover td { background: var(--lm-surface-2); }
body.lm-density--compact .tp-page .htmx-container table th,
body.lm-density--compact .tp-page .htmx-container table td { padding: 2px var(--lm-space-2); font-size: var(--lm-font-12); }
"""
    write('lab_manager/static/lab_manager/lm-components.css', css)
    report.append('  ok lm-components.css: 追加仪表板移动端横滑 + 框架表格粘性表头')
else:
    report.append('  -- lm-components.css: 已包含相关规则，跳过')

# ── 2. 仪表板：把「需要我处理」提升为显式分区 ──────────────────
patch('lab_manager/templates/lab_manager/home.html', [
    (
        "{# 待审批硬件 + 逾期借出 #}\n<div class=\"row tp-info-row\">\n",
        "{# ═══ 需要我处理：决策优先，放在 KPI 之后、次要统计之前 ═══ #}\n"
        "<h2 class=\"lm-section__title mb-2\">\n"
        "  <i class=\"mdi mdi-flash-outline\"></i> {% trans \"需要我处理\" %}\n"
        "</h2>\n"
        "<div class=\"row tp-info-row\">\n",
    ),
])

# ── 3. 硬件表：数量列渲染为水位条 + 精简默认列 ─────────────────
patch('lab_manager/tables/hardware.py', [
    (
        "import django_tables2 as tables\n\n"
        "from netbox.tables import NetBoxTable\n"
        "from netbox.tables.columns import ChoiceFieldColumn\n\n"
        "from ..models import Hardware\n",
        "import django_tables2 as tables\n"
        "from django.utils.html import format_html\n\n"
        "from netbox.tables import NetBoxTable\n"
        "from netbox.tables.columns import ChoiceFieldColumn\n\n"
        "from ..models import Hardware\n",
    ),
    (
        "    purchase_date = tables.DateColumn()\n"
        "    quantity = tables.Column()\n",
        "    purchase_date = tables.DateColumn()\n"
        "    quantity = tables.Column(verbose_name='可用/总量')\n"
        "\n"
        "    def render_quantity(self, value, record):\n"
        '        """把纯数字渲染为库存水位条（可借/总量，含阈值配色）。"""\n'
        "        available = int(value or 0)\n"
        "        outstanding = int(getattr(record, 'outstanding', 0) or 0)\n"
        "        total = available + outstanding\n"
        "        minimum = int(record.minimum_stock or 0)\n"
        "        if available <= 0:\n"
        "            level = 'danger'\n"
        "        elif (minimum and available <= minimum) or (total and available / total <= 0.25):\n"
        "            level = 'warning'\n"
        "        else:\n"
        "            level = 'ok'\n"
        "        width = 100 if total <= 0 else max(2, min(100, round(available / total * 100)))\n"
        "        return format_html(\n"
        "            '<div class=\"lm-waterline lm-waterline--{}\" title=\"可用 {} / 总量 {}（在借 {}，阈值 {}）\">'\n"
        "            '<div class=\"lm-waterline__track\"><div class=\"lm-waterline__fill\" style=\"width:{}%\"></div></div>'\n"
        "            '<span class=\"lm-waterline__text\">{}/{}</span></div>',\n"
        "            level, available, total, outstanding, minimum, width, available, total,\n"
        "        )\n",
    ),
    (
        "        default_columns = (\n"
        "            'name', 'category', 'model_number', 'quantity',\n"
        "            'status', 'approval_status', 'custodian', 'storage_location',\n"
        "        )\n",
        "        # 精简默认列（5 列）；其余列可在表格配置中按需开启\n"
        "        default_columns = (\n"
        "            'name', 'category', 'quantity', 'status', 'approval_status',\n"
        "        )\n",
    ),
])

# ── 4. 硬件列表视图：在借数量注解 + 低库存上下文 ───────────────
patch('lab_manager/views.py', [
    (
        "            qs = qs.filter(\n"
        "                Q(approval_status=HardwareApprovalStatusChoices.APPROVED) |\n"
        "                Q(submitted_by=self.request.user)\n"
        "            )\n"
        "        return qs\n",
        "            qs = qs.filter(\n"
        "                Q(approval_status=HardwareApprovalStatusChoices.APPROVED) |\n"
        "                Q(submitted_by=self.request.user)\n"
        "            )\n"
        "        # 一次聚合：在借数量（供库存水位条使用，避免逐行查询）\n"
        "        return qs.annotate(\n"
        "            outstanding=Count(\n"
        "                'borrow_records',\n"
        "                filter=Q(borrow_records__status=BorrowStatusChoices.BORROWED),\n"
        "            )\n"
        "        )\n"
        "\n"
        "    def get_context_data(self, **kwargs):\n"
        "        ctx = super().get_context_data(**kwargs)\n"
        "        ctx['low_stock'] = list(\n"
        "            Hardware.objects.filter(minimum_stock__gt=0, quantity__lt=F('minimum_stock'))\n"
        "            .order_by('quantity')[:5]\n"
        "        )\n"
        "        return ctx\n",
    ),
])

# ── 5. 共享列表模板：低库存横幅 + 密度切换入口 ─────────────────
patch('lab_manager/templates/lab_manager/object_list.html', [
    (
        "        {# Objects table #}\n        <div class=\"card\">\n",
        "        {# 低库存横幅（仅硬件列表传入 low_stock） #}\n"
        "        {% if low_stock %}\n"
        "          <div class=\"lm-banner lm-banner--danger mb-2 flex-wrap\">\n"
        "            <i class=\"mdi mdi-alert-outline\"></i>\n"
        "            <span>{% blocktrans count n=low_stock|length %}{{ n }} 项硬件低于最低库存{% plural %}{{ n }} 项硬件低于最低库存{% endblocktrans %}：</span>\n"
        "            {% for hw in low_stock %}\n"
        "              <a href=\"{{ hw.get_absolute_url }}\" class=\"lm-badge lm-badge--danger text-decoration-none\">\n"
        "                {{ hw.name }} · {{ hw.quantity }}/{{ hw.minimum_stock }}\n"
        "              </a>\n"
        "            {% endfor %}\n"
        "          </div>\n"
        "        {% endif %}\n"
        "\n"
        "        {# Objects table #}\n        <div class=\"card\">\n",
    ),
    (
        "    {% plugin_list_buttons model %}\n",
        "    {% plugin_list_buttons model %}\n"
        "    <button type=\"button\" class=\"btn btn-sm btn-outline-secondary\" data-lm-density-toggle\n"
        "            title=\"{% trans '切换表格密度' %}\" aria-pressed=\"false\">\n"
        "      <i class=\"mdi mdi-format-line-spacing\"></i>\n"
        "    </button>\n",
    ),
])

# ── 6. 导航菜单：留待下一批（需先确认 menu.py 结构）────────────
report.append('  -- menu.py: 本批跳过（下一批补看板/指挥舱入口）')

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
