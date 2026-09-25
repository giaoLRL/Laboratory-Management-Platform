"""可视化座位接入：NavItem 菜单 + 内置角色授权。

- member：可看座位图、挪位、设状态形象、冒气泡、大厅发言
- teacher / manager：额外获得 action:seats.manage（编辑布局 + 大厅撤回）
"""

from django.db import migrations

MEMBER_KEYS = ['page:seats', 'action:seats.move', 'action:seats.status',
               'action:seats.bubble', 'action:seats.chat']
STAFF_ADDS = ['action:seats.manage']


def _grant(Role, code, keys):
    role = Role.objects.filter(code=code).first()
    if not role:
        return
    perms = list(role.permissions or [])
    for key in keys:
        if key not in perms:
            perms.append(key)
    role.permissions = sorted(perms)
    role.save(update_fields=['permissions'])


def apply(apps, schema_editor):
    NavItem = apps.get_model('accounts', 'NavItem')
    Role = apps.get_model('accounts', 'Role')
    if not NavItem.objects.filter(pk='seats').exists():
        NavItem.objects.create(pk='seats', label='实验室座位', icon='pin',
                               permission='page:seats', param='', enabled=True, order=98)
    for code in ('member', 'teacher', 'manager'):
        _grant(Role, code, MEMBER_KEYS)
    for code in ('teacher', 'manager'):
        _grant(Role, code, STAFF_ADDS)


def rollback(apps, schema_editor):
    NavItem = apps.get_model('accounts', 'NavItem')
    Role = apps.get_model('accounts', 'Role')
    NavItem.objects.filter(pk='seats').delete()
    for code in ('member', 'teacher', 'manager'):
        role = Role.objects.filter(code=code).first()
        if not role:
            continue
        drop = set(MEMBER_KEYS) | set(STAFF_ADDS)
        role.permissions = sorted(k for k in (role.permissions or []) if k not in drop)
        role.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0021_operationlog_ref_id_operationlog_ref_type_and_more'),
    ]

    operations = [
        migrations.RunPython(apply, rollback),
    ]