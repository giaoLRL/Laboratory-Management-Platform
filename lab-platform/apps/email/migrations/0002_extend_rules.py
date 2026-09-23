"""邮件规则扩展：新增规则键 + 补充默认模板（借用审批/发放、维修完成、比赛开赛）。"""

from django.db import migrations, models

NEW_RULES = [
    ('competition_start', '比赛开赛提醒', 24,
     '比赛即将开赛：{title}',
     '你好 {name}：\n\n比赛「{title}」将于 {start} 在 {location} 开赛，请提前到场准备。\n\n—— 具身智能实验室'),
    ('loan_reviewed', '借用审批结果', 0, '', ''),
    ('loan_issued', '借用发放', 0, '', ''),
    ('asset_repaired', '维修完成', 0, '', ''),
]


def apply(apps, schema_editor):
    EmailRule = apps.get_model('email', 'EmailRule')
    for key, label, hours, subject, body in NEW_RULES:
        EmailRule.objects.get_or_create(key=key, defaults={
            'label': label, 'hours_before': hours, 'subject_tpl': subject, 'body_tpl': body,
        })


def rollback(apps, schema_editor):
    EmailRule = apps.get_model('email', 'EmailRule')
    EmailRule.objects.filter(key__in=[r[0] for r in NEW_RULES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('email', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='EmailRule',
            name='key',
            field=models.CharField(choices=[
                ('task_due', '任务临近截止'), ('loan_overdue', '借用已逾期'),
                ('competition_deadline', '比赛报名截止'), ('competition_start', '比赛开赛提醒'),
                ('leave_result', '请假审批结果'), ('loan_reviewed', '借用审批结果'),
                ('loan_issued', '借用发放'), ('asset_repaired', '维修完成'),
                ('custom', '自定义')], max_length=32, unique=True, verbose_name='规则'),
        ),
        migrations.RunPython(apply, rollback),
    ]
