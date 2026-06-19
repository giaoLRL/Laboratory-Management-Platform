from netbox.forms.filtersets import NetBoxModelFilterSetForm
from utilities.forms.fields import TagFilterField
from utilities.forms.rendering import FieldSet

from ..filtersets import HardwareFilterSet, TaskFilterSet
from ..models import Hardware, Task


class HardwareFilterForm(NetBoxModelFilterSetForm):
    model = Hardware
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('category', 'status', 'custodian_id', name='筛选条件'),
    )
    tag = TagFilterField(Hardware)


class TaskFilterForm(NetBoxModelFilterSetForm):
    model = Task
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('assigned_to_id', 'status', 'priority', name='筛选条件'),
    )
    tag = TagFilterField(Task)
