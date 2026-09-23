from django.contrib.auth.models import User
from django.db import models


class Task(models.Model):
    """任务：看板列 status（todo/doing/submitted/done）。"""

    STATUS_TODO = 'todo'
    STATUS_DOING = 'doing'
    STATUS_SUBMITTED = 'submitted'
    STATUS_DONE = 'done'
    STATUS_CHOICES = [(STATUS_TODO, '待办'), (STATUS_DOING, '进行中'), (STATUS_SUBMITTED, '待审核'), (STATUS_DONE, '已完成')]
    PRIORITY_CHOICES = [('low', '低'), ('normal', '普通'), ('high', '高'), ('urgent', '紧急')]

    id = models.CharField('任务编号', max_length=32, primary_key=True)
    title = models.CharField('标题', max_length=256)
    description = models.TextField('描述', blank=True, default='')
    status = models.CharField('看板列', max_length=16, choices=STATUS_CHOICES, default=STATUS_TODO)
    priority = models.CharField('优先级', max_length=16, choices=PRIORITY_CHOICES, default='normal')
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks_created')
    group = models.ForeignKey('accounts.LabGroup', on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks', verbose_name='小组任务')
    due = models.DateTimeField('截止时间', null=True, blank=True)
    completion_note = models.TextField('完成总结', blank=True, default='')
    completed_at = models.DateTimeField('完成时间', null=True, blank=True)
    score = models.PositiveSmallIntegerField('评分', null=True, blank=True)
    submission = models.TextField('提交内容', blank=True, default='')
    submitted_at = models.DateTimeField('提交时间', null=True, blank=True)
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks_as_reviewer', verbose_name='指定审核人')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks_reviewed', verbose_name='实际审核人')
    reviewed_at = models.DateTimeField('审核时间', null=True, blank=True)
    review_opinion = models.TextField('审核意见', blank=True, default='')
    created = models.DateTimeField('创建时间', auto_now_add=True)
    updated = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['due', 'id']


class TaskAttachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField('附件', upload_to='tasks/%Y%m/')
    name = models.CharField('文件名', max_length=256, blank=True, default='')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
