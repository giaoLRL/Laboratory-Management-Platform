"""批次3 数据正确性修复。"""
import io
import os
import sys

BASE = r'C:\Users\PC\Documents\实验室\netbox-main\netbox'
APPLY = '--apply' in sys.argv
report, failures = [], []


def patch(path, pairs):
    full = os.path.join(BASE, path)
    src = io.open(full, encoding='utf-8').read()
    orig = src
    for old, new in pairs:
        n = src.count(old)
        if n != 1:
            failures.append(f'{path}: 期望 1 次，实际 {n} 次 -> {old.strip().splitlines()[0][:70]!r}')
            continue
        src = src.replace(old, new)
        report.append(f'  ok {path}: {old.strip().splitlines()[0][:70]}')
    if src != orig and APPLY:
        io.open(full, 'w', encoding='utf-8', newline='').write(src)


# ── 1. 成员借出登记表单（不能指定借用人）────────────────────────
patch('lab_manager/forms/model_forms.py', [(
    "class LabProjectForm(NetBoxModelForm):\n",
    "class HardwareBorrowRecordMemberForm(NetBoxModelForm):\n"
    '    """成员借出登记表单：不允许指定借用人（强制为本人）"""\n'
    "\n"
    "    expected_return_date = django_forms.DateTimeField(\n"
    "        widget=DateTimePicker(),\n"
    "        required=False,\n"
    "        label='预计归还日期',\n"
    "    )\n"
    "\n"
    "    class Meta:\n"
    "        model = HardwareBorrowRecord\n"
    "        fields = (\n"
    "            'hardware', 'expected_return_date', 'purpose', 'notes', 'tags',\n"
    "        )\n"
    "        widgets = {\n"
    "            'purpose': django_forms.Textarea(attrs={'rows': 2, 'placeholder': '说明借用该硬件的目的'}),\n"
    "            'notes': django_forms.Textarea(attrs={'rows': 2, 'placeholder': '备注信息'}),\n"
    "        }\n"
    "\n"
    "\n"
    "class LabProjectForm(NetBoxModelForm):\n",
)])

# ── 2. views.py ────────────────────────────────────────────────
patch('lab_manager/views.py', [
    # 导入成员表单
    (
        "    AgentToolForm, CheckInForm, HardwareBorrowRecordForm, HardwareForm,\n",
        "    AgentToolForm, CheckInForm, HardwareBorrowRecordForm,\n"
        "    HardwareBorrowRecordMemberForm, HardwareForm,\n",
    ),
    # 打卡去重窗口常量
    (
        "def _client_ip(request):\n",
        "# 打卡防重复提交时间窗（秒）\n"
        "CHECKIN_DEDUPE_SECONDS = 60\n"
        "\n"
        "\n"
        "def _client_ip(request):\n",
    ),
    # 打卡统计口径：以 CheckInRecord 为准
    (
        "        ctx['today_checkins'] = today_records.filter(target_type='checkin').count()\n",
        "        # 打卡数直接以 CheckInRecord 为准（MemberOpenRecord 记录的是页面浏览行为，\n"
        "        # 浏览打卡详情页也曾被计入打卡数，导致统计虚高）\n"
        "        ctx['today_checkins'] = CheckInRecord.objects.filter(created__gte=today_start).count()\n",
    ),
    # 打卡详情：不存在 -> 404；浏览详情不再记为 checkin
    (
        "        record = CheckInRecord.objects.select_related('user').get(pk=self.kwargs['pk'])\n",
        "        record = get_object_or_404(\n"
        "            CheckInRecord.objects.select_related('user'), pk=self.kwargs['pk']\n"
        "        )\n",
    ),
    (
        "        record_member_open(request, page_title='打卡详情', target_type='checkin', target_id=record.pk)\n",
        "        record_member_open(request, page_title='打卡详情', target_type='checkin_detail', target_id=record.pk)\n",
    ),
    # 成员浏览记录详情：不存在 -> 404
    (
        "        self.record = MemberOpenRecord.objects.select_related('user').get(pk=self.kwargs['pk'])\n",
        "        self.record = get_object_or_404(\n"
        "            MemberOpenRecord.objects.select_related('user'), pk=self.kwargs['pk']\n"
        "        )\n",
    ),
    # 打卡防重复提交
    (
        "    def post(self, request):\n"
        "        form = CheckInForm(request.POST, request.FILES)\n"
        "        if form.is_valid():\n",
        "    def post(self, request):\n"
        "        # 防重复提交：时间窗内已有打卡记录则忽略本次提交（连点/刷新不会产生重复打卡）\n"
        "        if CheckInRecord.objects.filter(\n"
        "            user=request.user,\n"
        "            created__gte=timezone.now() - timedelta(seconds=CHECKIN_DEDUPE_SECONDS),\n"
        "        ).exists():\n"
        "            messages.warning(request, _('刚刚已完成打卡，请勿重复提交'))\n"
        "            return redirect('plugins:lab_manager:checkin_list')\n"
        "        form = CheckInForm(request.POST, request.FILES)\n"
        "        if form.is_valid():\n",
    ),
    # 评论：保存 m2m（tags 不再被丢弃）
    (
        "            comment.save()\n"
        "            messages.success(request, _('评论已发布'))\n",
        "            comment.save()\n"
        "            form.save_m2m()\n"
        "            messages.success(request, _('评论已发布'))\n",
    ),
    # 借出详情：归属校验
    (
        "@register_model_view(HardwareBorrowRecord)\n"
        "class HardwareBorrowRecordView(generic.ObjectView):\n"
        "    queryset = HardwareBorrowRecord.objects.select_related('hardware', 'borrower')\n"
        "\n"
        "    def has_permission(self):\n"
        "        return self.request.user.is_authenticated\n"
        "\n",
        "@register_model_view(HardwareBorrowRecord)\n"
        "class HardwareBorrowRecordView(generic.ObjectView):\n"
        "    queryset = HardwareBorrowRecord.objects.select_related('hardware', 'borrower')\n"
        "\n"
        "    def has_permission(self):\n"
        "        return self.request.user.is_authenticated\n"
        "\n"
        "    def get(self, request, *args, **kwargs):\n"
        "        obj = get_object_or_404(HardwareBorrowRecord, pk=kwargs['pk'])\n"
        "        if not request.user.is_superuser and request.user != obj.borrower:\n"
        "            messages.error(request, _('你没有权限查看此借出记录'))\n"
        "            return redirect('plugins:lab_manager:hardwareborrowrecord_list')\n"
        "        return super().get(request, *args, **kwargs)\n"
        "\n",
    ),
    # 借出编辑：角色表单 + 归属校验
    (
        "    def has_permission(self):\n"
        "        return self.request.user.is_authenticated\n"
        "\n"
        "    def alter_object(self, obj, request, url_args, url_kwargs):\n"
        "        if not obj.pk:\n"
        "            obj.borrower = request.user\n"
        "            obj.status = BorrowStatusChoices.BORROWED\n"
        "        return obj\n",
        "    def has_permission(self):\n"
        "        return self.request.user.is_authenticated\n"
        "\n"
        "    def _resolve_role(self, request):\n"
        "        # 普通成员用受限表单，不能把借用人改成别人\n"
        "        self.form = (\n"
        "            HardwareBorrowRecordForm if request.user.is_superuser\n"
        "            else HardwareBorrowRecordMemberForm\n"
        "        )\n"
        "\n"
        "    def _owner_denied(self, request):\n"
        "        if 'pk' not in self.kwargs:\n"
        "            return None\n"
        "        obj = get_object_or_404(HardwareBorrowRecord, pk=self.kwargs['pk'])\n"
        "        if not request.user.is_superuser and request.user != obj.borrower:\n"
        "            messages.error(request, _('你没有权限编辑此借出记录'))\n"
        "            return redirect('plugins:lab_manager:hardwareborrowrecord_list')\n"
        "        return None\n"
        "\n"
        "    def alter_object(self, obj, request, url_args, url_kwargs):\n"
        "        if not obj.pk:\n"
        "            obj.borrower = request.user\n"
        "            obj.status = BorrowStatusChoices.BORROWED\n"
        "        return obj\n"
        "\n"
        "    def get(self, request, *args, **kwargs):\n"
        "        self._resolve_role(request)\n"
        "        denied = self._owner_denied(request)\n"
        "        return denied or super().get(request, *args, **kwargs)\n"
        "\n"
        "    def post(self, request, *args, **kwargs):\n"
        "        self._resolve_role(request)\n"
        "        denied = self._owner_denied(request)\n"
        "        return denied or super().post(request, *args, **kwargs)\n",
    ),
])

# ── 3. models/borrow.py：删除记录时归还库存 ─────────────────────
patch('lab_manager/models/borrow.py', [(
    "                hardware.save(update_fields=['quantity', 'last_updated'])\n"
    "            super().save(*args, **kwargs)\n"
    "\n"
    "    def mark_returned(self, notes=''):\n",
    "                hardware.save(update_fields=['quantity', 'last_updated'])\n"
    "            super().save(*args, **kwargs)\n"
    "\n"
    "    def delete(self, *args, **kwargs):\n"
    '        """删除借出记录时归还其占用的库存。"""\n'
    "        restore = self.status == BorrowStatusChoices.BORROWED\n"
    "        with transaction.atomic():\n"
    "            result = super().delete(*args, **kwargs)\n"
    "            if restore:\n"
    "                hardware = Hardware.objects.select_for_update().get(pk=self.hardware_id)\n"
    "                hardware.quantity += 1\n"
    "                hardware.save(update_fields=['quantity', 'last_updated'])\n"
    "        return result\n"
    "\n"
    "    def mark_returned(self, notes=''):\n",
)])

# ── 4. api/views.py：模型校验错误转成 400 ───────────────────────
patch('lab_manager/api/views.py', [
    (
        "class HardwareBorrowRecordViewSet(NetBoxModelViewSet):\n"
        "    queryset = HardwareBorrowRecord.objects.prefetch_related('tags')\n"
        "    serializer_class = serializers.HardwareBorrowRecordSerializer\n",
        "class HardwareBorrowRecordViewSet(NetBoxModelViewSet):\n"
        "    queryset = HardwareBorrowRecord.objects.prefetch_related('tags')\n"
        "    serializer_class = serializers.HardwareBorrowRecordSerializer\n"
        "\n"
        "    def perform_create(self, serializer):\n"
        "        try:\n"
        "            serializer.save()\n"
        "        except DjangoValidationError as e:\n"
        "            raise DRFValidationError(getattr(e, 'messages', [str(e)]))\n"
        "\n"
        "    def perform_update(self, serializer):\n"
        "        try:\n"
        "            serializer.save()\n"
        "        except DjangoValidationError as e:\n"
        "            raise DRFValidationError(getattr(e, 'messages', [str(e)]))\n",
    ),
])

# api/views.py 顶部导入
full = os.path.join(BASE, 'lab_manager/api/views.py')
src = io.open(full, encoding='utf-8').read()
if 'DjangoValidationError' in src and 'from django.core.exceptions import ValidationError as DjangoValidationError' not in src:
    marker = 'from rest_framework.viewsets import ModelViewSet'
    if marker in src:
        src = src.replace(
            marker,
            'from django.core.exceptions import ValidationError as DjangoValidationError\n'
            'from rest_framework.exceptions import ValidationError as DRFValidationError\n'
            + marker, 1)
        report.append('  ok lab_manager/api/views.py: 补 ValidationError 导入')
    else:
        # 退路：在最后一行 import 之后插入
        lines = src.split('\n')
        idx = max(i for i, l in enumerate(lines) if l.startswith(('import ', 'from ')))
        lines.insert(idx + 1, 'from django.core.exceptions import ValidationError as DjangoValidationError')
        lines.insert(idx + 2, 'from rest_framework.exceptions import ValidationError as DRFValidationError')
        src = '\n'.join(lines)
        report.append('  ok lab_manager/api/views.py: 补 ValidationError 导入（退路插入）')
    if APPLY:
        io.open(full, 'w', encoding='utf-8', newline='').write(src)

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
