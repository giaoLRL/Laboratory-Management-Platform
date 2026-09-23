from django.contrib.auth.models import User
from django.db import models


class CheckInRecord(models.Model):
    """到场打卡：照片 + GPS 定位，每成员每天限一条。"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='checkins')
    photo = models.ImageField('打卡照片', upload_to='checkins/%Y%m/')
    latitude = models.FloatField('纬度')
    longitude = models.FloatField('经度')
    created = models.DateTimeField('打卡时间', auto_now_add=True)

    class Meta:
        ordering = ['-created']
