"""营销官网首页可编辑内容模型。

两表分离：文案（纯文本，前台 textContent 替换）与图片（含默认引用 seed 与当前
alt）。image 字段为空时，前端回退到 seed 指向的 /assets 静态图。
"""
from django.db import models


class HomePageText(models.Model):
    key = models.CharField('标识', max_length=64, primary_key=True)
    label = models.CharField('后台表单标题', max_length=128, default='')
    value = models.TextField('文案', blank=True, default='')
    updated = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['key']

    def __str__(self):
        return f'{self.label}({self.key})'


class HomePageImage(models.Model):
    key = models.CharField('标识', max_length=64, primary_key=True)
    label = models.CharField('后台表单标题', max_length=128, default='')
    alt = models.CharField('图片 alt', max_length=256, blank=True, default='')
    seed = models.CharField('默认引用', max_length=256, default='')  # 如 /assets/img/work-01.webp?v=2
    kind = models.CharField('媒体类型', max_length=16, choices=[('image', 'image'), ('video', 'video')], default='image')
    image = models.ImageField('上传图片', upload_to='homepage/%Y%m/', blank=True, null=True)
    video = models.FileField('上传视频', upload_to='homepage/%Y%m/', blank=True, null=True)
    scale = models.PositiveSmallIntegerField('显示缩放', default=100)  # 80–150%
    updated = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['key']

    def __str__(self):
        return f'{self.label}({self.key})'