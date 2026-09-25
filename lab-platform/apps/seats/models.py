from django.contrib.auth.models import User
from django.db import models


class SeatLayout(models.Model):
    """实验室俯视图布局（可编辑）。

    grid 是「行字符串数组」，每个字符是一个格子：
      .  通道空地   w  工位   s  储物柜   t  测试台   d  门口   #  墙体
    labels / owners 以「行-列」为键（如 "3-2"），编辑地图时不必重算主键。
    """

    id = models.CharField('布局编号', max_length=32, primary_key=True)
    name = models.CharField('名称', max_length=64, default='实验室平面')
    rows = models.IntegerField('行数', default=0)
    cols = models.IntegerField('列数', default=0)
    grid = models.JSONField('格子矩阵', default=list, blank=True)
    labels = models.JSONField('座位编号', default=dict, blank=True)
    owners = models.JSONField('默认归属', default=dict, blank=True)
    active = models.BooleanField('启用', default=True)
    created = models.DateTimeField('创建时间', auto_now_add=True)
    updated = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['-updated']


class SeatPresence(models.Model):
    """在席位置：小人 = 今日打卡且未签退，所在格随挪动更新。

    没有记录时按「默认归属 → 空工位」自动分配，因此签退后删除本条即可。
    """

    member = models.OneToOneField(User, on_delete=models.CASCADE, related_name='seat_presence')
    layout = models.ForeignKey(SeatLayout, on_delete=models.CASCADE, related_name='presences')
    row = models.IntegerField('行')
    col = models.IntegerField('列')
    updated = models.DateTimeField('更新时间', auto_now=True)


class SeatStatus(models.Model):
    """在席状态 + 文字，全员可见，持续到签退或下次修改。"""

    STATUS_CHOICES = [('work', '在工位'), ('debug', '调试中'), ('meeting', '开会'),
                      ('rest', '休息'), ('out', '实验室外'), ('custom', '自定义')]

    member = models.OneToOneField(User, on_delete=models.CASCADE, related_name='seat_status')
    status_key = models.CharField('状态', max_length=16, choices=STATUS_CHOICES, default='work')
    text = models.CharField('状态文字', max_length=30, blank=True, default='')
    updated = models.DateTimeField('更新时间', auto_now=True)


class SeatMessage(models.Model):
    """座位气泡：短消息，到期即不再下发（服务端按 expires_at 过滤）。"""

    id = models.CharField('气泡编号', max_length=32, primary_key=True)
    layout = models.ForeignKey(SeatLayout, on_delete=models.CASCADE, related_name='bubbles')
    member = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seat_bubbles')
    text = models.CharField('内容', max_length=50)
    created = models.DateTimeField('发送时间', auto_now_add=True)
    expires_at = models.DateTimeField('过期时间')
    updated = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['-created']


class MemberCharacter(models.Model):
    """参数化形象：只存白名单部件键值，前端拼 SVG，不接收任意 SVG（防存储型 XSS）。"""

    member = models.OneToOneField(User, on_delete=models.CASCADE, related_name='seat_character')
    parts = models.JSONField('部件', default=dict, blank=True)
    updated = models.DateTimeField('更新时间', auto_now=True)


class SeatChat(models.Model):
    """实验室大厅（公共频道）。

    故意不进 workspace 快照：聊天记录无限增长，进快照会把每次
    GET /api/workspace 越撑越大。改走 /seats/chat 独立分页接口。
    """

    id = models.CharField('消息编号', max_length=32, primary_key=True)
    member = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seat_chats')
    text = models.CharField('内容', max_length=200)
    active = models.BooleanField('有效', default=True)
    created = models.DateTimeField('发送时间', auto_now_add=True)

    class Meta:
        ordering = ['-created']
        indexes = [models.Index(fields=['-created'])]


class SeatChatCursor(models.Model):
    """大厅已读游标：未读数 = 游标之后的消息条数（不做逐条已读）。"""

    member = models.OneToOneField(User, on_delete=models.CASCADE, related_name='seat_chat_cursor')
    last_read_at = models.DateTimeField('上次已读时间')