import django_tables2 as tables

from netbox.tables import NetBoxTable
from netbox.tables.columns import ChoiceFieldColumn

from ..models import Task


class TaskTable(NetBoxTable):
    title = tables.Column(linkify=True)
    status = ChoiceFieldColumn()
    priority = ChoiceFieldColumn()
    assigned_to = tables.Column(linkify=True)
    created_by = tables.Column(linkify=True)
    deadline = tables.DateTimeColumn()

    class Meta(NetBoxTable.Meta):
        model = Task
        fields = (
            'pk', 'id', 'title', 'status', 'priority',
            'assigned_to', 'created_by', 'deadline', 'tags',
            'created', 'last_updated',
        )
        default_columns = (
            'title', 'status', 'priority', 'assigned_to', 'deadline',
        )
