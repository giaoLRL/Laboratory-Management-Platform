from netbox.forms.filtersets import NetBoxModelFilterSetForm
from utilities.forms.fields import TagFilterField
from utilities.forms.rendering import FieldSet

from ..filtersets import (
    AgentToolFilterSet,
    CheckInRecordFilterSet,
    HardwareBorrowRecordFilterSet,
    HardwareFilterSet,
    LabProjectFilterSet,
    MemberOpenRecordFilterSet,
    TaskFilterSet,
)
from ..models import AgentTool, CheckInRecord, Hardware, HardwareBorrowRecord, LabProject, MemberOpenRecord, Task


class HardwareFilterForm(NetBoxModelFilterSetForm):
    model = Hardware
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('category', 'status', 'approval_status', 'model_number', 'custodian_id', name='筛选条件'),
    )
    tag = TagFilterField(Hardware)


class TaskFilterForm(NetBoxModelFilterSetForm):
    model = Task
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('assigned_to_id', 'created_by_id', 'status', 'priority', name='筛选条件'),
    )
    tag = TagFilterField(Task)


class AgentToolFilterForm(NetBoxModelFilterSetForm):
    model = AgentTool
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('tool_type', 'category', 'is_enabled', name='筛选条件'),
    )
    tag = TagFilterField(AgentTool)


class CheckInRecordFilterForm(NetBoxModelFilterSetForm):
    model = CheckInRecord
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('user_id', name='筛选条件'),
    )
    tag = TagFilterField(CheckInRecord)


class MemberOpenRecordFilterForm(NetBoxModelFilterSetForm):
    model = MemberOpenRecord
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('user_id', 'target_type', name='筛选条件'),
    )
    tag = TagFilterField(MemberOpenRecord)


class HardwareBorrowRecordFilterForm(NetBoxModelFilterSetForm):
    model = HardwareBorrowRecord
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('hardware_id', 'borrower_id', 'status', name='筛选条件'),
    )
    tag = TagFilterField(HardwareBorrowRecord)


class LabProjectFilterForm(NetBoxModelFilterSetForm):
    model = LabProject
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('leader_id', 'status', name='筛选条件'),
    )
    tag = TagFilterField(LabProject)
