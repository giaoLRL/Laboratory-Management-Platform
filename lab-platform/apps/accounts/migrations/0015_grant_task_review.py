"""给内置角色补充新增权限点：老师/管理员 += 任务审核。"""

from django.db import migrations

TASK_REVIEW = 'action:task.review'
STAFF_ADDS = [TASK_REVIEW]


def apply(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    for role in Role.objects.filter(code__in=('teacher', 'manager')):
        perms = list(role.permissions or [])
        for k in STAFF_ADDS:
            if k not in perms:
                perms.append(k)
        role.permissions = sorted(perms)
        role.save(update_fields=['permissions'])


def rollback(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    for role in Role.objects.filter(code__in=('teacher', 'manager')):
        perms = list(role.permissions or [])
        role.permissions = sorted(k for k in perms if k not in STAFF_ADDS)
        role.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0014_notifications_nav'),
    ]

    operations = [
        migrations.RunPython(apply, rollback),
    ]
