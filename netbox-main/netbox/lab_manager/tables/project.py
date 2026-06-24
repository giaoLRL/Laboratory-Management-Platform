import django_tables2 as tables

from netbox.tables import NetBoxTable
from netbox.tables.columns import ChoiceFieldColumn

from ..models import LabProject


class LabProjectTable(NetBoxTable):
    name = tables.Column(linkify=True)
    status = ChoiceFieldColumn()
    leader = tables.Column(linkify=True)
    start_date = tables.DateColumn()
    end_date = tables.DateColumn()

    class Meta(NetBoxTable.Meta):
        model = LabProject
        fields = (
            'pk', 'id', 'name', 'status', 'leader',
            'start_date', 'end_date',
            'tags', 'created', 'last_updated',
        )
        default_columns = (
            'name', 'status', 'leader', 'start_date', 'end_date',
        )
