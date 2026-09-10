"""批次3b：库存回补改用 post_delete 信号（QuerySet.delete 不走 Model.delete）、
REST 审批字段只读、权限初始化命令修正。"""
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


# ── 1. 去掉 Model.delete() 覆盖（QuerySet.delete 不会调用它）────
patch('lab_manager/models/borrow.py', [(
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
    "    def mark_returned(self, notes=''):\n",
)])

# ── 2. post_delete 信号回补库存（覆盖 QuerySet.delete / 级联删除）──
patch('lab_manager/signals.py', [
    (
        "from django.db.models.signals import post_save, pre_delete\n",
        "from django.db import transaction\nfrom django.db.models.signals import post_delete, post_save, pre_delete\n",
    ),
    (
        "from .choices import HardwareApprovalStatusChoices\n",
        "from .choices import HardwareApprovalStatusChoices\nfrom .models.borrow import BorrowStatusChoices\n",
    ),
    (
        "# ── 通知信号 ──\n",
        "@receiver(post_delete, sender=HardwareBorrowRecord)\n"
        "def restore_hardware_stock(sender, instance, **kwargs):\n"
        '    """借出记录被删除时把占用的库存加回去。\n'
        "\n"
        "    必须用信号实现：QuerySet.delete() 不会调用 Model.delete()。\n"
        '    """\n'
        "    if instance.status != BorrowStatusChoices.BORROWED or not instance.hardware_id:\n"
        "        return\n"
        "    try:\n"
        "        with transaction.atomic():\n"
        "            hardware = Hardware.objects.select_for_update().get(pk=instance.hardware_id)\n"
        "            hardware.quantity += 1\n"
        "            hardware.save(update_fields=['quantity', 'last_updated'])\n"
        "    except Hardware.DoesNotExist:\n"
        "        # 硬件本身正在被删除（级联），无需回补\n"
        "        pass\n"
        "\n"
        "\n"
        "# ── 通知信号 ──\n",
    ),
])

# ── 3. REST：审批相关字段只读（成员不能自助审批）────────────────
patch('lab_manager/api/serializers.py', [(
    "        brief_fields = ('id', 'display', 'name', 'category', 'status', 'approval_status')\n",
    "        brief_fields = ('id', 'display', 'name', 'category', 'status', 'approval_status')\n"
    "        # 审批结果只能通过审批视图/管理界面产生，禁止经 REST 自助审批\n"
    "        read_only_fields = ('approval_status', 'approved_by', 'approval_note', 'submitted_by')\n",
)])

# ── 4. 权限初始化命令修正 ──────────────────────────────────────
patch('lab_manager/management/commands/setup_permissions.py', [
    (
        "运行: python manage.py setup_lab_permissions\n",
        "运行: python manage.py setup_permissions\n",
    ),
    (
        "        # ── 2. 发布任务 + 评论 ──\n"
        "        _make_perm(\n"
        "            '实验室 - 发布任务和评论',\n"
        "            '所有成员可发布任务和评论',\n"
        "            ['add_task', 'add_taskcomment'],\n"
        "            [task_ct, cmt_ct],\n"
        "            group=group,\n"
        "        )\n"
        "        self.stdout.write('  [OK] 发布任务/评论')\n",
        "        # ── 2. 评论（任务发布仅限管理员，与 views.py 的路由限制保持一致）──\n"
        "        _make_perm(\n"
        "            '实验室 - 发表评论',\n"
        "            '所有成员可对任务发表评论',\n"
        "            ['add_taskcomment'],\n"
        "            [cmt_ct],\n"
        "            group=group,\n"
        "        )\n"
        "        self.stdout.write('  [OK] 发表评论')\n",
    ),
    (
        "        # ── 5. 管理附件 ──\n"
        "        _make_perm(\n"
        "            '实验室 - 管理附件',\n"
        "            '成员可上传/删除任务附件',\n"
        "            ['add_taskattachment', 'delete_taskattachment', 'view_taskattachment'],\n"
        "            [att_ct],\n"
        "            group=group,\n"
        "        )\n"
        "        self.stdout.write('  [OK] 附件管理')\n",
        "        # ── 5. 管理附件（删除限定为任务创建人或执行人）──\n"
        "        _make_perm(\n"
        "            '实验室 - 上传附件',\n"
        "            '成员可上传并查看任务附件',\n"
        "            ['add_taskattachment', 'view_taskattachment'],\n"
        "            [att_ct],\n"
        "            group=group,\n"
        "        )\n"
        "        _make_perm(\n"
        "            '实验室 - 删除自己任务的附件',\n"
        "            '仅任务创建人可删除附件',\n"
        "            ['delete_taskattachment'],\n"
        "            [att_ct],\n"
        "            constraints={'task__created_by': '$user'},\n"
        "            group=group,\n"
        "        )\n"
        "        _make_perm(\n"
        "            '实验室 - 删除被分配任务的附件',\n"
        "            '任务执行人可删除所负责任务的附件',\n"
        "            ['delete_taskattachment'],\n"
        "            [att_ct],\n"
        "            constraints={'task__assigned_to': '$user'},\n"
        "            group=group,\n"
        "        )\n"
        "        self.stdout.write('  [OK] 附件上传/查看 + 受限删除')\n",
    ),
])

print('\n'.join(report))
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
sys.exit(1 if failures else 0)
