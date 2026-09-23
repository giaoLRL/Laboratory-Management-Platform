"""智能体代操作权限：action:agent.operate 授予指导老师与负责人。"""

from django.db import migrations

STAFF_ADDS = ['action:agent.operate']


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
        role.permissions = sorted(k for k in (role.permissions or []) if k not in STAFF_ADDS)
        role.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_grant_email_permissions'),
    ]

    operations = [
        migrations.RunPython(apply, rollback),
    ]