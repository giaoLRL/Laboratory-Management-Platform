"""新增 must_complete_profile：新账号首次登录需完善资料后清除。"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0015_grant_task_review'),
    ]

    operations = [
        migrations.AddField(
            model_name='memberprofile',
            name='must_complete_profile',
            field=models.BooleanField('首次登录需完善资料', default=False),
        ),
    ]
