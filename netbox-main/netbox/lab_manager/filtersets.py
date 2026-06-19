import django_filters
from django.utils.translation import gettext_lazy as _

from netbox.filtersets import NetBoxModelFilterSet
from users.models import User

from .choices import (
    HardwareApprovalStatusChoices,
    HardwareCategoryChoices,
    HardwareStatusChoices,
    TaskPriorityChoices,
    TaskStatusChoices,
)
from .models import Hardware, Task, TaskAttachment


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
