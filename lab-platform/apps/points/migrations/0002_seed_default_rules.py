"""种子化默认积分规则：任务评分/打卡/按时归还（幂等 get_or_create）。"""

from django.db import migrations

DEFAULT_RULES = [
    ('task_complete', '任务完成评分（每星）', 5),
    ('checkin_daily', '每日到实验室打卡', 2),
    ('checkin_streak', '连续打卡加成', 0),
    ('loan_on_time', '借用按时归还', 3),
    ('custom', '手动调整', 0),
]


def seed_rules(apps, schema_editor):
    PointRule = apps.get_model('points', 'PointRule')
    for key, label, points in DEFAULT_RULES:
        PointRule.objects.get_or_create(key=key, defaults={'label': label, 'points': points, 'enabled': True})


def unseed(apps, schema_editor):
    PointRule = apps.get_model('points', 'PointRule')
    PointRule.objects.filter(key__in=[k for k, _, _ in DEFAULT_RULES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('points', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_rules, unseed),
    ]