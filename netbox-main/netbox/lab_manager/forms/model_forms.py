from django import forms as django_forms

from netbox.forms import NetBoxModelForm
from utilities.forms.widgets import DateTimePicker

from ..models import CheckInRecord, Hardware, Task, TaskComment


class CheckInForm(django_forms.ModelForm):
    class Meta:
        model = CheckInRecord
        fields = ('photo', 'latitude', 'longitude', 'accuracy', 'address', 'note')
        widgets = {
            'photo': django_forms.ClearableFileInput(attrs={
                'accept': 'image/*',
                'capture': 'environment',
                'class': 'form-control',
            }),
            'latitude': django_forms.HiddenInput(),
            'longitude': django_forms.HiddenInput(),
            'accuracy': django_forms.HiddenInput(),
            'address': django_forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '例如：A 楼 302 实验室',
            }),
            'note': django_forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': '可填写打卡说明',
            }),
        }


class TaskCommentForm(django_forms.ModelForm):
    """评论表单"""
    class Meta:
        model = TaskComment
        fields = ('content',)
        widgets = {
            'content': django_forms.Textarea(attrs={
                'rows': 2,
                'placeholder': '输入评论...',
                'class': 'form-control',
            }),
        }
        labels = {
            'content': '',
        }


class HardwareForm(NetBoxModelForm):
    """管理员硬件表单：包含审批字段"""
    class Meta:
        model = Hardware
        fields = (
            'name', 'category', 'model_number', 'manufacturer',
            'quantity', 'unit_price', 'purchase_date', 'purchase_link',
            'status', 'storage_location', 'custodian', 'image', 'invoice_image', 'remarks',
            'approval_status', 'approved_by', 'approval_note', 'tags',
        )


class HardwareMemberForm(NetBoxModelForm):
    """非管理员硬件表单：不含审批字段，提交后进入待审核"""

    class Meta:
        model = Hardware
        fields = (
            'name', 'category', 'model_number', 'manufacturer',
            'quantity', 'unit_price', 'purchase_date', 'purchase_link',
            'status', 'storage_location', 'custodian', 'image', 'invoice_image', 'remarks', 'tags',
        )


class TaskForm(NetBoxModelForm):
    deadline = django_forms.DateTimeField(
        widget=DateTimePicker(),
        required=False,
        label='截止日期',
    )

    class Meta:
        model = Task
        fields = (
            'title', 'description', 'priority', 'status',
            'created_by', 'assigned_to', 'deadline', 'completion_note', 'tags',
        )


class TaskMemberForm(NetBoxModelForm):
    """非管理员编辑表单：只能修改完成说明"""

    class Meta:
        model = Task
        fields = ('completion_note',)
        widgets = {
            'completion_note': django_forms.Textarea(attrs={'rows': 6, 'placeholder': '请描述你的完成情况、遇到的问题、解决方案等...'}),
        }
