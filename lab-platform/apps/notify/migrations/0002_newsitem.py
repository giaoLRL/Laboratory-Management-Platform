from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notify', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='NewsItem',
            fields=[
                ('id', models.CharField(max_length=32, primary_key=True, serialize=False, verbose_name='编号')),
                ('title', models.CharField(max_length=256, verbose_name='标题')),
                ('source', models.CharField(blank=True, default='', max_length=128, verbose_name='来源')),
                ('url', models.URLField(blank=True, default='', max_length=512, verbose_name='原文链接')),
                ('summary', models.TextField(blank=True, default='', verbose_name='摘要')),
                ('published_at', models.DateTimeField(verbose_name='发布时间')),
                ('fetch_source', models.CharField(choices=[('manual', '手动录入'), ('rss', 'RSS 抓取'), ('llm', 'LLM 摘要')], default='manual', max_length=16, verbose_name='采集来源')),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='入库时间')),
            ],
            options={'ordering': ['-published_at']},
        ),
    ]