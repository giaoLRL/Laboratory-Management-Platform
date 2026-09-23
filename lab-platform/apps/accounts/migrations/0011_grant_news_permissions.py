"""实时动态权限：page:news 全员可见，action:news.manage 授予指导老师/负责人。"""

from django.db import migrations

STAFF_ADDS = ['page:news', 'action:news.manage']
MEMBER_ADDS = ['page:news']


def apply(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    for role in Role.objects.filter(code__in=('teacher', 'manager')):
        perms = list(role.permissions or [])
        for k in STAFF_ADDS:
            if k not in perms:
                perms.append(k)
        role.permissions = sorted(perms)
        role.save(update_fields=['permissions'])
    role = Role.objects.filter(code='member').first()
    if role:
        perms = list(role.permissions or [])
        for k in MEMBER_ADDS:
            if k not in perms:
                perms.append(k)
        role.permissions = sorted(perms)
        role.save(update_fields=['permissions'])


def rollback(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    for role in Role.objects.filter(code__in=('teacher', 'manager', 'member')):
        role.permissions = sorted(k for k in (role.permissions or []) if k not in STAFF_ADDS and k not in MEMBER_ADDS)
        role.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_grant_token_manage'),
        ('notify', '0002_newsitem'),
    ]

    operations = [
        migrations.RunPython(apply, rollback),
    ]