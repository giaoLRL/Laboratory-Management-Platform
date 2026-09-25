from django.contrib.auth.models import User
from django.db import models


class CheckInRecord(models.Model):
    """到场打卡：照片 + GPS 定位，每成员每天限一条。

    `signout_at IS NULL` 表示仍在席 —— 座位图上的小人据此显示，
    签退后置为当前时间，小人即消失（同一天不可再打卡）。
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='checkins')
    photo = models.ImageField('打卡照片', upload_to='checkins/%Y%m/')
    latitude = models.FloatField('纬度')
    longitude = models.FloatField('经度')
    signout_at = models.DateTimeField('签退时间', null=True, blank=True)
    created = models.DateTimeField('打卡时间', auto_now_add=True)
    updated = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['-created']
