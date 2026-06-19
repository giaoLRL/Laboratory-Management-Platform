import django_tables2 as tables

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
    quantity = tables.Column()

    class Meta(NetBoxTable.Meta):
        model = Hardware
        fields = (
            'pk', 'id', 'name', 'category', 'model_number',
            'manufacturer', 'quantity', 'status', 'approval_status', 'custodian',
            'storage_location', 'purchase_date', 'tags',
            'created', 'last_updated',
        )
        default_columns = (
            'name', 'category', 'model_number', 'quantity',
            'status', 'approval_status', 'custodian', 'storage_location',
        )
