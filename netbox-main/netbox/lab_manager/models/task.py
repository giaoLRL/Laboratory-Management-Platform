from django.db import models
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel
from users.models import User

from ..choices import TaskPriorityChoices, TaskStatusChoices
from ..validators import validate_file_size


class Task(NetBoxModel):
    """任务"""
    title = models.CharField(
        verbose_name=_('标题'),
        max_length=200,
        help_text=_('任务标题，简明扼要描述任务内容'),
    )
    description = models.TextField(
        verbose_name=_('任务描述'),
        help_text=_('详细的任务说明、要求和注意事项'),
    )
    priority = models.CharField(
        verbose_name=_('优先级'),
        max_length=10,
        choices=TaskPriorityChoices,
        default=TaskPriorityChoices.MEDIUM,
        db_index=True,
        help_text=_('任务优先级：低、中、高、紧急'),
    )
    status = models.CharField(
        verbose_name=_('状态'),
        max_length=20,
        choices=TaskStatusChoices,
        default=TaskStatusChoices.PENDING,
        db_index=True,
        help_text=_('任务当前状态：待开始、进行中、已完成'),
    )
    created_by = models.ForeignKey(
        to=User,
        on_delete=models.CASCADE,
        related_name='created_tasks',
        verbose_name=_('创建人'),
        db_index=True,
        help_text=_('创建此任务的管理员'),
    )
    assigned_to = models.ForeignKey(
        to=User,
        on_delete=models.CASCADE,
        related_name='assigned_tasks',
        verbose_name=_('执行人'),
        db_index=True,
        help_text=_('负责任务执行的成员'),
    )
    deadline = models.DateTimeField(
        verbose_name=_('截止日期'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('任务截止日期和时间'),
    )
    completed_at = models.DateTimeField(
        verbose_name=_('完成时间'),
        null=True,
        blank=True,
        help_text=_('任务实际完成的时间'),
    )
    completion_note = models.TextField(
        verbose_name=_('完成说明'),
        blank=True,
        default='',
        help_text=_('成员在完成任务时填写的文字总结'),
    )
    project = models.ForeignKey(
        to='lab_manager.LabProject',
        on_delete=models.SET_NULL,
        related_name='tasks',
        verbose_name=_('所属项目'),
        null=True,
        blank=True,
        help_text=_('关联的实验室项目'),
    )

    class Meta(NetBoxModel.Meta):
        verbose_name = _('任务')
        verbose_name_plural = _('任务')
        ordering = ('-created',)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('plugins:lab_manager:task', args=[self.pk])


class TaskComment(NetBoxModel):
    """任务评论 — 所有人可评论"""
    task = models.ForeignKey(
        to=Task,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_('所属任务'),
    )
    user = models.ForeignKey(
        to=User,
        on_delete=models.CASCADE,
        related_name='task_comments',
        verbose_name=_('评论人'),
    )
    content = models.TextField(
        verbose_name=_('评论内容'),
    )

    class Meta(NetBoxModel.Meta):
        verbose_name = _('任务评论')
        verbose_name_plural = _('任务评论')
        ordering = ('created',)

    def __str__(self):
        return f'{self.user.username}: {self.content[:50]}'


class TaskAttachment(NetBoxModel):
    """任务附件 — 图片和视频统一通过此模型上传"""
    task = models.ForeignKey(
        to=Task,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name=_('所属任务'),
    )
    file = models.FileField(
        verbose_name=_('文件'),
        upload_to='task_attachments/',
        validators=[validate_file_size],
        help_text=_('上传附件，最大 10MB'),
    )
    uploaded_by = models.ForeignKey(
        to=User,
        on_delete=models.CASCADE,
        related_name='uploaded_attachments',
        verbose_name=_('上传者'),
    )
    remark = models.CharField(
        verbose_name=_('附件说明'),
        max_length=200,
        blank=True,
    )

    class Meta(NetBoxModel.Meta):
        verbose_name = _('任务附件')
        verbose_name_plural = _('任务附件')
        ordering = ('-created',)

    def __str__(self):
        return f'{self.task.title} - 附件 ({self.pk})'
