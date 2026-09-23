from django.contrib.auth.models import User
from django.db import models


class Asset(models.Model):
    """模块（一物一码）：id 即资产编号（EM-001），创建后不可修改。"""

    STATUS_FREE = '空闲'
    STATUS_IN_USE = '使用中'
    STATUS_REPAIR = '维修中'
    STATUS_RETIRED = '报废'
    STATUS_CHOICES = [(STATUS_FREE, STATUS_FREE), (STATUS_IN_USE, STATUS_IN_USE),
                      (STATUS_REPAIR, STATUS_REPAIR), (STATUS_RETIRED, STATUS_RETIRED)]

    id = models.CharField('资产编号', max_length=32, primary_key=True)
    name = models.CharField('名称', max_length=128)
    model = models.CharField('型号', max_length=128, blank=True, default='')
    category = models.CharField('类别', max_length=64, blank=True, default='')
    vendor = models.CharField('供应商', max_length=128, blank=True, default='')
    spec = models.CharField('规格', max_length=256, blank=True, default='')
    location = models.CharField('位置', max_length=128, blank=True, default='')
    status = models.CharField('状态', max_length=16, choices=STATUS_CHOICES, default=STATUS_FREE)
    note = models.CharField('备注', max_length=512, blank=True, default='')
    datasheet = models.CharField('资料链接', max_length=512, blank=True, default='')
    created = models.DateTimeField('创建时间', auto_now_add=True)
    updated = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.id} {self.name}'


class Loan(models.Model):
    """借用单：申请 → 审批 → 发放 → 归还申请 → 验收。"""

    STATUS_PENDING = '待审批'
    STATUS_APPROVED = '已批准'
    STATUS_REJECTED = '已拒绝'
    STATUS_CANCELLED = '已取消'
    STATUS_IN_USE = '使用中'
    STATUS_RETURNING = '归还申请中'
    STATUS_DONE = '已完成'
    STATUS_CHOICES = [(STATUS_PENDING, STATUS_PENDING), (STATUS_APPROVED, STATUS_APPROVED),
                      (STATUS_REJECTED, STATUS_REJECTED), (STATUS_CANCELLED, STATUS_CANCELLED),
                      (STATUS_IN_USE, STATUS_IN_USE), (STATUS_RETURNING, STATUS_RETURNING),
                      (STATUS_DONE, STATUS_DONE)]

    id = models.CharField('借用单号', max_length=32, primary_key=True)
    member = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loans')
    purpose = models.CharField('用途', max_length=256, blank=True, default='')
    project = models.CharField('关联项目', max_length=128, blank=True, default='')
    status = models.CharField('状态', max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created = models.DateTimeField('申请时间', auto_now_add=True)
    due = models.DateTimeField('预计归还')
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='loans_reviewed')
    reviewed = models.DateTimeField(null=True, blank=True)
    opinion = models.CharField('审批意见', max_length=256, blank=True, default='')
    issued = models.DateTimeField(null=True, blank=True)
    issuer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='loans_issued')
    return_requested = models.DateTimeField(null=True, blank=True)
    received = models.DateTimeField(null=True, blank=True)
    receiver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='loans_received')
    note = models.CharField('验收备注', max_length=512, blank=True, default='')

    class Meta:
        ordering = ['-created']


class LoanItem(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='items')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='loan_items')


class Maintenance(models.Model):
    id = models.CharField('维修单号', max_length=32, primary_key=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='maintenance_records')
    description = models.CharField('问题描述', max_length=512)
    status = models.CharField('状态', max_length=16, default='维修中')
    created = models.DateTimeField('登记时间', auto_now_add=True)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-created']
