"""批次 UI-1（P0）：统一分页 + 筛选 + 命令面板 + 看板后端 + 全站 UI 注入。

按方案 A/B/P0 落地：
 - 分页助手 paginate()/pagination_context()，5 个列表页全部接入（?page=&per_page=）
 - 打卡记录 / 浏览记录 补筛选（成员、关键词、时间范围）+ 导出
 - 命令面板索引接口、任务看板视图、看板拖拽状态更新接口
 - base/layout.html 注入 lm-components.css、global_ui 与 lm-ui.js
"""
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


def patch(rel, pairs):
    src = read(rel)
    orig = src
    for old, new in pairs:
        n = src.count(old)
        if n != 1:
            failures.append(f'{rel}: 期望 1 次，实际 {n} 次 -> {old.strip().splitlines()[0][:66]!r}')
            continue
        src = src.replace(old, new)
        report.append(f'  ok {rel}: {old.strip().splitlines()[0][:64]}')
    if src != orig:
        write(rel, src)


# ── 1. views.py：分页助手 + 5 个列表页 ─────────────────────────
patch('lab_manager/views.py', [
    (
        "# 打卡防重复提交时间窗（秒）\nCHECKIN_DEDUPE_SECONDS = 60\n",
        "# 打卡防重复提交时间窗（秒）\nCHECKIN_DEDUPE_SECONDS = 60\n"
        "\n"
        "# 统一分页配置\n"
        "PAGE_SIZE_CHOICES = (25, 50, 100, 200)\n"
        "DEFAULT_PAGE_SIZE = 50\n"
        "\n"
        "\n"
        "def build_page(request, queryset, default_size=DEFAULT_PAGE_SIZE):\n"
        '    """统一的列表分页：?page=&per_page=（页大小限定在 PAGE_SIZE_CHOICES 内）。"""\n'
        "    from django.core.paginator import Paginator\n"
        "    try:\n"
        "        per_page = int(request.GET.get('per_page', default_size))\n"
        "    except (TypeError, ValueError):\n"
        "        per_page = default_size\n"
        "    if per_page not in PAGE_SIZE_CHOICES:\n"
        "        per_page = default_size\n"
        "    return Paginator(queryset, per_page).get_page(request.GET.get('page'))\n"
        "\n"
        "\n"
        "def add_pagination(ctx, request, queryset, default_size=DEFAULT_PAGE_SIZE):\n"
        '    """把分页对象与页大小选项塞进上下文，返回 page_obj。"""\n'
        "    page_obj = build_page(request, queryset, default_size)\n"
        "    ctx['page_obj'] = page_obj\n"
        "    ctx['per_page'] = page_obj.paginator.per_page\n"
        "    ctx['per_page_choices'] = PAGE_SIZE_CHOICES\n"
        "    return page_obj\n",
    ),
    # 打卡记录：筛选 + 分页
    (
        "    def get_context_data(self, **kwargs):\n"
        "        ctx = super().get_context_data(**kwargs)\n"
        "        records = CheckInRecord.objects.select_related('user').order_by('-created')\n"
        "        if not self.request.user.is_superuser:\n"
        "            records = records.filter(user=self.request.user)\n"
        "        ctx['records'] = records[:200]\n"
        "        ctx['is_superuser'] = self.request.user.is_superuser\n"
        "        return ctx\n",
        "    def get_context_data(self, **kwargs):\n"
        "        ctx = super().get_context_data(**kwargs)\n"
        "        request = self.request\n"
        "        records = CheckInRecord.objects.select_related('user').order_by('-created')\n"
        "        if not request.user.is_superuser:\n"
        "            records = records.filter(user=request.user)\n"
        "        # ── 筛选：成员 / 关键词 / 时间范围 ──\n"
        "        username = (request.GET.get('username') or '').strip()\n"
        "        keyword = (request.GET.get('q') or '').strip()\n"
        "        date_from = (request.GET.get('date_from') or '').strip()\n"
        "        date_to = (request.GET.get('date_to') or '').strip()\n"
        "        if username:\n"
        "            records = records.filter(\n"
        "                Q(user__username__icontains=username) | Q(user__first_name__icontains=username)\n"
        "                | Q(user__last_name__icontains=username) | Q(user__email__icontains=username)\n"
        "            )\n"
        "        if keyword:\n"
        "            records = records.filter(Q(address__icontains=keyword) | Q(note__icontains=keyword))\n"
        "        if date_from:\n"
        "            records = records.filter(created__date__gte=date_from)\n"
        "        if date_to:\n"
        "            records = records.filter(created__date__lte=date_to)\n"
        "        page_obj = add_pagination(ctx, request, records)\n"
        "        ctx['records'] = page_obj.object_list\n"
        "        ctx['is_superuser'] = request.user.is_superuser\n"
        "        ctx['filter_username'] = username\n"
        "        ctx['filter_q'] = keyword\n"
        "        ctx['filter_date_from'] = date_from\n"
        "        ctx['filter_date_to'] = date_to\n"
        "        ctx['filtered_count'] = page_obj.paginator.count\n"
        "        return ctx\n",
    ),
    # 浏览记录：分页（保留原筛选与统计）
    (
        "        if target_type:\n"
        "            records = records.filter(target_type=target_type)\n"
        "        ctx['records'] = records[:300]\n"
        "        ctx['username'] = username or ''\n"
        "        ctx['target_type'] = target_type or ''\n",
        "        if target_type:\n"
        "            records = records.filter(target_type=target_type)\n"
        "        keyword = (self.request.GET.get('q') or '').strip()\n"
        "        date_from = (self.request.GET.get('date_from') or '').strip()\n"
        "        date_to = (self.request.GET.get('date_to') or '').strip()\n"
        "        if keyword:\n"
        "            records = records.filter(Q(path__icontains=keyword) | Q(page_title__icontains=keyword))\n"
        "        if date_from:\n"
        "            records = records.filter(created__date__gte=date_from)\n"
        "        if date_to:\n"
        "            records = records.filter(created__date__lte=date_to)\n"
        "        page_obj = add_pagination(ctx, self.request, records, default_size=100)\n"
        "        ctx['records'] = page_obj.object_list\n"
        "        ctx['username'] = username or ''\n"
        "        ctx['target_type'] = target_type or ''\n"
        "        ctx['filter_q'] = keyword\n"
        "        ctx['filter_date_from'] = date_from\n"
        "        ctx['filter_date_to'] = date_to\n"
        "        ctx['filtered_count'] = page_obj.paginator.count\n",
    ),
    # 通知中心：分页
    (
        "        notifications = Notification.objects.filter(user=user).order_by('-created')\n"
        "        ctx['notifications'] = notifications[:50]\n"
        "        ctx['unread_count'] = notifications.filter(is_read=False).count()\n"
        "        return ctx\n",
        "        notifications = Notification.objects.filter(user=user).order_by('-created')\n"
        "        ctx['unread_count'] = notifications.filter(is_read=False).count()\n"
        "        page_obj = add_pagination(ctx, self.request, notifications)\n"
        "        ctx['notifications'] = page_obj.object_list\n"
        "        return ctx\n",
    ),
    # 成员列表：分页（先分页再聚合，查询数不随成员数增长）
    (
        "        users = list(User.objects.filter(is_active=True).order_by('username'))\n"
        "        user_ids = [u.pk for u in users]\n",
        "        page_obj = add_pagination(\n"
        "            ctx, self.request, User.objects.filter(is_active=True).order_by('username')\n"
        "        )\n"
        "        ctx['members_page'] = page_obj\n"
        "        users = list(page_obj.object_list)\n"
        "        user_ids = [u.pk for u in users]\n",
    ),
    (
        "        ctx['members'] = members\n"
        "        ctx['total_members'] = len(members)\n"
        "        return ctx\n",
        "        ctx['members'] = members\n"
        "        ctx['total_members'] = page_obj.paginator.count\n"
        "        return ctx\n",
    ),
    # 智能体会话：分页
    (
        "        ctx['conversations'] = conversations[:20]\n",
        "        page_obj = add_pagination(ctx, self.request, conversations, default_size=25)\n"
        "        ctx['conversations'] = page_obj.object_list\n",
    ),
])

# ── 2. views.py 追加新视图（命令面板索引 / 看板 / 状态更新） ────
BOARD_VIEWS = '''

# ── 界面增强：命令面板索引 / 任务看板 ──────────────────────────

class CommandIndexView(LoginRequiredMixin, View):
    """命令面板索引：导航 + 常用操作 + 少量动态对象（按需加载，不进入页面渲染）。"""

    http_method_names = ['get']

    def get(self, request):
        def nav(label, url_name, icon, group, keywords=''):
            try:
                return {'label': label, 'url': reverse(f'plugins:lab_manager:{url_name}'),
                        'icon': icon, 'group': group, 'keywords': keywords, 'action': 'goto'}
            except NoReverseMatch:
                return None

        items = [x for x in [
            nav('仪表板', 'home', 'mdi-view-dashboard-outline', '导航', 'home dashboard 首页'),
            nav('硬件列表', 'hardware_list', 'mdi-cube-outline', '导航', 'hardware 设备'),
            nav('任务列表', 'task_list', 'mdi-clipboard-text-outline', '导航', 'tasks 待办'),
            nav('任务看板', 'task_board', 'mdi-view-column-outline', '导航', 'kanban 看板'),
            nav('我的任务', 'my_tasks', 'mdi-account-check-outline', '导航', 'my tasks'),
            nav('借出记录', 'hardwareborrowrecord_list', 'mdi-swap-horizontal', '导航', 'borrow 借出'),
            nav('实验项目', 'labproject_list', 'mdi-flask-outline', '导航', 'project'),
            nav('打卡记录', 'checkin_list', 'mdi-map-marker-check-outline', '导航', 'checkin 签到'),
            nav('成员列表', 'member_list', 'mdi-account-group-outline', '导航', 'members'),
            nav('任务日历', 'calendar', 'mdi-calendar-month-outline', '导航', 'calendar'),
            nav('浏览记录', 'member_open_records', 'mdi-history', '导航', 'audit 审计'),
            nav('通知中心', 'notifications', 'mdi-bell-outline', '导航', 'notifications'),
            nav('智能体控制台', 'agent_console', 'mdi-robot-happy-outline', '导航', 'agent ai'),
            nav('指挥舱', 'mission_control', 'mdi-monitor-dashboard', '导航', 'mission control 大屏'),
            nav('数据导出', 'export_data', 'mdi-download-outline', '导航', 'export csv'),
            nav('设计系统', 'design_system', 'mdi-palette-outline', '导航', 'design tokens 组件'),
            nav('新增硬件', 'hardware_add', 'mdi-plus-thick', '操作', 'add hardware 提交'),
            nav('新增任务', 'task_add', 'mdi-plus-thick', '操作', 'add task 派发'),
            nav('登记借出', 'hardwareborrowrecord_add', 'mdi-plus-thick', '操作', 'borrow 借出'),
            nav('新增项目', 'labproject_add', 'mdi-plus-thick', '操作', 'project'),
            nav('拍照打卡', 'checkin_create', 'mdi-camera', '操作', 'checkin 打卡'),
            nav('发送通知', 'notification_send', 'mdi-send', '操作', 'notify'),
        ] if x]

        if request.user.is_superuser:
            for hw in Hardware.objects.order_by('name')[:40]:
                items.append({'label': hw.name, 'url': hw.get_absolute_url(), 'icon': 'mdi-cube-outline',
                              'group': '硬件', 'keywords': f'{hw.category} {hw.model_number} 硬件',
                              'action': 'goto'})
            for task in Task.objects.select_related('assigned_to').order_by('-created')[:30]:
                items.append({'label': task.title, 'url': task.get_absolute_url(),
                              'icon': 'mdi-clipboard-text-outline', 'group': '任务',
                              'keywords': f'{task.status} {getattr(task.assigned_to, "username", "")}',
                              'action': 'goto'})
        else:
            for task in Task.objects.filter(assigned_to=request.user).order_by('-created')[:30]:
                items.append({'label': task.title, 'url': task.get_absolute_url(),
                              'icon': 'mdi-clipboard-text-outline', 'group': '我的任务',
                              'keywords': task.status, 'action': 'goto'})

        return JsonResponse({'items': items})


@method_decorator(require_POST, name='dispatch')
class TaskStatusUpdateView(LoginRequiredMixin, View):
    """看板拖拽改状态（JSON）。"""

    def post(self, request):
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse({'ok': False, 'error': '请求体不是合法 JSON'}, status=400)
        pk = payload.get('pk')
        status = str(payload.get('status') or '').strip()
        if status not in {c[0] for c in Task._meta.get_field('status').choices}:
            return JsonResponse({'ok': False, 'error': 'status 不合法'}, status=400)
        task = get_object_or_404(Task, pk=pk)
        if not (request.user.is_superuser or request.user in (task.created_by, task.assigned_to)):
            return JsonResponse({'ok': False, 'error': '无权修改该任务'}, status=403)
        task.status = status
        if status == TaskStatusChoices.COMPLETED:
            task.completed_at = timezone.now()
        else:
            task.completed_at = None
        task.save(update_fields=['status', 'completed_at', 'last_updated'])
        return JsonResponse({'ok': True, 'status': task.status})


class TaskBoardView(LoginRequiredMixin, TemplateView):
    """任务看板：按状态三列，可拖拽流转。"""

    template_name = 'lab_manager/task_board.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        request = self.request
        tasks = Task.objects.select_related('assigned_to', 'created_by', 'project')
        if not request.user.is_superuser:
            tasks = tasks.filter(Q(assigned_to=request.user) | Q(created_by=request.user))
        tasks = tasks.order_by('deadline', '-created')
        now = timezone.now()
        columns = []
        for value, label in Task._meta.get_field('status').choices:
            rows = [t for t in tasks if t.status == value]
            columns.append({
                'value': value, 'label': label, 'tasks': rows, 'count': len(rows),
                'overdue': sum(1 for t in rows if t.deadline and t.deadline < now and value != TaskStatusChoices.COMPLETED),
            })
        ctx['columns'] = columns
        ctx['now'] = now
        return ctx
'''
src = read('lab_manager/views.py')
if 'class TaskBoardView' in src:
    report.append('  -- views.py: 看板视图已存在，跳过')
else:
    anchor = "\n\n# ── 站内通知 ──\n"
    if src.count(anchor) != 1:
        failures.append('views.py: 未找到插入锚点 "# ── 站内通知 ──"')
    else:
        src = src.replace(anchor, BOARD_VIEWS + anchor)
        # 需要的导入
        if 'from django.views.decorators.http import require_POST' not in src:
            src = src.replace(
                'from django.views.generic import TemplateView, View\n',
                'from django.views.decorators.http import require_POST\n'
                'from django.views.generic import TemplateView, View\n', 1)
        if 'from django.utils.decorators import method_decorator' not in src:
            src = src.replace(
                'from django.views.decorators.http import require_POST\n',
                'from django.utils.decorators import method_decorator\n'
                'from django.views.decorators.http import require_POST\n', 1)
        if 'from django.urls import NoReverseMatch, reverse' not in src:
            src = src.replace(
                'from django.shortcuts import get_object_or_404, redirect\n',
                'from django.shortcuts import get_object_or_404, redirect\n'
                'from django.urls import NoReverseMatch, reverse\n', 1)
        write('lab_manager/views.py', src)
        report.append('  ok views.py: 追加 CommandIndexView / TaskBoardView / TaskStatusUpdateView')

# ── 3. urls.py：新路由 ─────────────────────────────────────────
patch('lab_manager/urls.py', [
    (
        "    path('notifications/read-all/', views.NotificationMarkReadView.as_view(), name='notification_read_all'),\n",
        "    path('notifications/read-all/', views.NotificationMarkReadView.as_view(), name='notification_read_all'),\n"
        "    path('api/command-index/', views.CommandIndexView.as_view(), name='command_index'),\n"
        "    path('api/tasks/status/', views.TaskStatusUpdateView.as_view(), name='task_status_update'),\n",
    ),
    (
        "    path('my-tasks/', views.MyTasksView.as_view(), name='my_tasks'),\n",
        "    path('my-tasks/', views.MyTasksView.as_view(), name='my_tasks'),\n"
        "    path('tasks/board/', views.TaskBoardView.as_view(), name='task_board'),\n",
    ),
])

# ── 4. layout.html：注入组件层 CSS 与全局 UI ───────────────────
patch('templates/base/layout.html', [
    (
        "<link rel=\"stylesheet\" href=\"{% static 'lab_manager/terminal_pixel.css' %}?v=36\">\n",
        "<link rel=\"stylesheet\" href=\"{% static 'lab_manager/terminal_pixel.css' %}?v=36\">\n"
        "<link rel=\"stylesheet\" href=\"{% static 'lab_manager/lm-components.css' %}?v=1\">\n",
    ),
    (
        "{% endblock layout %}",
        "{# ── 全局 UI：命令面板 ⌘K + AI 副驾驶 ── #}\n"
        "{% include 'lab_manager/inc/global_ui.html' %}\n"
        "<script src=\"{% static 'lab_manager/lm-ui.js' %}?v=1\"></script>\n"
        "\n"
        "{% endblock layout %}",
    ),
])

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
