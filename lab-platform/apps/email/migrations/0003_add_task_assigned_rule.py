"""邮件规则扩展：新增「任务指派」即时规则 + 默认模板。"""

from django.db import migrations, models

KEY = 'task_assigned'


def apply(apps, schema_editor):
    EmailRule = apps.get_model('email', 'EmailRule')
    EmailRule.objects.get_or_create(key=KEY, defaults={
        'label': '任务指派',
        'hours_before': 0,
        'subject_tpl': '新任务指派：{title}',
        'body_tpl': '你好 {name}：\n\n你有一个新任务「{title}」（{id}）{due}\n\n—— 具身智能实验室',
    })


def rollback(apps, schema_editor):
    EmailRule = apps.get_model('email', 'EmailRule')
    EmailRule.objects.filter(key=KEY).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('email', '0002_extend_rules'),
    ]

    operations = [
        migrations.AlterField(
            model_name='EmailRule',
            name='key',
            field=models.CharField(choices=[
                ('task_due', '任务临近截止'), ('task_assigned', '任务指派'),
                ('loan_overdue', '借用已逾期'),
                ('competition_deadline', '比赛报名截止'), ('competition_start', '比赛开赛提醒'),
                ('leave_result', '请假审批结果'), ('loan_reviewed', '借用审批结果'),
                ('loan_issued', '借用发放'), ('asset_repaired', '维修完成'),
                ('custom', '自定义')], max_length=32, unique=True, verbose_name='规则'),
        ),
        migrations.RunPython(apply, rollback),
    ]
