"""API 令牌权限：action:token.manage 授予全部内置角色（每个人管理自己的令牌）。"""

from django.db import migrations

TOKEN_KEY = 'action:token.manage'


def apply(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    for role in Role.objects.filter(code__in=('teacher', 'manager', 'member')):
        perms = list(role.permissions or [])
        if TOKEN_KEY not in perms:
            perms.append(TOKEN_KEY)
        role.permissions = sorted(perms)
        role.save(update_fields=['permissions'])


def rollback(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    for role in Role.objects.filter(code__in=('teacher', 'manager', 'member')):
        role.permissions = sorted(k for k in (role.permissions or []) if k != TOKEN_KEY)
        role.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_apitoken'),
    ]

    operations = [
        migrations.RunPython(apply, rollback),
    ]