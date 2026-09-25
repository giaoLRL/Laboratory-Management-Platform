"""导航补充：主页管理页 homepage 加入 NavItem（仅 superadmin，permission 门控）。"""

from django.db import migrations


def apply(apps, schema_editor):
    NavItem = apps.get_model('accounts', 'NavItem')
    if not NavItem.objects.filter(pk='homepage').exists():
        NavItem.objects.create(pk='homepage', label='主页管理', icon='image',
                               permission='page:homepage', param='', enabled=True, order=0)


def rollback(apps, schema_editor):
    NavItem = apps.get_model('accounts', 'NavItem')
    NavItem.objects.filter(pk='homepage').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0016_memberprofile_must_complete_profile'),
    ]

    operations = [
        migrations.RunPython(apply, rollback),
    ]