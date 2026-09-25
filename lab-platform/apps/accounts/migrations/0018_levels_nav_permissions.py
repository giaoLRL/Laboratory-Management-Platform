"""关卡接入：NavItem 菜单 + 内置角色授权（teacher/manager 可管理审核，member 可查看）。"""

from django.db import migrations

LEVEL_MENU = {
    'page:levels': ('levels', '关卡挑战', 'trophy', 'page:levels', ''),
    'action:level.manage': 'action:level.manage',
    'action:level.review': 'action:level.review',
}


def apply(apps, schema_editor):
    NavItem = apps.get_model('accounts', 'NavItem')
    Role = apps.get_model('accounts', 'Role')
    if not NavItem.objects.filter(pk='levels').exists():
        NavItem.objects.create(pk='levels', label='技能关卡', icon='trophy',
                               permission='page:levels', param='', enabled=True, order=99)
    for key in ('action:level.manage', 'action:level.review', 'page:levels'):
        for code in ('teacher', 'manager'):
            role = Role.objects.filter(code=code).first()
            if role:
                perms = list(role.permissions or [])
                if key not in perms:
                    perms.append(key)
                role.permissions = sorted(perms)
                role.save(update_fields=['permissions'])
        if key == 'page:levels':
            role = Role.objects.filter(code='member').first()
            if role:
                perms = list(role.permissions or [])
                if key not in perms:
                    perms.append(key)
                role.permissions = sorted(perms)
                role.save(update_fields=['permissions'])


def rollback(apps, schema_editor):
    NavItem = apps.get_model('accounts', 'NavItem')
    NavItem.objects.filter(pk='levels').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0017_add_homepage_nav'),
    ]

    operations = [
        migrations.RunPython(apply, rollback),
    ]