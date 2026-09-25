"""种子化「借用逾期惩罚」积分规则（负分，默认 -10）。"""

from django.db import migrations


def seed(apps, schema_editor):
    PointRule = apps.get_model('points', 'PointRule')
    PointRule.objects.get_or_create(key='loan_overdue_penalty',
                                    defaults={'label': '借用逾期惩罚', 'points': -10, 'enabled': True})


def unseed(apps, schema_editor):
    PointRule = apps.get_model('points', 'PointRule')
    PointRule.objects.filter(key='loan_overdue_penalty').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('points', '0004_alter_pointrule_points'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
