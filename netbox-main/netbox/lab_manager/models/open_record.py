from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel
from users.models import User


class MemberOpenRecord(NetBoxModel):
    """成员打开实验室平台页面的记录"""
    user = models.ForeignKey(
        to=User,
        on_delete=models.CASCADE,
        related_name='lab_open_records',
        verbose_name=_('成员'),
    )
    path = models.CharField(
        verbose_name=_('打开路径'),
        max_length=500,
    )
    page_title = models.CharField(
        verbose_name=_('页面名称'),
        max_length=100,
        blank=True,
    )
    target_type = models.CharField(
        verbose_name=_('对象类型'),
        max_length=50,
        blank=True,
    )
    target_id = models.PositiveBigIntegerField(
        verbose_name=_('对象ID'),
        null=True,
        blank=True,
    )
    user_agent = models.TextField(
        verbose_name=_('浏览器标识'),
        blank=True,
    )
    ip_address = models.GenericIPAddressField(
        verbose_name=_('IP地址'),
        null=True,
        blank=True,
    )

    class Meta(NetBoxModel.Meta):
        verbose_name = _('成员打开记录')
        verbose_name_plural = _('成员打开记录')
        ordering = ('-created',)

    def __str__(self):
        return f'{self.user} - {self.page_title or self.path}'

    def get_absolute_url(self):
        return reverse('plugins:lab_manager:member_open_records')
