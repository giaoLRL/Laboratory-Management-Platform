"""修复指挥舱趋势图：数据全为 0 时的空白画面 → 空状态兜底 + 基线 + 峰值刻度。"""
import io
import os
import sys

BASE = r'C:\Users\PC\Documents\实验室\netbox-main\netbox'
APPLY = '--apply' in sys.argv
report, failures = [], []


def patch(rel, pairs):
    full = os.path.join(BASE, rel)
    src = io.open(full, encoding='utf-8').read()
    orig = src
    for old, new in pairs:
        n = src.count(old)
        if n != 1:
            failures.append(f'{rel}: 期望 1 次，实际 {n} 次 -> {old.strip().splitlines()[0][:60]!r}')
            continue
        src = src.replace(old, new)
        report.append(f'  ok {rel}: {old.strip().splitlines()[0][:58]}')
    if src != orig and APPLY:
        io.open(full, 'w', encoding='utf-8', newline='').write(src)


patch('lab_manager/views.py', [(
    "        ctx['trend'] = {'chart_w': chart_w, 'chart_h': chart_h, 'peak': peak,\n"
    "                        'series': chart, 'start': days[0], 'end': days[-1]}\n",
    "        ctx['trend'] = {'chart_w': chart_w, 'chart_h': chart_h, 'peak': peak,\n"
    "                        'series': chart, 'start': days[0], 'end': days[-1],\n"
    "                        'empty': all(item['total'] == 0 for item in chart)}\n",
)])

patch('lab_manager/templates/lab_manager/mission_control.html', [(
    "          <div class=\"lm-chart\">\n"
    "            <svg viewBox=\"0 0 {{ trend.chart_w }} {{ trend.chart_h }}\" preserveAspectRatio=\"none\" role=\"img\"\n"
    "                 aria-label=\"{% trans '近 30 天趋势' %}\">\n"
    "              {% for s in trend.series %}\n"
    "              <polyline fill=\"none\" stroke=\"{{ s.color }}\" stroke-width=\"2\" points=\"{{ s.points }}\" />\n"
    "              {% endfor %}\n"
    "            </svg>\n"
    "          </div>\n",
    "          {% if trend.empty %}\n"
    "            {% include 'lab_manager/inc/empty_state.html' with icon='mdi-chart-line' title=_('近 30 天暂无数据') desc=_('有任务完成、打卡或借出记录后，这里会显示趋势曲线。') %}\n"
    "          {% else %}\n"
    "          <div class=\"lm-chart\">\n"
    "            <svg viewBox=\"0 0 {{ trend.chart_w }} {{ trend.chart_h }}\" preserveAspectRatio=\"none\" role=\"img\"\n"
    "                 aria-label=\"{% trans '近 30 天趋势' %}\">\n"
    "              <line x1=\"0\" y1=\"{{ trend.chart_h }}\" x2=\"{{ trend.chart_w }}\" y2=\"{{ trend.chart_h }}\"\n"
    "                    stroke=\"var(--lm-border-subtle)\" stroke-width=\"1\" />\n"
    "              <line x1=\"0\" y1=\"4\" x2=\"{{ trend.chart_w }}\" y2=\"4\"\n"
    "                    stroke=\"var(--lm-border-subtle)\" stroke-width=\"1\" stroke-dasharray=\"3 4\" />\n"
    "              {% for s in trend.series %}\n"
    "              <polyline fill=\"none\" stroke=\"{{ s.color }}\" stroke-width=\"2\"\n"
    "                        points=\"{{ s.points }}\" vector-effect=\"non-scaling-stroke\" />\n"
    "              {% endfor %}\n"
    "            </svg>\n"
    "            <div class=\"d-flex justify-content-between text-muted small mt-1\">\n"
    "              <span>{{ trend.start|date:'m-d' }}</span>\n"
    "              <span>{% trans '峰值' %} {{ trend.peak }}</span>\n"
    "              <span>{{ trend.end|date:'m-d' }}</span>\n"
    "            </div>\n"
    "          </div>\n"
    "          {% endif %}\n",
)])

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
