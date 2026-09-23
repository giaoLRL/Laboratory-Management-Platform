from django.contrib.auth.models import User
from django.db import models


class MemberProfile(models.Model):
    """成员档案：1:1 扩展 Django 用户，承载实验室业务字段。"""

    ROLE_TEACHER = 'teacher'
    ROLE_MANAGER = 'manager'
    ROLE_MEMBER = 'member'
    ROLE_CHOICES = [(ROLE_TEACHER, '指导老师'), (ROLE_MANAGER, '负责人'), (ROLE_MEMBER, '普通成员')]

    STATUS_FREE = '空闲'
    STATUS_BUSY = '忙碌'
    STATUS_OFFLINE = '模拟离线'
    BASE_STATUS_CHOICES = [(STATUS_FREE, STATUS_FREE), (STATUS_BUSY, STATUS_BUSY), (STATUS_OFFLINE, STATUS_OFFLINE)]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='member_profile')
    name = models.CharField('姓名', max_length=64)
    number = models.CharField('学号/工号', max_length=32, unique=True)
    role = models.CharField('角色', max_length=16, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    group = models.CharField('所属小组', max_length=64, blank=True, default='')
    direction = models.CharField('技术方向', max_length=128, blank=True, default='')
    contact = models.CharField('联系方式', max_length=128, blank=True, default='')
    active = models.BooleanField('在籍', default=True)
    base_status = models.CharField('工作状态', max_length=16, choices=BASE_STATUS_CHOICES, default=STATUS_FREE)
    note = models.CharField('备注', max_length=256, blank=True, default='')
    joined = models.DateTimeField('加入时间', auto_now_add=True)
    updated = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['number']

    def __str__(self):
        return f'{self.name}({self.number})'


class OperationLog(models.Model):
    """操作日志：由后端在写操作时生成，不信任客户端自报。"""

    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='logs_as_actor')
    member = models.ForeignKey(MemberProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs_about')
    text = models.CharField('内容', max_length=256)
    at = models.DateTimeField('时间', auto_now_add=True)
    private = models.BooleanField('仅管理可见', default=False)

    class Meta:
        ordering = ['-at']

    def __str__(self):
        return self.text
