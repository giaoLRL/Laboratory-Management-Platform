"""关卡系统：技能线关卡 + 任务 + 通关记录 + 审核人。

与任务系统衔接：关卡任务保存于 Task 表（复用提交/审核/评分/通知），
LevelTask 仅做"任务→关卡"的归属映射；完成图/视频存于 completing media 字段。
"""

from django.conf import settings
from django.db import models


class Level(models.Model):
    """关卡：一条技能链（chain：51单片机/物联网/电赛/无人机…）下的一个关卡。"""

    STATUS_OPEN = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [(STATUS_OPEN, '开放'), (STATUS_CLOSED, '已关闭')]

    CHAINS = [('51单片机', '51单片机'), ('物联网', '物联网'), ('电赛', '电赛'), ('无人机', '无人机'), ('嵌入式', '嵌入式'), ('其他', '其他')]
    CHAPTERS = [('基础', '基础'), ('进阶', '进阶'), ('大师', '大师')]

    id = models.CharField('关卡编号', max_length=32, primary_key=True)
    title = models.CharField('关卡名称', max_length=128)
    chain = models.CharField('技能线', max_length=32, choices=CHAINS, default='其他')
    chapter = models.CharField('章节', max_length=16, choices=CHAPTERS, default='基础')
    order = models.PositiveIntegerField('排序', default=0)
    score_limit = models.PositiveIntegerField('满分', default=100)  # 每关分数后台可改
    stars_rule = models.CharField('星级规则', max_length=256, blank=True, default='')  # 如：60≥1★ 80≥2★ 95≥3★
    require_pass = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='next_levels', verbose_name='前置关卡')
    pos_x = models.FloatField('画布 X', default=0)
    pos_y = models.FloatField('画布 Y', default=0)
    description = models.TextField('关卡说明', blank=True, default='')
    cover = models.ImageField('封面/徽章图', upload_to='levels/%Y%m/', blank=True, null=True)
    activity = models.BooleanField('冲刺活动（通关 EXP/积分 ×2）', default=False)
    status = models.CharField('状态', max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='levels_created')
    created = models.DateTimeField('创建时间', auto_now_add=True)
    updated = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['chain', 'chapter', 'order']

    def __str__(self):
        return f'{self.chain} · {self.title}'


class LevelTask(models.Model):
    """关卡任务归属：任务保存于 tasksapp.Task，此表仅关联关卡与任务。"""

    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name='tasks_link')
    task = models.ForeignKey('tasksapp.Task', on_delete=models.CASCADE, related_name='level_links')
    kind = models.CharField('类型', max_length=16, default='main', choices=[('main', '主线'), ('bonus', '加分')])
    created = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        unique_together = ('level', 'task')
        ordering = ['created']


class PassRecord(models.Model):
    """通关/提交记录：每人每关一条，保存最优成绩、评审与完成图/视频。"""

    STATUS_PENDING = 'pending'
    STATUS_PASSED = 'passed'
    STATUS_REJECTED = 'rejected'
    STATUS_DONE = 'done'
    STATUS_CHOICES = [(STATUS_PENDING, '待审核'), (STATUS_PASSED, '已通过'), (STATUS_REJECTED, '未通过'), (STATUS_DONE, '已通关')]

    id = models.CharField('记录编号', max_length=32, primary_key=True)
    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name='pass_records')
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='level_passes')
    status = models.CharField('状态', max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    score = models.PositiveIntegerField('得分', default=0)
    stars = models.PositiveSmallIntegerField('星级', default=0)
    featured = models.BooleanField('精选', default=False)
    first_pass = models.BooleanField('首通', default=False)
    best_score = models.PositiveIntegerField('最高分', default=0)
    best_at = models.DateTimeField('最佳时间', null=True, blank=True)
    media = models.JSONField('完成图/视频', default=list, blank=True)  # [{url,name}]
    note = models.CharField('备注', max_length=512, blank=True, default='')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='level_reviews')
    opinion = models.TextField('审核意见', blank=True, default='')
    submitted_at = models.DateTimeField('提交时间', auto_now_add=True)
    reviewed_at = models.DateTimeField('审核时间', null=True, blank=True)
    updated = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        unique_together = ('level', 'member')
        ordering = ['-best_score']

    def __str__(self):
        return f'{self.member_id} @ {self.level_id} {self.status}'


class LevelReviewer(models.Model):
    """关卡审核人：可增删，便于交接。"""

    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name='reviewers')
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='level_reviewer_roles')
    active = models.BooleanField('在职', default=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='reviewer_added')
    created = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        unique_together = ('level', 'member')
        ordering = ['created']