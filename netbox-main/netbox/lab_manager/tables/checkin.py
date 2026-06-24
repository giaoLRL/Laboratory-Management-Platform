import django_tables2 as tables

from netbox.tables import NetBoxTable

from ..models import CheckInRecord


class CheckInRecordTable(NetBoxTable):
    user = tables.Column(linkify=True)
    address = tables.Column()
    latitude = tables.Column()
    longitude = tables.Column()
    accuracy = tables.Column()
    note = tables.Column()

    class Meta(NetBoxTable.Meta):
        model = CheckInRecord
        fields = (
            'pk', 'id', 'user', 'photo', 'latitude', 'longitude',
            'accuracy', 'address', 'note',
            'tags', 'created', 'last_updated',
        )
        default_columns = (
            'user', 'address', 'latitude', 'longitude', 'note', 'created',
        )
