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
    # 旧字段：原「显示缩放」= transform: scale，在 cover 下放大只会裁得更狠。
    # 保留仅供旧接口 /homepage/scale 兼容，后台已改用 zoom，迁移时映射 zoom=max(100, scale)。
    scale = models.PositiveSmallIntegerField('显示缩放', default=100)
    fit = models.CharField('裁切方式', max_length=8, default='cover')  # cover 铺满 / contain 完整
    focus_x = models.PositiveSmallIntegerField('焦点 X', default=50)   # 0–100，object-position
    focus_y = models.PositiveSmallIntegerField('焦点 Y', default=50)
    zoom = models.PositiveSmallIntegerField('构图缩放', default=100)   # 100–150%，仅微调
    # 后台裁剪后保留的原图：用于「重新裁剪」而不必再让管理员找原始文件
    source = models.FileField('原图', upload_to='homepage/source/%Y%m/', blank=True, null=True)
    updated = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['key']

    def __str__(self):
        return f'{self.label}({self.key})'


class HomePageWork(models.Model):
    """作品集条目：列表可增删/排序/隐藏，取代原先写死的 work-01~08 媒体位。

    image 为空时前台回退 seed 指向的静态图；seed 为空则官网不渲染该条（新加的作品
    在上传图片前不会出现在官网上）。
    """
    sort = models.PositiveSmallIntegerField('排序', default=0)
    title = models.CharField('作品名', max_length=128, blank=True, default='')
    tag = models.CharField('赛事标签', max_length=64, blank=True, default='')
    alt = models.CharField('图片 alt', max_length=256, blank=True, default='')
    seed = models.CharField('默认引用', max_length=256, blank=True, default='')
    image = models.ImageField('上传图片', upload_to='homepage/%Y%m/', blank=True, null=True)
    visible = models.BooleanField('官网显示', default=True)
    updated = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['sort', 'id']

    def __str__(self):
        return f'{self.title or "未命名"}#{self.pk}'