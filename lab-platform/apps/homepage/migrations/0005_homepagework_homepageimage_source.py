"""作品集改数据驱动 + 媒体位保留原图。

1) HomePageImage.source：后台裁剪后的原图另存，供「重新裁剪」使用；
2) HomePageWork：作品集条目表，把原先写死的 8 个作品位（work-01~04 / demo-drone-nav /
   work-06~08）迁成 8 条种子数据，seed 仍指向原来的静态图，因此线上观感不变。
"""
from django.db import migrations, models

# 与 apps/homepage/defaults.py 的 WORK_DEFAULTS 一致（迁移内内联，避免依赖会变的常量）
WORKS = [
    ('机器视觉识别系统', '智能导航大赛', '/assets/img/work-01.webp?v=2'),
    ('无人机竞速训练场', '智能导航大赛', '/assets/img/work-02.webp?v=2'),
    ('视觉识别算法调试', '电赛', '/assets/img/work-03.webp?v=2'),
    ('机械臂搬运系统', '校内选拔', '/assets/img/work-04.webp?v=2'),
    ('工件视觉检测系统', '物联网竞赛', '/assets/img/demo-drone-nav.webp?v=2'),
    ('视觉云台平台', '智能导航大赛', '/assets/img/work-06.webp?v=2'),
    ('双机械臂系统', '校内选拔', '/assets/img/work-07.webp?v=2'),
    ('元件器材库', '日常备赛', '/assets/img/work-08.webp?v=2'),
]


# 作品集迁走后不再出现在 IMAGE_DEFAULTS 里的旧媒体位
ORPHAN_KEYS = ['work-01', 'work-02', 'work-03', 'work-04', 'demo-drone-nav', 'work-06', 'work-07', 'work-08']


def seed_works(apps, schema_editor):
    HomePageWork = apps.get_model('homepage', 'HomePageWork')
    if HomePageWork.objects.exists():
        return
    for i, (title, tag, seed) in enumerate(WORKS):
        HomePageWork.objects.create(sort=i, title=title, tag=tag, seed=seed, alt=title, visible=True)


def drop_orphan_slots(apps, schema_editor):
    """清掉旧媒体位遗留的空行（有上传文件的一律保留，避免误删管理员上传的素材）。"""
    HomePageImage = apps.get_model('homepage', 'HomePageImage')
    for row in HomePageImage.objects.filter(key__in=ORPHAN_KEYS):
        if not row.image and not row.video:
            row.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('homepage', '0004_homepageimage_frame'),
    ]

    operations = [
        migrations.AddField(
            model_name='homepageimage',
            name='source',
            field=models.FileField(blank=True, null=True, upload_to='homepage/source/%Y%m/', verbose_name='原图'),
        ),
        migrations.CreateModel(
            name='HomePageWork',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sort', models.PositiveSmallIntegerField(default=0, verbose_name='排序')),
                ('title', models.CharField(blank=True, default='', max_length=128, verbose_name='作品名')),
                ('tag', models.CharField(blank=True, default='', max_length=64, verbose_name='赛事标签')),
                ('alt', models.CharField(blank=True, default='', max_length=256, verbose_name='图片 alt')),
                ('seed', models.CharField(blank=True, default='', max_length=256, verbose_name='默认引用')),
                ('image', models.ImageField(blank=True, null=True, upload_to='homepage/%Y%m/', verbose_name='上传图片')),
                ('visible', models.BooleanField(default=True, verbose_name='官网显示')),
                ('updated', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={'ordering': ['sort', 'id']},
        ),
        migrations.RunPython(seed_works, migrations.RunPython.noop),
        migrations.RunPython(drop_orphan_slots, migrations.RunPython.noop),
    ]