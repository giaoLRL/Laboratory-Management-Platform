"""导航补充：实时动态页 news 加入 NavItem。"""

from django.db import migrations


def apply(apps, schema_editor):
    NavItem = apps.get_model('accounts', 'NavItem')
    if not NavItem.objects.filter(pk='news').exists():
        NavItem.objects.create(pk='news', label='实时动态', icon='wifi',
                               permission='page:news', param='', enabled=True, order=0)


def rollback(apps, schema_editor):
    NavItem = apps.get_model('accounts', 'NavItem')
    NavItem.objects.filter(pk='news').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_grant_news_permissions'),
    ]

    operations = [
        migrations.RunPython(apply, rollback),
    ]