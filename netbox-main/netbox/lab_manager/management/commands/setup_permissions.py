"""
初始化实验室管理插件的 NetBox ObjectPermission。

运行: python manage.py setup_permissions

创建 ObjectPermission 规则并自动分配给「实验室成员」组。
管理员只需在后台 Users > Groups 中将用户加入该组即可。

注意：NetBox 的 ObjectPermission.actions 只能填动作动词
（view / add / change / delete），后端会拼成
``<app_label>.<action>_<model>``。早期版本这里误填了
"view_hardware" 之类的完整权限名，导致生成
``lab_manager.view_hardware_hardware`` 这种永远匹配不到的权限，
成员因此无法在任何受限表单里选择硬件。
"""

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from users.models import Group, ObjectPermission


class Command(BaseCommand):
    help = '初始化实验室管理插件的 ObjectPermission'

    def handle(self, **options):
        from lab_manager.models import Task, Hardware, TaskAttachment, TaskComment

        # ── 清理旧的 lab_manager 权限（只按对象类型筛，绝不影响其他应用的权限）──
        old = ObjectPermission.objects.filter(object_types__app_label='lab_manager').distinct()
        deleted = old.delete()
        if deleted[0]:
            self.stdout.write(f'  已清理 {deleted[0]} 条旧对象记录')

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

        def make(name, desc, actions, cts, constraints=None, group=None):
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

        # 1. 查看
        make('实验室 - 查看全部', '所有认证用户可查看任务、硬件、附件和评论',
             ['view'], [task_ct, hw_ct, att_ct, cmt_ct], group=group)
        self.stdout.write('  [OK] 查看权限（view）')

        # 2. 评论（任务发布仅限管理员，与 views.py 的路由限制保持一致）
        make('实验室 - 发表评论', '所有成员可对任务发表评论',
             ['add'], [cmt_ct], group=group)
        self.stdout.write('  [OK] 发表评论（add taskcomment）')

        # 3. 编辑任务（创建人 / 被分配人）
        make('实验室 - 编辑自己的任务', '仅任务创建人可编辑',
             ['change'], [task_ct], constraints={'created_by': '$user'}, group=group)
        make('实验室 - 编辑被分配的任务', '被分配任务的用户可编辑',
             ['change'], [task_ct], constraints={'assigned_to': '$user'}, group=group)
        self.stdout.write('  [OK] 编辑任务（创建人/被分配人约束）')

        # 4. 附件：上传/查看 + 受限删除
        make('实验室 - 上传附件', '成员可上传并查看任务附件',
             ['add', 'view'], [att_ct], group=group)
        make('实验室 - 删除自己任务的附件', '仅任务创建人可删除附件',
             ['delete'], [att_ct], constraints={'task__created_by': '$user'}, group=group)
        make('实验室 - 删除被分配任务的附件', '任务执行人可删除所负责任务的附件',
             ['delete'], [att_ct], constraints={'task__assigned_to': '$user'}, group=group)
        self.stdout.write('  [OK] 附件上传/查看 + 受限删除')

        # 5. 硬件
        make('实验室 - 添加硬件', '所有成员可提交硬件（待审核）',
             ['add'], [hw_ct], group=group)
        make('实验室 - 编辑自己的硬件', '仅提交人可编辑自己待审核的硬件',
             ['change'], [hw_ct], constraints={'submitted_by': '$user'}, group=group)
        make('实验室 - 删除硬件', '管理员专用：删除硬件', ['delete'], [hw_ct])
        self.stdout.write('  [OK] 硬件：添加/编辑（提交人约束）+ 删除（需手动分配）')

        # 6. 任务删除（不加入默认组）
        make('实验室 - 删除任务', '管理员专用：删除任务', ['delete'], [task_ct])
        self.stdout.write('  [OK] 删除任务（不计入默认组，需后台手动分配）')

        self.stdout.write(self.style.SUCCESS(
            '\n权限初始化完成。\n'
            '\n「实验室成员」组已获得：查看、评论、编辑自己/被分配的任务、管理附件、提交硬件。'
            '\n请在后台 Users > Groups 中把成员加入「实验室成员」组。'
            '\n硬件删除、任务删除权限需在后台手动分配给管理员用户或组。'
        ))
