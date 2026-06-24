import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable, columns

from ..models import AgentTool


class AgentToolTable(NetBoxTable):
    name = tables.Column(
        linkify=True,
        verbose_name=_('工具标识'),
    )
    display_name = tables.Column(
        verbose_name=_('显示名称'),
    )
    tool_type = columns.ChoiceFieldColumn(
        verbose_name=_('工具类型'),
    )
    category = columns.ChoiceFieldColumn(
        verbose_name=_('分类'),
    )
    is_enabled = columns.BooleanColumn(
        verbose_name=_('启用'),
    )
    requires_superuser = columns.BooleanColumn(
        verbose_name=_('管理员权限'),
    )
    sort_order = tables.Column(
        verbose_name=_('排序'),
    )

    class Meta(NetBoxTable.Meta):
        model = AgentTool
        fields = (
            'pk', 'name', 'display_name', 'tool_type', 'category',
            'is_enabled', 'requires_superuser', 'sort_order', 'description',
        )
        default_columns = (
            'name', 'display_name', 'tool_type', 'category',
            'is_enabled', 'requires_superuser', 'sort_order',
        )
