"""种子化关卡积分规则：通关得分 + 首通加成（幂等，可重复执行）。"""

from django.db import migrations

LEVEL_RULES = [
    ('level_pass', '关卡通关（每星）', 10),
    ('level_first_bonus', '关卡首通加成', 50),
]


def seed_level_rules(apps, schema_editor):
    PointRule = apps.get_model('points', 'PointRule')
    for key, label, points in LEVEL_RULES:
        PointRule.objects.get_or_create(key=key, defaults={'label': label, 'points': points, 'enabled': True})


def unseed_level_rules(apps, schema_editor):
    PointRule = apps.get_model('points', 'PointRule')
    PointRule.objects.filter(key__in=[k for k, _, _ in LEVEL_RULES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('points', '0002_seed_default_rules'),
    ]

    operations = [
        migrations.RunPython(seed_level_rules, unseed_level_rules),
    ]