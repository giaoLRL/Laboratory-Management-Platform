"""批次1 语义修复补丁。每条替换都断言"恰好命中一次"，避免误改。

覆盖：
 views.py           借出归还视图 404 / 评论视图仅 POST / 通知已读改 POST+防开放重定向 /
                    日历参数容错 / AgentTool 批量视图 detail=False / _safe_int 与 _safe_redirect_target 辅助函数
 __init__.py        注册 signals
 models/borrow.py   修复 BorrowStatusChoices 属性错误 + 借出扣减/归还回补库存 + clean 校验
 models/hardware.py 记录审批状态快照（供信号判断真实变化）
 signals.py         硬件审批通知只在状态真正变化时发送
 agent_api.py       JSON 顶层类型校验 + 令牌用户需 is_active
 templates/.../notification_list.html  全部已读改为 POST 表单
"""
import io
import os
import re
import sys

BASE = r'C:\Users\PC\Documents\实验室\netbox-main\netbox'
PLUGIN = os.path.join(BASE, 'lab_manager')
APPLY = '--apply' in sys.argv
report = []


def patch(path, pairs, regex_pairs=()):
    full = os.path.join(BASE, path)
    src = io.open(full, encoding='utf-8').read()
    orig = src
    for old, new in pairs:
        n = src.count(old)
        if n != 1:
            report.append(f'  !! {path}: 期望命中 1 次，实际 {n} 次 -> {old[:70]!r}')
            continue
        src = src.replace(old, new)
        report.append(f'  ok {path}: {old.strip().splitlines()[0][:72]}')
    for pat, new, expect in regex_pairs:
        src, n = re.subn(pat, new, src)
        if n != expect:
            report.append(f'  !! {path}: 正则期望 {expect} 次，实际 {n} 次 -> {pat[:60]}')
        else:
            report.append(f'  ok {path}(regex): {pat[:60]}')
    if src != orig:
        if APPLY:
            io.open(full, 'w', encoding='utf-8', newline='').write(src)
        return True
    return False


# ── 1. views.py ────────────────────────────────────────────────
HELPERS = '''
def _safe_int(value, default, minimum=None, maximum=None):
    """把 GET 参数安全地转成整数并夹取范围；非法输入回退默认值，绝不抛异常。"""
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def _safe_redirect_target(url):
    """只允许站内相对路径，避免开放重定向。"""
    if not url:
        return None
    if url.startswith('/') and not url.startswith('//'):
        return url
    return None

'''

patch('lab_manager/views.py', [
    # (a) 归还视图：对象不存在 -> 404（原来 500），且匿名也拿不到 500
    (
        "        record = HardwareBorrowRecord.objects.select_related('hardware', 'borrower').get(pk=self.kwargs['pk'])",
        "        record = get_object_or_404(\n"
        "            HardwareBorrowRecord.objects.select_related('hardware', 'borrower'),\n"
        "            pk=self.kwargs['pk'],\n"
        "        )",
    ),
    # (b) 评论视图：GET 返回 405 而不是 500（缺 template_name）
    (
        'class TaskCommentView(LoginRequiredMixin, TemplateView):\n'
        '    """提交评论 — 所有人可评论"""\n',
        'class TaskCommentView(LoginRequiredMixin, View):\n'
        '    """提交评论 — 所有人可评论（仅接受 POST）"""\n\n'
        "    http_method_names = ['post', 'head', 'options']\n",
    ),
    # (c) 通知已读：read-all 严格 POST + 防开放重定向
    (
        "class NotificationMarkReadView(LoginRequiredMixin, View):\n"
        "    def post(self, request):\n"
        "        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)\n"
        "        return JsonResponse({'ok': True})\n"
        "\n"
        "    def get(self, request, pk=None):\n"
        "        # pk=None → 全部已读（来自 /notifications/read-all/）\n"
        "        if pk is None:\n"
        "            Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)\n"
        "            return redirect('plugins:lab_manager:notifications')\n"
        "        notif = get_object_or_404(Notification, pk=pk, user=request.user)\n"
        "        if not notif.is_read:\n"
        "            notif.is_read = True\n"
        "            notif.save(update_fields=['is_read'])\n"
        "        if notif.link:\n"
        "            return redirect(notif.link)\n"
        "        return redirect('plugins:lab_manager:notifications')\n",
        "class NotificationMarkReadView(LoginRequiredMixin, View):\n"
        '    """标记通知已读。\n'
        "\n"
        "    - POST /notifications/read-all/ → 全部已读（不接受 GET，避免被 <img> 之类触发状态变更）\n"
        "    - POST /notifications/<pk>/read/ → 单条已读\n"
        "    - GET  /notifications/<pk>/read/ → 单条已读并跳转（纯导航，只影响本人的已读标记）\n"
        '    """\n'
        "\n"
        "    def post(self, request, pk=None):\n"
        "        if pk is None:\n"
        "            Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)\n"
        "            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':\n"
        "                return JsonResponse({'ok': True})\n"
        "            messages.success(request, _('已全部标为已读'))\n"
        "            return redirect('plugins:lab_manager:notifications')\n"
        "        return self._mark_single(request, pk)\n"
        "\n"
        "    def get(self, request, pk=None):\n"
        "        if pk is None:\n"
        "            return HttpResponseNotAllowed(['POST'])\n"
        "        return self._mark_single(request, pk)\n"
        "\n"
        "    def _mark_single(self, request, pk):\n"
        "        notif = get_object_or_404(Notification, pk=pk, user=request.user)\n"
        "        if not notif.is_read:\n"
        "            notif.is_read = True\n"
        "            notif.save(update_fields=['is_read'])\n"
        "        return redirect(_safe_redirect_target(notif.link) or 'plugins:lab_manager:notifications')\n",
    ),
    # (d) 日历 year/month 容错
    (
        "        today = timezone.localdate()\n"
        "        year = int(self.request.GET.get('year', today.year))\n"
        "        month = int(self.request.GET.get('month', today.month))\n"
        "        # 限制范围\n"
        "        month = max(1, min(12, month))\n",
        "        today = timezone.localdate()\n"
        "        year = _safe_int(self.request.GET.get('year'), today.year, minimum=1970, maximum=2999)\n"
        "        month = _safe_int(self.request.GET.get('month'), today.month, minimum=1, maximum=12)\n",
    ),
    # (e) AgentTool 批量视图：detail=False（NetBox 框架惯例）
    (
        "@register_model_view(AgentTool, 'bulk_delete')\nclass AgentToolBulkDeleteView(generic.BulkDeleteView):",
        "@register_model_view(AgentTool, 'bulk_delete', path='bulk-delete', detail=False)\n"
        "class AgentToolBulkDeleteView(generic.BulkDeleteView):",
    ),
    (
        "@register_model_view(AgentTool, 'bulk_edit')\nclass AgentToolBulkEditView(generic.BulkEditView):",
        "@register_model_view(AgentTool, 'bulk_edit', path='bulk-edit', detail=False)\n"
        "class AgentToolBulkEditView(generic.BulkEditView):",
    ),
    # (f) 辅助函数 + HttpResponseNotAllowed 导入
    (
        "from django.http import JsonResponse\n",
        "from django.http import HttpResponseNotAllowed, JsonResponse\n",
    ),
    (
        "# ── Hardware ──\n",
        HELPERS + "# ── Hardware ──\n",
    ),
], regex_pairs=[
    (r"cal_year = int\(self\.request\.GET\.get\('cal_year', ([^)]+)\)\)",
     r"cal_year = _safe_int(self.request.GET.get('cal_year'), \1, minimum=1970, maximum=2999)", 1),
    (r"cal_month = int\(self\.request\.GET\.get\('cal_month', ([^)]+)\)\)",
     r"cal_month = _safe_int(self.request.GET.get('cal_month'), \1, minimum=1, maximum=12)", 1),
])

# ── 2. __init__.py：注册 signals ────────────────────────────────
patch('lab_manager/__init__.py', [
    (
        "    def ready(self):\n        super().ready()\n",
        "    def ready(self):\n"
        "        super().ready()\n"
        "        # 插件不会自动发现 signals.py，必须显式导入才能注册接收器\n"
        "        from . import signals  # noqa: F401\n",
    ),
])

# ── 3. models/borrow.py：属性错误 + 库存扣减 ────────────────────
patch('lab_manager/models/borrow.py', [
    (
        "from django.db import models\nfrom django.urls import reverse\n",
        "from django.core.exceptions import ValidationError\n"
        "from django.db import models, transaction\n"
        "from django.urls import reverse\n",
    ),
    (
        "    @property\n"
        "    def is_overdue(self):\n"
        "        from django.utils import timezone\n"
        "        if self.status != self.BorrowStatusChoices.BORROWED:\n"
        "            return False\n"
        "        if self.expected_return_date:\n"
        "            return timezone.now() > self.expected_return_date\n"
        "        return False\n"
        "\n"
        "    def mark_returned(self, notes=''):\n"
        "        from django.utils import timezone\n"
        "        self.status = self.BorrowStatusChoices.RETURNED\n"
        "        self.actual_return_date = timezone.now()\n"
        "        if notes:\n"
        "            self.notes = notes\n"
        "        self.save(update_fields=['status', 'actual_return_date', 'notes'])\n",
        "    @property\n"
        "    def is_overdue(self):\n"
        "        if self.status != BorrowStatusChoices.BORROWED:\n"
        "            return False\n"
        "        if self.expected_return_date:\n"
        "            from django.utils import timezone\n"
        "            return timezone.now() > self.expected_return_date\n"
        "        return False\n"
        "\n"
        "    def clean(self):\n"
        "        super().clean()\n"
        "        # 借出前校验可用库存（quantity 表示在库可用数量）\n"
        "        if self._state.adding and self.status == BorrowStatusChoices.BORROWED and self.hardware_id:\n"
        "            hardware = Hardware.objects.filter(pk=self.hardware_id).only('quantity').first()\n"
        "            if hardware is not None and hardware.quantity < 1:\n"
        "                raise ValidationError({'hardware': _('该硬件当前可用数量为 0，无法借出。')})\n"
        "\n"
        "    def save(self, *args, **kwargs):\n"
        "        \"\"\"借出时扣减库存、归还时回补库存（行级锁 + 事务，避免并发超借）。\"\"\"\n"
        "        creating = self._state.adding\n"
        "        previous_status = None\n"
        "        if not creating and self.pk:\n"
        "            previous_status = (\n"
        "                HardwareBorrowRecord.objects.filter(pk=self.pk)\n"
        "                .values_list('status', flat=True).first()\n"
        "            )\n"
        "        becomes_borrowed = self.status == BorrowStatusChoices.BORROWED\n"
        "        was_borrowed = previous_status == BorrowStatusChoices.BORROWED\n"
        "\n"
        "        if becomes_borrowed and not was_borrowed:\n"
        "            delta = -1\n"
        "        elif was_borrowed and not becomes_borrowed:\n"
        "            delta = 1\n"
        "        else:\n"
        "            delta = 0\n"
        "\n"
        "        with transaction.atomic():\n"
        "            if delta:\n"
        "                hardware = Hardware.objects.select_for_update().get(pk=self.hardware_id)\n"
        "                new_quantity = hardware.quantity + delta\n"
        "                if new_quantity < 0:\n"
        "                    raise ValidationError(_('该硬件当前可用数量为 0，无法借出。'))\n"
        "                hardware.quantity = new_quantity\n"
        "                hardware.save(update_fields=['quantity', 'last_updated'])\n"
        "            super().save(*args, **kwargs)\n"
        "\n"
        "    def mark_returned(self, notes=''):\n"
        "        from django.utils import timezone\n"
        "        self.status = BorrowStatusChoices.RETURNED\n"
        "        self.actual_return_date = timezone.now()\n"
        "        if notes:\n"
        "            self.notes = notes\n"
        "        self.save(update_fields=['status', 'actual_return_date', 'notes'])\n",
    ),
])

# ── 4. models/hardware.py：审批状态快照 ─────────────────────────
patch('lab_manager/models/hardware.py', [
    (
        'class Hardware(NetBoxModel):\n    """硬件资源"""\n    name = models.CharField(',
        'class Hardware(NetBoxModel):\n'
        '    """硬件资源"""\n'
        '\n'
        '    def __init__(self, *args, **kwargs):\n'
        '        super().__init__(*args, **kwargs)\n'
        '        # 记录加载时的审批状态，供 signals 判断状态是否真的发生变化\n'
        '        self._previous_approval_status = self.approval_status\n'
        '\n'
        '    @classmethod\n'
        '    def from_db(cls, db, field_names, values):\n'
        '        instance = super().from_db(db, field_names, values)\n'
        '        instance._previous_approval_status = instance.approval_status\n'
        '        return instance\n'
        '\n'
        '    name = models.CharField(',
    ),
])

# ── 5. signals.py：只在审批状态真正变化时通知 ───────────────────
patch('lab_manager/signals.py', [
    (
        '@receiver(post_save, sender=Hardware)\n'
        'def notify_hardware_approved(sender, instance, **kwargs):\n'
        '    """硬件审批状态变更时通知提交人。"""\n'
        '    from django.db import transaction\n'
        '    # 只在实际状态变更时通知\n'
        '    if instance.approval_status == HardwareApprovalStatusChoices.APPROVED and instance.submitted_by:\n',
        '@receiver(post_save, sender=Hardware)\n'
        'def notify_hardware_approved(sender, instance, created=False, **kwargs):\n'
        '    """硬件审批状态**发生变化**时通知提交人（新建不通知，避免批量导入刷屏）。"""\n'
        '    previous = getattr(instance, \'_previous_approval_status\', None)\n'
        '    if created or previous == instance.approval_status:\n'
        '        return\n'
        '    instance._previous_approval_status = instance.approval_status\n'
        '    if instance.approval_status == HardwareApprovalStatusChoices.APPROVED and instance.submitted_by:\n',
    ),
])

# ── 6. agent_api.py：JSON 顶层类型 + 令牌用户有效性 ─────────────
patch('lab_manager/agent_api.py', [
    (
        "        try:\n"
        "            raw_body = request.body.decode('utf-8') if request.body else '{}'\n"
        "            return json.loads(raw_body or '{}')\n"
        "        except (UnicodeDecodeError, json.JSONDecodeError):\n"
        "            return self.error_response('请求体不是合法 JSON', code='40001', status=400)\n",
        "        try:\n"
        "            raw_body = request.body.decode('utf-8') if request.body else '{}'\n"
        "            payload = json.loads(raw_body or '{}')\n"
        "        except (UnicodeDecodeError, json.JSONDecodeError):\n"
        "            return self.error_response('请求体不是合法 JSON', code='40001', status=400)\n"
        "        if not isinstance(payload, dict):\n"
        "            return self.error_response('请求体必须是 JSON 对象', code='40001', status=400)\n"
        "        return payload\n",
    ),
    (
        "            return User.objects.get(pk=user_id)\n",
        "            return User.objects.get(pk=user_id, is_active=True)\n",
    ),
])

# ── 7. 通知模板：全部已读改 POST ────────────────────────────────
patch('lab_manager/templates/lab_manager/notification_list.html', [
    (
        '      <a href="{% url \'plugins:lab_manager:notification_read_all\' %}" class="btn btn-outline-primary">\n'
        '        <i class="mdi mdi-check-all"></i> {% trans "全部标为已读" %}\n'
        '      </a>\n',
        '      <form method="post" action="{% url \'plugins:lab_manager:notification_read_all\' %}" class="d-inline">\n'
        '        {% csrf_token %}\n'
        '        <button type="submit" class="btn btn-outline-primary">\n'
        '          <i class="mdi mdi-check-all"></i> {% trans "全部标为已读" %}\n'
        '        </button>\n'
        '      </form>\n',
    ),
])

print('\n'.join(report))
print()
bad = [r for r in report if r.strip().startswith('!!')]
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(bad)} 条')
sys.exit(1 if bad else 0)
