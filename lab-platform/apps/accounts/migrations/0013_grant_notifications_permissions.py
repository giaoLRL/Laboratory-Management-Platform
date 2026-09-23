"""通知中心权限：page:notifications 全员可见（借用/请假/任务等成员都能看自己的通知）。"""

from django.db import migrations


def apply(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    for role in Role.objects.filter(code__in=('teacher', 'manager', 'member')):
        perms = list(role.permissions or [])
        if 'page:notifications' not in perms:
            perms.append('page:notifications')
        role.permissions = sorted(perms)
        role.save(update_fields=['permissions'])


def rollback(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    for role in Role.objects.filter(code__in=('teacher', 'manager', 'member')):
        role.permissions = sorted(k for k in (role.permissions or []) if k != 'page:notifications')
        role.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_add_news_nav'),
    ]

    operations = [
        migrations.RunPython(apply, rollback),
    ]
