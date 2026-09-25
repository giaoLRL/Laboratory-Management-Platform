from django.contrib.auth.models import User
from django.db import models


class Leave(models.Model):
    """请假：提交 → 审批（通过/拒绝）/ 撤销 → 到岗销假。"""

    STATUS_PENDING = '待审批'
    STATUS_APPROVED = '已批准'
    STATUS_REJECTED = '已拒绝'
    STATUS_CANCELLED = '已撤销'
    STATUS_REVERTED = '已销假'
    STATUS_CHOICES = [(STATUS_PENDING, STATUS_PENDING), (STATUS_APPROVED, STATUS_APPROVED),
                      (STATUS_REJECTED, STATUS_REJECTED), (STATUS_CANCELLED, STATUS_CANCELLED),
                      (STATUS_REVERTED, STATUS_REVERTED)]

    id = models.CharField('请假单号', max_length=32, primary_key=True)
    member = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leaves')
    start = models.DateTimeField('开始时间')
    end = models.DateTimeField('结束时间')
    reason = models.CharField('原因', max_length=512, blank=True, default='')
    status = models.CharField('状态', max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created = models.DateTimeField('提交时间', auto_now_add=True)
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='leaves_reviewed')
    reviewed = models.DateTimeField(null=True, blank=True)
    opinion = models.CharField('审批意见', max_length=256, blank=True, default='')
    updated = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['-created']
