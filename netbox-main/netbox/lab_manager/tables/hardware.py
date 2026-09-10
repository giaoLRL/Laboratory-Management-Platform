import django_tables2 as tables
from django.utils.html import format_html

from netbox.tables import NetBoxTable
from netbox.tables.columns import ChoiceFieldColumn

from ..models import Hardware


class HardwareTable(NetBoxTable):
    name = tables.Column(linkify=True)
    category = ChoiceFieldColumn()
    status = ChoiceFieldColumn()
    approval_status = ChoiceFieldColumn()
    custodian = tables.Column(linkify=True)
    storage_location = tables.Column()
    purchase_date = tables.DateColumn()
    quantity = tables.Column(verbose_name='可用/总量')

    def render_quantity(self, value, record):
        """把纯数字渲染为库存水位条（可借/总量，含阈值配色）。"""
        available = int(value or 0)
        outstanding = int(getattr(record, 'outstanding', 0) or 0)
        total = available + outstanding
        minimum = int(record.minimum_stock or 0)
        if available <= 0:
            level = 'danger'
        elif (minimum and available <= minimum) or (total and available / total <= 0.25):
            level = 'warning'
        else:
            level = 'ok'
        width = 100 if total <= 0 else max(2, min(100, round(available / total * 100)))
        return format_html(
            '<div class="lm-waterline lm-waterline--{}" title="可用 {} / 总量 {}（在借 {}，阈值 {}）">'
            '<div class="lm-waterline__track"><div class="lm-waterline__fill" style="width:{}%"></div></div>'
            '<span class="lm-waterline__text">{}/{}</span></div>',
            level, available, total, outstanding, minimum, width, available, total,
        )

    class Meta(NetBoxTable.Meta):
        model = Hardware
        fields = (
            'pk', 'id', 'name', 'category', 'model_number',
            'manufacturer', 'quantity', 'status', 'approval_status', 'custodian',
            'storage_location', 'purchase_date', 'tags',
            'created', 'last_updated',
        )
        # 精简默认列（5 列）；其余列可在表格配置中按需开启
        default_columns = (
            'name', 'category', 'quantity', 'status', 'approval_status',
        )
