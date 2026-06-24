import django_tables2 as tables

from netbox.tables import NetBoxTable

from ..models import MemberOpenRecord


class MemberOpenRecordTable(NetBoxTable):
    user = tables.Column(linkify=True)
    page_title = tables.Column()
    path = tables.Column()
    target_type = tables.Column()
    ip_address = tables.Column()

    class Meta(NetBoxTable.Meta):
        model = MemberOpenRecord
        fields = (
            'pk', 'id', 'user', 'page_title', 'path',
            'target_type', 'target_id', 'ip_address',
            'tags', 'created', 'last_updated',
        )
        default_columns = (
            'user', 'page_title', 'path', 'target_type', 'ip_address', 'created',
        )
