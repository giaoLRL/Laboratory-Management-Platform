from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel
from users.models import User


class Notification(NetBoxModel):
    """站内通知"""
    user = models.ForeignKey(
        to=User,
        on_delete=models.CASCADE,
        related_name='lab_notifications',
        verbose_name=_('接收人'),
        db_index=True,
        help_text=_('接收通知的用户'),
    )
    title = models.CharField(
        verbose_name=_('标题'),
        max_length=200,
        help_text=_('通知标题'),
    )
    message = models.TextField(
        verbose_name=_('内容'),
        blank=True,
        help_text=_('通知正文'),
    )
    is_read = models.BooleanField(
        verbose_name=_('已读'),
        default=False,
        db_index=True,
        help_text=_('用户是否已阅读此通知'),
    )
    link = models.CharField(
        verbose_name=_('跳转链接'),
        max_length=500,
        blank=True,
        help_text=_('点击通知跳转的目标 URL'),
    )
    notification_type = models.CharField(
        verbose_name=_('通知类型'),
        max_length=30,
        blank=True,
        default='info',
        help_text=_('通知分类：task/borrow/approval/system'),
    )

    class Meta(NetBoxModel.Meta):
        verbose_name = _('通知')
        verbose_name_plural = _('通知')
        ordering = ('-created',)

    def __str__(self):
        return f'{self.user} — {self.title}'

    def get_absolute_url(self):
        return self.link or '#'


def send_notification(user, title, message='', link='', notification_type='info'):
    """发送站内通知的辅助函数。"""
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        link=link,
        notification_type=notification_type,
    )
