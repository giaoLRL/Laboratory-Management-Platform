from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel
from users.models import User

from ..validators import validate_file_size


class CheckInRecord(NetBoxModel):
    """实验室拍照定位打卡记录"""
    user = models.ForeignKey(
        to=User,
        on_delete=models.CASCADE,
        related_name='lab_checkins',
        verbose_name=_('打卡人'),
        db_index=True,
        help_text=_('打卡的实验室成员'),
    )
    photo = models.ImageField(
        verbose_name=_('打卡照片'),
        upload_to='checkins/photos/',
        validators=[validate_file_size],
        help_text=_('打卡现场照片，最大 10MB'),
    )
    latitude = models.DecimalField(
        verbose_name=_('纬度'),
        max_digits=10,
        decimal_places=7,
        help_text=_('GPS 纬度坐标'),
    )
    longitude = models.DecimalField(
        verbose_name=_('经度'),
        max_digits=10,
        decimal_places=7,
        help_text=_('GPS 经度坐标'),
    )
    accuracy = models.DecimalField(
        verbose_name=_('定位精度（米）'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('GPS 定位精度，单位米'),
    )
    address = models.CharField(
        verbose_name=_('地址备注'),
        max_length=255,
        blank=True,
        help_text=_('可填写实验室、楼宇、房间号或现场说明'),
    )
    note = models.TextField(
        verbose_name=_('备注'),
        blank=True,
        help_text=_('打卡备注信息'),
    )

    class Meta(NetBoxModel.Meta):
        verbose_name = _('打卡记录')
        verbose_name_plural = _('打卡记录')
        ordering = ('-created',)

    def __str__(self):
        return f'{self.user} - {self.created}'

    def get_absolute_url(self):
        return reverse('plugins:lab_manager:checkin_detail', args=[self.pk])
