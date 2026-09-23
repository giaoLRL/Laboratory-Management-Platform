"""导航补充：通知中心页 notifications 加入 NavItem。"""

from django.db import migrations


def apply(apps, schema_editor):
    NavItem = apps.get_model('accounts', 'NavItem')
    if not NavItem.objects.filter(pk='notifications').exists():
        NavItem.objects.create(pk='notifications', label='通知中心', icon='bell',
                               permission='page:notifications', param='', enabled=True, order=0)


def rollback(apps, schema_editor):
    NavItem = apps.get_model('accounts', 'NavItem')
    NavItem.objects.filter(pk='notifications').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0013_grant_notifications_permissions'),
    ]

    operations = [
        migrations.RunPython(apply, rollback),
    ]
