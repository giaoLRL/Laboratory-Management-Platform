from django.contrib.auth.models import User
from django.db import models


class Competition(models.Model):
    """比赛：报名时间 / 正式时间 / 流程节点（JSON）/ 归档。"""

    id = models.CharField('比赛编号', max_length=32, primary_key=True)
    name = models.CharField('比赛名称', max_length=256)
    organizer = models.CharField('主办方', max_length=256, blank=True, default='')
    level = models.CharField('级别', max_length=32, blank=True, default='')  # 校级/省级/国家级...
    category = models.CharField('类别', max_length=64, blank=True, default='')
    registration_start = models.DateTimeField('报名开始')
    registration_end = models.DateTimeField('报名截止')
    start = models.DateTimeField('比赛开始')
    end = models.DateTimeField('比赛结束')
    location = models.CharField('地点', max_length=256, blank=True, default='')
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='competitions_owned')
    team_size = models.CharField('队伍规模', max_length=64, blank=True, default='')
    link = models.CharField('官方链接', max_length=512, blank=True, default='')
    summary = models.CharField('简介', max_length=1024, blank=True, default='')
    requirements = models.TextField('参赛须知', blank=True, default='')
    stages = models.JSONField('流程节点', default=list)  # [{title, at, description}]
    archived = models.BooleanField('已归档', default=False)
    created = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        ordering = ['-created']
