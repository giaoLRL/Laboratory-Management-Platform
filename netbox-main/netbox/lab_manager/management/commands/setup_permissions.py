"""
初始化实验室管理插件的 NetBox ObjectPermission。

运行: python manage.py setup_lab_permissions

创建 ObjectPermission 规则并自动分配给「实验室成员」组。
管理员只需在后台 Users > Groups 中将用户加入该组即可。
"""

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from users.models import Group, ObjectPermission


LAB_ACTIONS = [
    'view_task', 'add_task', 'change_task', 'delete_task',
    'view_hardware', 'add_hardware', 'change_hardware', 'delete_hardware',
    'view_taskcomment', 'add_taskcomment',
    'view_taskattachment', 'add_taskattachment', 'delete_taskattachment',
]


def _make_perm(name, desc, actions, cts, constraints=None, group=None):
    perm = ObjectPermission.objects.create(
        name=name,
        description=desc,
        enabled=True,
        actions=actions,
        constraints=constraints,
    )
    perm.object_types.set(cts)
    if group:
        group.object_permissions.add(perm)
    return perm


class Command(BaseCommand):
    help = '初始化实验室管理插件的 ObjectPermission'

    def handle(self, **options):
        from lab_manager.models import Task, Hardware, TaskAttachment, TaskComment

        # ── 清理旧权限 ──
        deleted = ObjectPermission.objects.filter(actions__overlap=LAB_ACTIONS).delete()
        if deleted[0]:
            self.stdout.write(f'  已清理 {deleted[0]} 条旧权限')

        # ── 获取或创建默认组 ──
        group, created = Group.objects.get_or_create(
            name='实验室成员',
            defaults={'description': '实验室管理系统默认用户组'},
        )
        if created:
            self.stdout.write('  已创建「实验室成员」组')

        task_ct = ContentType.objects.get_for_model(Task)
        hw_ct = ContentType.objects.get_for_model(Hardware)
        att_ct = ContentType.objects.get_for_model(TaskAttachment)
        cmt_ct = ContentType.objects.get_for_model(TaskComment)

        # ── 1. 查看权限 ──
        _make_perm(
            '实验室 - 查看全部',
            '所有认证用户可查看任务、硬件、附件和评论',
            ['view_task', 'view_hardware', 'view_taskattachment', 'view_taskcomment'],
            [task_ct, hw_ct, att_ct, cmt_ct],
            group=group,
        )
        self.stdout.write('  [OK] 查看权限')

        # ── 2. 发布任务 + 评论 ──
        _make_perm(
            '实验室 - 发布任务和评论',
            '所有成员可发布任务和评论',
            ['add_task', 'add_taskcomment'],
            [task_ct, cmt_ct],
            group=group,
        )
        self.stdout.write('  [OK] 发布任务/评论')

        # ── 3. 编辑自己的任务 ──
        _make_perm(
            '实验室 - 编辑自己的任务',
            '仅任务创建人可编辑',
            ['change_task'],
            [task_ct],
            constraints={'created_by': '$user'},
            group=group,
        )
        self.stdout.write('  [OK] 编辑任务 (创建人约束)')

        # ── 4. 编辑被分配的任务 ──
        _make_perm(
            '实验室 - 编辑被分配的任务',
            '被分配任务的用户可编辑',
            ['change_task'],
            [task_ct],
            constraints={'assigned_to': '$user'},
            group=group,
        )
        self.stdout.write('  [OK] 编辑任务 (被分配者约束)')

        # ── 5. 管理附件 ──
        _make_perm(
            '实验室 - 管理附件',
            '成员可上传/删除任务附件',
            ['add_taskattachment', 'delete_taskattachment', 'view_taskattachment'],
            [att_ct],
            group=group,
        )
        self.stdout.write('  [OK] 附件管理')

        # ── 6. 添加硬件（所有人） ──
        _make_perm(
            '实验室 - 添加硬件',
            '所有成员可提交硬件（待审核）',
            ['add_hardware'],
            [hw_ct],
            group=group,
        )
        self.stdout.write('  [OK] 添加硬件 — 所有成员')

        # ── 7. 编辑硬件（提交人） ──
        _make_perm(
            '实验室 - 编辑自己的硬件',
            '仅提交人可编辑自己待审核的硬件',
            ['change_hardware'],
            [hw_ct],
            constraints={'submitted_by': '$user'},
            group=group,
        )
        self.stdout.write('  [OK] 编辑硬件 — 提交人约束')

        # ── 8. 删除硬件（仅分配，不加入默认组） ──
        _make_perm(
            '实验室 - 删除硬件',
            '管理员专用：删除硬件',
            ['delete_hardware'],
            [hw_ct],
        )
        self.stdout.write('  [OK] 删除硬件（不计入默认组，需后台手动分配）')

        # ── 9. 删除任务（仅分配，不加入默认组） ──
        _make_perm(
            '实验室 - 删除任务',
            '管理员专用：删除任务',
            ['delete_task'],
            [task_ct],
        )
        self.stdout.write('  [OK] 删除任务（不计入默认组，需后台手动分配）')

        self.stdout.write(self.style.SUCCESS(
            f'\n权限初始化完成。'
            f'\n'
            f'\n「实验室成员」组已自动获得：查看、发布任务、评论、编辑自己任务、管理附件。'
            f'\n请在后台 Users > Groups 中将用户加入「实验室成员」组即可。'
            f'\n'
            f'\n硬件管理和删除任务权限需在后台手动分配给管理员用户或组。'
        ))
