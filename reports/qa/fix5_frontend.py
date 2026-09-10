"""批次5 前端体验与性能修复。"""
import io
import os
import re as _re
import sys

BASE = r'C:\Users\PC\Documents\实验室\netbox-main\netbox'
APPLY = '--apply' in sys.argv
report, failures = [], []


def patch(path, pairs, regex_pairs=()):
    full = os.path.join(BASE, path)
    src = io.open(full, encoding='utf-8').read()
    orig = src
    for old, new in pairs:
        n = src.count(old)
        if n != 1:
            failures.append(f'{path}: 期望 1 次，实际 {n} 次 -> {old.strip().splitlines()[0][:70]!r}')
            continue
        src = src.replace(old, new)
        report.append(f'  ok {path}: {old.strip().splitlines()[0][:68]}')
    for pat, new, expect in regex_pairs:
        src, n = _re.subn(pat, new, src)
        (report if n == expect else failures).append(
            f'  {"ok" if n == expect else "!!"} {path}(regex {n}/{expect}): {pat[:58]}')
    if src != orig and APPLY:
        io.open(full, 'w', encoding='utf-8', newline='').write(src)


# ── A. 智能体会话删除视图 ─────────────────────────────────────
patch('lab_manager/views.py', [
    (
        "class NotificationSendView(LoginRequiredMixin, TemplateView):\n",
        "class AgentConversationDeleteView(LoginRequiredMixin, View):\n"
        '    """删除本人的智能体会话（连同消息）。仅 POST。"""\n'
        "\n"
        "    http_method_names = ['post']\n"
        "\n"
        "    def post(self, request, pk):\n"
        "        conversation = get_object_or_404(AgentConversation, pk=pk, user=request.user)\n"
        "        conversation.delete()\n"
        "        return JsonResponse({'ok': True})\n"
        "\n"
        "\n"
        "class NotificationSendView(LoginRequiredMixin, TemplateView):\n",
    ),
    # 成员列表：批量聚合，消除每用户 ~11 次 count() 的 N+1
    (
        "        users = User.objects.filter(is_active=True).order_by('username')\n"
        "        today = timezone.localdate()\n"
        "\n"
        "        members = []\n"
        "        for user in users:\n",
        "        users = list(User.objects.filter(is_active=True).order_by('username'))\n"
        "        user_ids = [u.pk for u in users]\n"
        "        today = timezone.localdate()\n"
        "        now = timezone.now()\n"
        "\n"
        "        def counts(queryset, key, **filters):\n"
        "            return {\n"
        "                row[key]: row['n']\n"
        "                for row in queryset.filter(**filters).values(key).annotate(n=Count('pk'))\n"
        "            }\n"
        "\n"
        "        assigned_qs = Task.objects.filter(assigned_to_id__in=user_ids)\n"
        "        task_total_map = counts(assigned_qs, 'assigned_to_id')\n"
        "        task_completed_map = counts(assigned_qs, 'assigned_to_id', status=TaskStatusChoices.COMPLETED)\n"
        "        task_progress_map = counts(assigned_qs, 'assigned_to_id', status=TaskStatusChoices.IN_PROGRESS)\n"
        "        task_pending_map = counts(assigned_qs, 'assigned_to_id', status=TaskStatusChoices.PENDING)\n"
        "        task_overdue_map = counts(\n"
        "            assigned_qs, 'assigned_to_id',\n"
        "            status__in=[TaskStatusChoices.PENDING, TaskStatusChoices.IN_PROGRESS], deadline__lt=now,\n"
        "        )\n"
        "        borrow_qs = HardwareBorrowRecord.objects.filter(borrower_id__in=user_ids)\n"
        "        borrowed_total_map = counts(borrow_qs, 'borrower_id')\n"
        "        borrowed_current_map = counts(borrow_qs, 'borrower_id', status=BorrowStatusChoices.BORROWED)\n"
        "        checkin_qs = CheckInRecord.objects.filter(user_id__in=user_ids)\n"
        "        checkin_total_map = counts(checkin_qs, 'user_id')\n"
        "        checkin_today_map = counts(checkin_qs, 'user_id', created__date=today)\n"
        "        member_projects = counts(LabProject.objects.filter(members__in=user_ids), 'members')\n"
        "        led_projects = counts(LabProject.objects.filter(leader_id__in=user_ids), 'leader_id')\n"
        "        last_open_map = dict(\n"
        "            MemberOpenRecord.objects.filter(user_id__in=user_ids)\n"
        "            .order_by('user_id', '-created').distinct('user_id')\n"
        "            .values_list('user_id', 'created')\n"
        "        )\n"
        "        last_checkin_map = dict(\n"
        "            CheckInRecord.objects.filter(user_id__in=user_ids)\n"
        "            .order_by('user_id', '-created').distinct('user_id')\n"
        "            .values_list('user_id', 'created')\n"
        "        )\n"
        "\n"
        "        members = []\n"
        "        for user in users:\n"
        "            uid = user.pk\n"
        "            task_total = task_total_map.get(uid, 0)\n"
        "            task_completed = task_completed_map.get(uid, 0)\n"
        "            task_in_progress = task_progress_map.get(uid, 0)\n"
        "            task_pending = task_pending_map.get(uid, 0)\n"
        "            task_overdue = task_overdue_map.get(uid, 0)\n"
        "            borrowed_total = borrowed_total_map.get(uid, 0)\n"
        "            borrowed_current = borrowed_current_map.get(uid, 0)\n"
        "            checkin_total = checkin_total_map.get(uid, 0)\n"
        "            checkin_today = checkin_today_map.get(uid, 0)\n"
        "            project_count = member_projects.get(uid, 0) + led_projects.get(uid, 0)\n"
        "            last_open = last_open_map.get(uid)\n"
        "            last_checkin = last_checkin_map.get(uid)\n"
        "\n"
        "            if False:  # 占位：保持下方原有 append 结构\n",
    ),
    (
        "            # 任务统计\n"
        "            assigned = user.assigned_tasks.all()\n"
        "            task_total = assigned.count()\n"
        "            task_completed = assigned.filter(status=TaskStatusChoices.COMPLETED).count()\n"
        "            task_in_progress = assigned.filter(status=TaskStatusChoices.IN_PROGRESS).count()\n"
        "            task_pending = assigned.filter(status=TaskStatusChoices.PENDING).count()\n"
        "            task_overdue = assigned.filter(\n"
        "                status__in=[TaskStatusChoices.PENDING, TaskStatusChoices.IN_PROGRESS],\n"
        "                deadline__lt=timezone.now(),\n"
        "            ).count()\n"
        "\n"
        "            # 借出统计\n"
        "            borrowed_total = user.borrowed_hardware.count()\n"
        "            borrowed_current = user.borrowed_hardware.filter(\n"
        "                status=BorrowStatusChoices.BORROWED,\n"
        "            ).count()\n"
        "\n"
        "            # 打卡统计\n"
        "            checkin_total = user.lab_checkins.count()\n"
        "            checkin_today = user.lab_checkins.filter(\n"
        "                created__date=today,\n"
        "            ).count()\n"
        "\n"
        "            # 项目统计\n"
        "            project_count = user.project_memberships.count() + user.led_projects.count()\n"
        "\n"
        "            # 最近活动\n"
        "            last_open = user.lab_open_records.order_by('-created').first()\n"
        "            last_checkin = user.lab_checkins.order_by('-created').first()\n"
        "\n",
        "",
    ),
    (
        "            if False:  # 占位：保持下方原有 append 结构\n",
        "",
    ),
])

# ── B. 会话删除路由 ───────────────────────────────────────────
patch('lab_manager/urls.py', [(
    "    path('agent/chat/', views.AgentChatProxyView.as_view(), name='agent_chat_proxy'),\n",
    "    path('agent/chat/', views.AgentChatProxyView.as_view(), name='agent_chat_proxy'),\n"
    "    path('agent-conversation/<int:pk>/delete/',\n"
    "         views.AgentConversationDeleteView.as_view(), name='agent_conversation_delete'),\n",
)])

# ── C. 打卡表单：补 tags 字段 + 提交需照片 ──────────────────────
patch('lab_manager/templates/lab_manager/checkin_form.html', [
    (
        "                    <button type=\"submit\" class=\"btn btn-success\" id=\"submit-button\" disabled>\n",
        "                    {% if form.tags %}\n"
        "                    <div class=\"mb-3\">\n"
        "                        <label class=\"form-label\" for=\"{{ form.tags.id_for_label }}\">{% trans \"标签\" %}</label>\n"
        "                        {{ form.tags }}\n"
        "                        {% if form.tags.errors %}<div class=\"text-danger small\">{{ form.tags.errors }}</div>{% endif %}\n"
        "                    </div>\n"
        "                    {% endif %}\n"
        "                    <button type=\"submit\" class=\"btn btn-success\" id=\"submit-button\" disabled>\n",
    ),
    (
        "    function enableSubmitIfReady() {\n"
        "        submitButton.disabled = !(latitude.value && longitude.value);\n"
        "    }\n",
        "    var photoInput = document.getElementById('id_photo');\n"
        "\n"
        "    function enableSubmitIfReady() {\n"
        "        var hasPhoto = !!(photoInput && photoInput.files && photoInput.files.length);\n"
        "        submitButton.disabled = !(latitude.value && longitude.value) || !hasPhoto;\n"
        "    }\n"
        "\n"
        "    if (photoInput) {\n"
        "        photoInput.addEventListener('change', enableSubmitIfReady);\n"
        "    }\n",
    ),
])

# ── D. 统计卡：无 JS 时也显示真实数值 ──────────────────────────
patch('lab_manager/templates/lab_manager/home.html', [],
      regex_pairs=[(r'data-target="\{\{ (\w+) \}\}">0</h3>', r'data-target="{{ \1 }}">{{ \1 }}</h3>', 10)])

# ── E. 导出命令补齐 borrow_records / projects ──────────────────
patch('lab_manager/management/commands/export_lab_data.py', [
    (
        "from lab_manager.models import CheckInRecord, Hardware, Task\n",
        "from lab_manager.models import (\n"
        "    CheckInRecord, Hardware, HardwareBorrowRecord, LabProject, Task,\n"
        ")\n",
    ),
    (
        "            choices=['hardware', 'tasks', 'checkins'],\n",
        "            choices=['hardware', 'tasks', 'checkins', 'borrow_records', 'projects'],\n",
    ),
    (
        "        elif model_name == 'checkins':\n"
        "            self._export_checkins(filename)\n",
        "        elif model_name == 'checkins':\n"
        "            self._export_checkins(filename)\n"
        "        elif model_name == 'borrow_records':\n"
        "            self._export_borrow_records(filename)\n"
        "        elif model_name == 'projects':\n"
        "            self._export_projects(filename)\n",
    ),
    (
        "    def _export_tasks(self, filename):\n",
        "    def _export_borrow_records(self, filename):\n"
        "        rows = HardwareBorrowRecord.objects.select_related('hardware', 'borrower').values_list(\n"
        "            'hardware__name', 'borrower__username', 'borrow_date', 'expected_return_date',\n"
        "            'actual_return_date', 'status', 'purpose', 'notes',\n"
        "        )\n"
        "        headers = ['硬件', '借用人', '借出时间', '预计归还', '实际归还', '状态', '用途', '备注']\n"
        "        self._write_csv(filename, headers, rows)\n"
        "        self.stdout.write(self.style.SUCCESS(f'借出记录已导出到 {filename}'))\n"
        "\n"
        "    def _export_projects(self, filename):\n"
        "        rows = LabProject.objects.select_related('leader').values_list(\n"
        "            'name', 'status', 'leader__username', 'start_date', 'end_date', 'description',\n"
        "        )\n"
        "        headers = ['项目名称', '状态', '负责人', '开始日期', '结束日期', '描述']\n"
        "        self._write_csv(filename, headers, rows)\n"
        "        self.stdout.write(self.style.SUCCESS(f'项目数据已导出到 {filename}'))\n"
        "\n"
        "    def _export_tasks(self, filename):\n",
    ),
])

# ── F. 关闭 Debug Toolbar（修测试报错 + 移动端遮挡）─────────────
for cfg in ['netbox/configuration.py', 'netbox/configuration_docker.py']:
    full = os.path.join(BASE, cfg)
    src = io.open(full, encoding='utf-8').read()
    if 'ENABLE_DEBUG_TOOLBAR' in src:
        report.append(f'  -- {cfg}: 已存在 ENABLE_DEBUG_TOOLBAR，跳过')
        continue
    new_src, n = _re.subn(
        r'(?m)^(DEBUG = .*)$',
        r'\1\n\n# 关闭 Django Debug Toolbar：它会遮挡窄屏页面控件，且导致 manage.py test 无法运行\n'
        r'ENABLE_DEBUG_TOOLBAR = False',
        src)
    if n == 1:
        if APPLY:
            io.open(full, 'w', encoding='utf-8', newline='').write(new_src)
        report.append(f'  ok {cfg}: 追加 ENABLE_DEBUG_TOOLBAR = False')
    else:
        failures.append(f'{cfg}: 未找到 DEBUG 行（{n} 次）')

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
