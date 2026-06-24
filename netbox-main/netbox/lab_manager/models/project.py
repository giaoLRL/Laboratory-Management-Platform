from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel
from users.models import User


class ProjectStatusChoices(models.TextChoices):
    PLANNING = 'planning', _('规划中')
    ACTIVE = 'active', _('进行中')
    COMPLETED = 'completed', _('已完成')
    ARCHIVED = 'archived', _('已归档')


class LabProject(NetBoxModel):
    """实验室项目/实验"""
    name = models.CharField(
        verbose_name=_('项目名称'),
        max_length=200,
        help_text=_('实验室项目或实验的名称'),
    )
    description = models.TextField(
        verbose_name=_('项目描述'),
        blank=True,
        help_text=_('详细的项目说明、目标和注意事项'),
    )
    status = models.CharField(
        verbose_name=_('状态'),
        max_length=20,
        choices=ProjectStatusChoices.choices,
        default=ProjectStatusChoices.PLANNING,
        db_index=True,
        help_text=_('项目当前状态'),
    )
    leader = models.ForeignKey(
        to=User,
        on_delete=models.SET_NULL,
        related_name='led_projects',
        verbose_name=_('项目负责人'),
        null=True,
        blank=True,
        help_text=_('项目的负责人或指导老师'),
    )
    members = models.ManyToManyField(
        to=User,
        related_name='project_memberships',
        verbose_name=_('项目成员'),
        blank=True,
        help_text=_('参与该项目的实验室成员'),
    )
    start_date = models.DateField(
        verbose_name=_('开始日期'),
        null=True,
        blank=True,
        help_text=_('项目启动日期'),
    )
    end_date = models.DateField(
        verbose_name=_('截止日期'),
        null=True,
        blank=True,
        help_text=_('项目预期完成日期'),
    )

    class Meta(NetBoxModel.Meta):
        verbose_name = _('实验室项目')
        verbose_name_plural = _('实验室项目')
        ordering = ('-created',)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('plugins:lab_manager:labproject', args=[self.pk])

    @property
    def hardware_count(self):
        """通过借用记录关联到该项目的硬件数量（去重）。"""
        return self.hardware_set.count() if hasattr(self, 'hardware_set') else 0

    @property
    def task_count(self):
        """该项目下的任务数量。"""
        return self.tasks.count()
