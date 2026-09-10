"""批次 UI-3：指挥舱 + 设计系统页 + 导航入口 + 成员详情移动端紧凑化。"""
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


# ── 1. views.py：指挥舱 + 设计系统 ─────────────────────────────
MC_VIEWS = '''

# ── 界面增强：指挥舱（投屏大屏）+ 设计系统 ──────────────────────

class MissionControlView(LoginRequiredMixin, TemplateView):
    """指挥舱：一屏 KPI + 待办队列 + 库存水位 + 实时事件流 + 考勤热力图。"""

    template_name = 'lab_manager/mission_control.html'

    def get_context_data(self, **kwargs):
        from django.db.models.functions import TruncDate

        ctx = super().get_context_data(**kwargs)
        request = self.request
        now = timezone.now()
        today = timezone.localdate()

        tasks = Task.objects.all() if request.user.is_superuser else Task.objects.filter(
            Q(assigned_to=request.user) | Q(created_by=request.user)
        )
        hardware = Hardware.objects.all()
        if not request.user.is_superuser:
            hardware = hardware.filter(
                Q(approval_status=HardwareApprovalStatusChoices.APPROVED) | Q(submitted_by=request.user)
            )

        ctx['kpis'] = [
            {'label': _('硬件总数'), 'value': hardware.count(), 'hint': _('含待审批')},
            {'label': _('在用硬件'), 'value': hardware.filter(status=HardwareStatusChoices.IN_USE).count(),
             'hint': _('状态=在用'), 'tone': 'ok'},
            {'label': _('进行中任务'), 'value': tasks.filter(status=TaskStatusChoices.IN_PROGRESS).count(),
             'hint': f"{tasks.filter(status=TaskStatusChoices.PENDING).count()} " + str(_('待开始'))},
            {'label': _('今日打卡'), 'value': CheckInRecord.objects.filter(created__date=today).count(),
             'hint': _('今天'), 'tone': 'warning'},
        ]

        pending_hw = hardware.filter(approval_status=HardwareApprovalStatusChoices.PENDING)[:5]
        overdue_tasks = tasks.filter(
            status__in=[TaskStatusChoices.PENDING, TaskStatusChoices.IN_PROGRESS], deadline__lt=now
        )[:5]
        overdue_borrows = HardwareBorrowRecord.objects.filter(
            status=BorrowStatusChoices.BORROWED, expected_return_date__lt=now
        ).select_related('hardware', 'borrower')[:5]
        low_stock = hardware.filter(minimum_stock__gt=0, quantity__lt=F('minimum_stock'))[:5]
        ctx['todos'] = {
            'pending_hardware': list(pending_hw),
            'overdue_tasks': list(overdue_tasks),
            'overdue_borrows': list(overdue_borrows),
            'low_stock': list(low_stock),
        }

        # 实时事件流：浏览记录 + 通知 + 打卡合并
        stream = []
        for rec in MemberOpenRecord.objects.select_related('user').order_by('-created')[:20]:
            stream.append({'time': rec.created, 'icon': 'mdi-history',
                           'text': f'{rec.user} · {rec.page_title or rec.path}'})
        for ck in CheckInRecord.objects.select_related('user').order_by('-created')[:10]:
            stream.append({'time': ck.created, 'icon': 'mdi-map-marker-check-outline',
                           'text': f'{ck.user} · {_("完成打卡")} {ck.address or ""}'.strip()})
        for nf in Notification.objects.select_related('user').order_by('-created')[:10]:
            stream.append({'time': nf.created, 'icon': 'mdi-bell-outline', 'text': f'{nf.user} · {nf.title}'})
        stream.sort(key=lambda x: x['time'], reverse=True)
        ctx['stream'] = stream[:24]

        # 库存水位（按类别聚合）
        ctx['waterlines'] = list(
            hardware.values('category').annotate(
                available=Sum('quantity'), minimum=Sum('minimum_stock'), items=Count('id')
            ).order_by('category')[:8]
        )

        # 近 26 周考勤热力图
        start = today - timedelta(days=today.weekday() + 7 * 25)
        counts = {
            row['d']: row['n']
            for row in CheckInRecord.objects.filter(created__date__gte=start)
            .annotate(d=TruncDate('created')).values('d').annotate(n=Count('id'))
        }
        weeks, day = [], start
        while day <= today:
            week = []
            for _i in range(7):
                n = counts.get(day, 0)
                level = 0 if n == 0 else (1 if n == 1 else 2 if n == 2 else 3 if n < 5 else 4)
                week.append({'date': day, 'count': n, 'level': level,
                             'future': day > today})
                day += timedelta(days=1)
            weeks.append(week)
        ctx['heatmap_weeks'] = weeks
        ctx['heatmap_total'] = sum(counts.values())

        # 近 30 天趋势（任务完成 / 打卡 / 借出），服务端算好折线点
        days = [today - timedelta(days=i) for i in range(29, -1, -1)]
        def series(queryset, date_field):
            rows = (queryset.filter(**{f'{date_field}__date__gte': days[0]})
                    .annotate(d=TruncDate(date_field)).values('d').annotate(n=Count('id')))
            mapping = {r['d']: r['n'] for r in rows}
            return [mapping.get(d, 0) for d in days]

        raw = {
            '任务完成': series(Task.objects.filter(completed_at__isnull=False), 'completed_at'),
            '打卡': series(CheckInRecord.objects.all(), 'created'),
            '借出': series(HardwareBorrowRecord.objects.all(), 'borrow_date'),
        }
        chart_w, chart_h = 600, 120
        peak = max([1] + [v for s in raw.values() for v in s])
        chart = []
        for idx, (label, values) in enumerate(raw.items()):
            points = ' '.join(
                f'{(i / (len(values) - 1)) * chart_w:.1f},{chart_h - (v / peak) * (chart_h - 8):.1f}'
                for i, v in enumerate(values)
            )
            chart.append({'label': label, 'points': points, 'total': sum(values),
                          'color': ['var(--lm-accent)', 'var(--lm-ok)', 'var(--lm-warning)'][idx % 3]})
        ctx['trend'] = {'chart_w': chart_w, 'chart_h': chart_h, 'peak': peak,
                        'series': chart, 'start': days[0], 'end': days[-1]}
        return ctx


class DesignSystemView(LoginRequiredMixin, TemplateView):
    """设计系统展示页：令牌与组件示例（团队设计资产单一来源）。"""

    template_name = 'lab_manager/design_system.html'
'''
src = read('lab_manager/views.py')
if 'class MissionControlView' in src:
    report.append('  -- views.py: 指挥舱已存在，跳过')
else:
    anchor = "\n\n# ── 界面增强：命令面板索引 / 任务看板 ──────────────────────────\n"
    if src.count(anchor) != 1:
        failures.append('views.py: 未找到插入锚点（命令面板注释）')
    else:
        src = src.replace(anchor, MC_VIEWS + anchor)
        for need, target, ins in [
            ('from django.db.models.functions import TruncDate', None, None),
        ]:
            pass
        if 'from django.db.models import Count, F, Q, Sum' not in src:
            src = src.replace('from django.db.models import Count, Q\n',
                              'from django.db.models import Count, F, Q, Sum\n', 1)
        write('lab_manager/views.py', src)
        report.append('  ok views.py: 追加 MissionControlView / DesignSystemView')

# ── 2. urls.py ────────────────────────────────────────────────
patch('lab_manager/views.py', [
    (
        "from .choices import HardwareApprovalStatusChoices, TaskStatusChoices\n",
        "from .choices import HardwareApprovalStatusChoices, HardwareStatusChoices, TaskStatusChoices\n",
    ),
])

patch('lab_manager/urls.py', [
    (
        "    path('tasks/board/', views.TaskBoardView.as_view(), name='task_board'),\n",
        "    path('tasks/board/', views.TaskBoardView.as_view(), name='task_board'),\n"
        "    path('mission-control/', views.MissionControlView.as_view(), name='mission_control'),\n"
        "    path('design-system/', views.DesignSystemView.as_view(), name='design_system'),\n",
    ),
])

# ── 3. 导航：任务看板 + 指挥舱 + 设计系统 ───────────────────────
patch('lab_manager/navigation/menu.py', [
    (
        "            PluginMenuItem(\n"
        "                link='plugins:lab_manager:my_tasks',\n"
        "                link_text='我的任务',\n"
        "            ),\n",
        "            PluginMenuItem(\n"
        "                link='plugins:lab_manager:my_tasks',\n"
        "                link_text='我的任务',\n"
        "            ),\n"
        "            PluginMenuItem(\n"
        "                link='plugins:lab_manager:task_board',\n"
        "                link_text='任务看板',\n"
        "            ),\n"
        "            PluginMenuItem(\n"
        "                link='plugins:lab_manager:mission_control',\n"
        "                link_text='指挥舱 / 投屏',\n"
        "            ),\n"
        "            PluginMenuItem(\n"
        "                link='plugins:lab_manager:design_system',\n"
        "                link_text='设计系统',\n"
        "            ),\n",
    ),
])

# ── 4. 成员详情：统计行移动端横滑 ──────────────────────────────
patch('lab_manager/templates/lab_manager/member_detail.html', [
    (
        "{# ── 第一行：4 个统计卡片 ── #}\n<div class=\"row mb-3\">\n",
        "{# ── 第一行：4 个统计卡片（移动端横滑，见 lm-components.css） ── #}\n"
        "<div class=\"row mb-3 tp-stat-row\">\n",
    ),
])

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
