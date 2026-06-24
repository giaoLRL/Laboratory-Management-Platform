from django.db import models
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel

from ..choices import AgentToolCategoryChoices, AgentToolTypeChoices


class AgentTool(NetBoxModel):
    """智能体工具定义——可在管理界面模块化管理"""

    name = models.CharField(
        verbose_name=_('工具标识'),
        max_length=80,
        unique=True,
        help_text=_('唯一标识符，如 list_records、create_task。不可重复'),
    )
    display_name = models.CharField(
        verbose_name=_('显示名称'),
        max_length=120,
        help_text=_('管理界面中显示的中文名称，如"列表查询""任务创建"'),
    )
    description = models.TextField(
        verbose_name=_('工具描述'),
        help_text=_('传递给 LLM 的工具说明，用于让模型理解工具的用途和参数'),
    )
    tool_type = models.CharField(
        verbose_name=_('工具类型'),
        max_length=30,
        choices=AgentToolTypeChoices,
        db_index=True,
        help_text=_('工具执行类型，决定运行时的调用逻辑'),
    )
    category = models.CharField(
        verbose_name=_('分类'),
        max_length=30,
        choices=AgentToolCategoryChoices,
        default='data_query',
        db_index=True,
        help_text=_('工具分类：数据查询 / 任务管理 / 分析诊断 / 系统管理'),
    )
    is_enabled = models.BooleanField(
        verbose_name=_('启用'),
        default=True,
        db_index=True,
        help_text=_('关闭后 LLM 将不再调用此工具'),
    )
    parameters_schema = models.JSONField(
        verbose_name=_('参数定义'),
        default=dict,
        blank=True,
        help_text=_(
            'JSON Schema 格式的参数定义。示例：'
            '{"model": {"type": "string", "description": "要查询的模型名称"}, '
            '"limit": {"type": "integer", "default": 20}}'
        ),
    )
    execution_key = models.CharField(
        verbose_name=_('执行标识'),
        max_length=80,
        blank=True,
        default='',
        help_text=_(
            '对应 tool_registry.py 中的执行函数 key。'
            '若为空则与 name 相同。常用值：platform_query / task_create / '
            'video_search / hardware_gap / describe_data'
        ),
    )
    default_args = models.JSONField(
        verbose_name=_('默认参数'),
        default=dict,
        blank=True,
        help_text=_('工具调用时的默认参数，可被 LLM 传入的参数覆盖'),
    )
    requires_superuser = models.BooleanField(
        verbose_name=_('需要管理员权限'),
        default=False,
        help_text=_('勾选后只有超级管理员可调用此工具'),
    )
    sort_order = models.PositiveSmallIntegerField(
        verbose_name=_('排序'),
        default=0,
        help_text=_('数字越小越靠前'),
    )

    class Meta(NetBoxModel.Meta):
        verbose_name = _('智能体工具')
        verbose_name_plural = _('智能体工具')
        ordering = ('sort_order', 'name')

    def __str__(self):
        status = '🟢' if self.is_enabled else '⚪'
        return f'{status} {self.display_name or self.name}'

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('plugins:lab_manager:agenttool', args=[self.pk])

    @property
    def effective_execution_key(self) -> str:
        """返回实际使用的执行标识，为空时回退到 name"""
        return self.execution_key or self.name
