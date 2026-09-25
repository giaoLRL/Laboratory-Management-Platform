from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from apps.accounts.models import MemberProfile
from apps.common.ids import next_code


class Announcement(models.Model):
    """公告：发布人、内容、置顶、接收范围（全员/小组/指定成员）。"""

    SCOPE_ALL = 'all'
    SCOPE_GROUP = 'group'
    SCOPE_MEMBERS = 'members'
    SCOPE_CHOICES = [(SCOPE_ALL, '全体成员'), (SCOPE_GROUP, '指定小组'), (SCOPE_MEMBERS, '指定成员')]

    id = models.CharField('编号', max_length=32, primary_key=True)
    title = models.CharField('标题', max_length=128)
    content = models.TextField('内容', default='')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='announcements')
    pinned = models.BooleanField('置顶', default=False)
    scope = models.CharField('范围', max_length=16, choices=SCOPE_CHOICES, default=SCOPE_ALL)
    group = models.ForeignKey('accounts.LabGroup', on_delete=models.CASCADE, null=True, blank=True, related_name='announcements')
    member_ids = models.JSONField('指定成员', default=list, blank=True)
    active = models.BooleanField('有效', default=True)
    created = models.DateTimeField('发布时间', auto_now_add=True)
    updated = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['-pinned', '-created']

    def __str__(self):
        return f'{self.title}({self.id})'

    @classmethod
    def next_id(cls):
        from apps.common.ids import next_code
        return next_code(cls, 'AN')


class AnnouncementRead(models.Model):
    """公告已读记录：用于未读角标。"""

    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name='reads')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='announcement_reads')
    read_at = models.DateTimeField('阅读时间', auto_now_add=True)

    class Meta:
        unique_together = ('announcement', 'user')


def visible_announcements(profile, staff=False):
    """当前用户可见的公告（含范围过滤），置顶优先、新的在前。

    SQLite 不支持 JSONField 的 contains 查找（member_ids 过滤），
    为便于本地开发与测试，全部走内存过滤（公告数量级小，无性能顾虑）。
    """
    now = timezone.now()
    qs = list(Announcement.objects.prefetch_related('group__members').filter(active=True))
    result = []
    for a in qs:
        if a.scope == Announcement.SCOPE_ALL:
            result.append(a)
        elif a.scope == Announcement.SCOPE_GROUP and a.group and profile in a.group.members.all():
            result.append(a)
        elif a.scope == Announcement.SCOPE_MEMBERS and profile.user_id in (a.member_ids or []):
            result.append(a)
    return result


class NewsItem(models.Model):
    """实时动态：聚合 AI/具身智能领域资讯，来源可自动抓取或手动录入。"""

    FETCH_MANUAL = 'manual'
    FETCH_RSS = 'rss'
    FETCH_LLM = 'llm'
    FETCH_CHOICES = [(FETCH_MANUAL, '手动录入'), (FETCH_RSS, 'RSS 抓取'), (FETCH_LLM, 'LLM 摘要')]

    id = models.CharField('编号', max_length=32, primary_key=True)
    title = models.CharField('标题', max_length=256)
    source = models.CharField('来源', max_length=128, blank=True, default='')
    url = models.URLField('原文链接', max_length=512, blank=True, default='')
    summary = models.TextField('摘要', blank=True, default='')
    published_at = models.DateTimeField('发布时间')
    fetch_source = models.CharField('采集来源', max_length=16, choices=FETCH_CHOICES, default=FETCH_MANUAL)
    created = models.DateTimeField('入库时间', auto_now_add=True)

    class Meta:
        ordering = ['-published_at']

    def __str__(self):
        return self.title

    @classmethod
    def next_id(cls):
        return next_code(cls, 'NEWS')


class Notification(models.Model):
    """站内通知：按接收者生成，幂等去重（recipient+kind+ref 唯一）。"""

    KIND_CHOICES = [
        ('loan_apply', '借用申请'),
        ('loan_reviewed', '借用审批结果'),
        ('loan_issued', '借用发放'),
        ('loan_return_requested', '归还申请'),
        ('loan_returned', '归还验收'),
        ('loan_overdue', '借用逾期'),
        ('leave_apply', '请假申请'),
        ('leave_reviewed', '请假审批结果'),
        ('task_assigned', '任务指派'),
        ('task_completed', '任务完成'),
        ('task_scored', '任务评分'),
        ('task_due', '任务到期'),
        ('task_submitted', '任务待审核'),
        ('task_reviewed', '任务审核通过'),
        ('task_rejected', '任务被退回'),
        ('competition_published', '新比赛发布'),
        ('competition_deadline', '报名截止'),
        ('competition_start', '开赛提醒'),
        ('announcement_published', '新公告'),
        ('asset_repaired', '维修完成'),
        ('points_changed', '积分变动'),
        ('member_joined', '成员加入'),
    ]
    KIND_GROUP = {
        'loan': '借用', 'leave': '请假', 'task': '任务', 'competition': '比赛',
        'announcement': '公告', 'asset': '资产', 'points': '积分', 'member': '成员',
    }

    id = models.CharField('编号', max_length=32, primary_key=True)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField('类型', max_length=32, choices=KIND_CHOICES)
    title = models.CharField('标题', max_length=128)
    body = models.TextField('正文', blank=True, default='')
    ref_type = models.CharField('引用类型', max_length=32, blank=True, default='')
    ref_id = models.CharField('引用编号', max_length=64, blank=True, default='')
    link = models.CharField('前端路由', max_length=64, blank=True, default='')
    read = models.BooleanField('已读', default=False)
    read_at = models.DateTimeField('已读时间', null=True, blank=True)
    created = models.DateTimeField('时间', auto_now_add=True)

    class Meta:
        ordering = ['-created']
        constraints = [
            models.UniqueConstraint(fields=['recipient', 'kind', 'ref_type', 'ref_id'],
                                    name='uniq_notification_ref'),
        ]

    def __str__(self):
        return f'{self.recipient_id} {self.kind} {self.title}'

    @classmethod
    def next_id(cls):
        return next_code(cls, 'NF')