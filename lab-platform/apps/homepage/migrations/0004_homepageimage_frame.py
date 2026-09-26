"""媒体位构图参数：fit / focus_x / focus_y / zoom。

zoom 由旧的 scale 映射而来（zoom = max(100, scale)）：旧 scale 语义是 transform: scale，
80 这类「缩小」在 cover 下其实是被裁得更多，直接沿用会让已上传的位变小，故取下限 100。
"""
from django.db import migrations, models


def scale_to_zoom(apps, schema_editor):
    HomePageImage = apps.get_model('homepage', 'HomePageImage')
    for row in HomePageImage.objects.exclude(scale=100):
        zoom = max(100, int(row.scale or 100))
        if zoom != row.zoom:
            row.zoom = zoom
            row.save(update_fields=['zoom'])


class Migration(migrations.Migration):

    dependencies = [
        ('homepage', '0003_homepageimage_scale'),
    ]

    operations = [
        migrations.AddField(
            model_name='homepageimage',
            name='fit',
            field=models.CharField(default='cover', max_length=8, verbose_name='裁切方式'),
        ),
        migrations.AddField(
            model_name='homepageimage',
            name='focus_x',
            field=models.PositiveSmallIntegerField(default=50, verbose_name='焦点 X'),
        ),
        migrations.AddField(
            model_name='homepageimage',
            name='focus_y',
            field=models.PositiveSmallIntegerField(default=50, verbose_name='焦点 Y'),
        ),
        migrations.AddField(
            model_name='homepageimage',
            name='zoom',
            field=models.PositiveSmallIntegerField(default=100, verbose_name='构图缩放'),
        ),
        migrations.RunPython(scale_to_zoom, migrations.RunPython.noop),
    ]