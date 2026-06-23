from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('lab_manager', '0013_memberopenrecord'),
    ]

    operations = [
        migrations.AddField(
            model_name='memberopenrecord',
            name='photo',
            field=models.ImageField(blank=True, null=True, upload_to='checkins/photos/', verbose_name='打卡照片'),
        ),
        migrations.AddField(
            model_name='memberopenrecord',
            name='latitude',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True, verbose_name='纬度'),
        ),
        migrations.AddField(
            model_name='memberopenrecord',
            name='longitude',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True, verbose_name='经度'),
        ),
        migrations.AddField(
            model_name='memberopenrecord',
            name='accuracy',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='定位精度（米）'),
        ),
        migrations.AddField(
            model_name='memberopenrecord',
            name='address',
            field=models.CharField(blank=True, max_length=255, verbose_name='地址备注'),
        ),
        migrations.AddField(
            model_name='memberopenrecord',
            name='note',
            field=models.TextField(blank=True, verbose_name='备注'),
        ),
    ]
