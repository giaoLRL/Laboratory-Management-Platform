from django.contrib.auth.models import User
from django.db import models


class PointRule(models.Model):
    """积分规则：每个规则的单位分值与会启用状态。"""

    key = models.CharField('规则键', max_length=32, unique=True)
    label = models.CharField('规则名称', max_length=64)
    points = models.IntegerField('单位分值', default=0)
    enabled = models.BooleanField('启用', default=True)
    builtin = models.BooleanField('内置', default=True)

    class Meta:
        ordering = ['key']

    def __str__(self):
        return f'{self.label}({self.key})'


class PointRecord(models.Model):
    """积分流水：单向只增，同一 (user, rule_key, ref) 只发一次。"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='point_records')
    rule_key = models.CharField('规则', max_length=32)
    points = models.IntegerField('分值', default=0)
    ref_type = models.CharField('关联类型', max_length=32, blank=True, default='')
    ref_id = models.CharField('关联编号', max_length=64, blank=True, default='')
    reason = models.CharField('说明', max_length=256, blank=True, default='')
    created = models.DateTimeField('时间', auto_now_add=True)

    class Meta:
        ordering = ['-created']
        constraints = [
            models.UniqueConstraint(fields=['user', 'rule_key', 'ref_type', 'ref_id'], name='uniq_point_award'),
        ]

    def __str__(self):
        return f'{self.user_id} +{self.points} ({self.rule_key})'