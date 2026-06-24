import django_filters
from django.utils.translation import gettext_lazy as _

from netbox.filtersets import NetBoxModelFilterSet
from users.models import User

from .choices import (
    AgentToolCategoryChoices,
    AgentToolTypeChoices,
    HardwareApprovalStatusChoices,
    HardwareCategoryChoices,
    HardwareStatusChoices,
    TaskPriorityChoices,
    TaskStatusChoices,
)
from .models.borrow import BorrowStatusChoices
from .models import (
    AgentTool, CheckInRecord, Hardware, HardwareBorrowRecord,
    LabProject, MemberOpenRecord, Task, TaskAttachment,
)
from .models.project import ProjectStatusChoices


class AgentToolFilterSet(NetBoxModelFilterSet):
    tool_type = django_filters.MultipleChoiceFilter(
        choices=AgentToolTypeChoices,
    )
    category = django_filters.MultipleChoiceFilter(
        choices=AgentToolCategoryChoices,
    )
    is_enabled = django_filters.BooleanFilter()

    class Meta:
        model = AgentTool
        fields = ('name', 'display_name', 'tool_type', 'category', 'is_enabled')


class HardwareFilterSet(NetBoxModelFilterSet):
    category = django_filters.MultipleChoiceFilter(
        choices=HardwareCategoryChoices,
    )
    status = django_filters.MultipleChoiceFilter(
        choices=HardwareStatusChoices,
    )
    approval_status = django_filters.MultipleChoiceFilter(
        choices=HardwareApprovalStatusChoices,
    )
    custodian_id = django_filters.ModelMultipleChoiceFilter(
        field_name='custodian',
        queryset=User.objects.all(),
        label=_('保管人'),
    )

    class Meta:
        model = Hardware
        fields = ('name', 'category', 'status', 'approval_status', 'model_number', 'manufacturer')


class TaskFilterSet(NetBoxModelFilterSet):
    assigned_to_id = django_filters.ModelMultipleChoiceFilter(
        field_name='assigned_to',
        queryset=User.objects.all(),
        label=_('执行人'),
    )
    created_by_id = django_filters.ModelMultipleChoiceFilter(
        field_name='created_by',
        queryset=User.objects.all(),
        label=_('创建人'),
    )
    status = django_filters.MultipleChoiceFilter(
        choices=TaskStatusChoices,
    )
    priority = django_filters.MultipleChoiceFilter(
        choices=TaskPriorityChoices,
    )

    class Meta:
        model = Task
        fields = ('title', 'status', 'priority')


class TaskAttachmentFilterSet(NetBoxModelFilterSet):
    task_id = django_filters.ModelMultipleChoiceFilter(
        field_name='task',
        queryset=Task.objects.all(),
        label=_('所属任务'),
    )

    class Meta:
        model = TaskAttachment
        fields = ('task_id',)


class HardwareBorrowRecordFilterSet(NetBoxModelFilterSet):
    hardware_id = django_filters.ModelMultipleChoiceFilter(
        field_name='hardware',
        queryset=Hardware.objects.all(),
        label=_('硬件'),
    )
    borrower_id = django_filters.ModelMultipleChoiceFilter(
        field_name='borrower',
        queryset=User.objects.all(),
        label=_('借用人'),
    )
    status = django_filters.MultipleChoiceFilter(
        choices=BorrowStatusChoices.choices,
    )

    class Meta:
        model = HardwareBorrowRecord
        fields = ('hardware_id', 'borrower_id', 'status')


class CheckInRecordFilterSet(NetBoxModelFilterSet):
    user_id = django_filters.ModelMultipleChoiceFilter(
        field_name='user',
        queryset=User.objects.all(),
        label=_('打卡人'),
    )

    class Meta:
        model = CheckInRecord
        fields = ('user_id', 'address', 'note')


class MemberOpenRecordFilterSet(NetBoxModelFilterSet):
    user_id = django_filters.ModelMultipleChoiceFilter(
        field_name='user',
        queryset=User.objects.all(),
        label=_('成员'),
    )

    class Meta:
        model = MemberOpenRecord
        fields = ('user_id', 'page_title', 'target_type')


class LabProjectFilterSet(NetBoxModelFilterSet):
    leader_id = django_filters.ModelMultipleChoiceFilter(
        field_name='leader',
        queryset=User.objects.all(),
        label=_('项目负责人'),
    )
    status = django_filters.MultipleChoiceFilter(
        choices=ProjectStatusChoices.choices,
    )

    class Meta:
        model = LabProject
        fields = ('name', 'leader_id', 'status')
