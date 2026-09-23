import django.db.models.deletion
from django.db import migrations, models

DEFAULT_RULES = [
    ('task_due', '任务临近截止', 24,
     '任务临近截止提醒：{title}',
     '你好 {name}：\n\n任务 {id}「{title}」将于 {due} 截止，请及时推进。\n\n—— 具身智能实验室'),
    ('loan_overdue', '借用已逾期', 0,
     '借用逾期提醒：{id}',
     '你好 {name}：\n\n借用单 {id} 已超过预计归还时间（{due}），请尽快归还并处理。\n\n—— 具身智能实验室'),
    ('competition_deadline', '比赛报名截止', 72,
     '比赛报名即将截止：{title}',
     '你好 {name}：\n\n比赛「{title}」报名将于 {due} 截止，请尽快完成组队报名。\n\n—— 具身智能实验室'),
    ('leave_result', '请假审批结果', 0, '', ''),
    ('custom', '自定义', 0, '', ''),
]


def seed_rules(apps, schema_editor):
    EmailRule = apps.get_model('email', 'EmailRule')
    for key, label, hours, subject, body in DEFAULT_RULES:
        EmailRule.objects.get_or_create(key=key, defaults={
            'label': label, 'hours_before': hours, 'subject_tpl': subject, 'body_tpl': body,
        })


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='EmailConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('smtp_host', models.CharField(blank=True, default='', max_length=128, verbose_name='SMTP 服务器')),
                ('smtp_port', models.PositiveIntegerField(default=465, verbose_name='端口')),
                ('smtp_user', models.CharField(blank=True, default='', max_length=128, verbose_name='账号')),
                ('smtp_password_enc', models.CharField(blank=True, default='', max_length=512, verbose_name='密码(加密)')),
                ('from_addr', models.EmailField(blank=True, default='', max_length=128, verbose_name='发件人')),
                ('use_ssl', models.BooleanField(default=True, verbose_name='SSL')),
                ('enabled', models.BooleanField(default=False, verbose_name='启用')),
                ('updated', models.DateTimeField(auto_now=True)),
            ],
            options={'verbose_name': '邮件配置'},
        ),
        migrations.CreateModel(
            name='EmailLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rule_key', models.CharField(max_length=32, verbose_name='规则')),
                ('recipient', models.EmailField(max_length=128, verbose_name='收件人')),
                ('obj_type', models.CharField(blank=True, default='', max_length=32, verbose_name='对象类型')),
                ('obj_id', models.CharField(blank=True, default='', max_length=64, verbose_name='对象编号')),
                ('subject', models.CharField(blank=True, default='', max_length=256, verbose_name='主题')),
                ('day', models.DateField(auto_now_add=True, verbose_name='发送日')),
                ('ok', models.BooleanField(default=True, verbose_name='成功')),
                ('error', models.CharField(blank=True, default='', max_length=256, verbose_name='错误')),
                ('sent_at', models.DateTimeField(auto_now_add=True, verbose_name='发送时间')),
            ],
            options={'ordering': ['-sent_at']},
        ),
        migrations.CreateModel(
            name='EmailRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(choices=[('task_due', '任务临近截止'), ('loan_overdue', '借用已逾期'), ('competition_deadline', '比赛报名截止'), ('leave_result', '请假审批结果'), ('custom', '自定义')], max_length=32, unique=True, verbose_name='规则')),
                ('label', models.CharField(max_length=64, verbose_name='名称')),
                ('enabled', models.BooleanField(default=True, verbose_name='启用')),
                ('hours_before', models.PositiveIntegerField(default=24, verbose_name='提前小时数')),
                ('subject_tpl', models.CharField(blank=True, default='', max_length=256, verbose_name='标题模板')),
                ('body_tpl', models.TextField(blank=True, default='', verbose_name='正文模板')),
            ],
            options={'ordering': ['key']},
        ),
        migrations.AddConstraint(
            model_name='EmailLog',
            constraint=models.UniqueConstraint(fields=('rule_key', 'obj_type', 'obj_id', 'recipient', 'day'), name='uniq_email_day'),
        ),
        migrations.RunPython(seed_rules),
    ]