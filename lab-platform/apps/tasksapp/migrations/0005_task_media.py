"""Task 增加 media（任务图片/示例图 JSON）。"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasksapp', '0004_task_reviewer_alter_task_reviewed_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='media',
            field=models.JSONField(blank=True, default=list, verbose_name='任务图片/示例视频'),
        ),
    ]