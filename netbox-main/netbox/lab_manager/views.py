from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import connection
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from netbox.views import generic
from utilities.views import register_model_view

from .choices import HardwareApprovalStatusChoices, TaskStatusChoices
from .filtersets import HardwareFilterSet, TaskFilterSet
from .forms.filtersets import HardwareFilterForm, TaskFilterForm
from .forms.model_forms import HardwareForm, HardwareMemberForm, TaskForm, TaskMemberForm, TaskCommentForm
from .models import Hardware, Task, TaskAttachment, TaskComment
from .tables.hardware import HardwareTable
from .tables.task import TaskTable

# ── Hardware ──

@register_model_view(Hardware, 'list', path='', detail=False)
class HardwareListView(generic.ObjectListView):
    queryset = Hardware.objects.all()
    table = HardwareTable
    filterset = HardwareFilterSet
    filterset_form = HardwareFilterForm

    def has_permission(self):
        return self.request.user.is_authenticated

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not self.request.user.is_superuser and self.request.user.is_authenticated:
            # 普通用户：只显示已通过的和自己提交的
            qs = qs.filter(
                Q(approval_status=HardwareApprovalStatusChoices.APPROVED) |
                Q(submitted_by=self.request.user)
            )
        return qs


@register_model_view(Hardware)
class HardwareView(generic.ObjectView):
    queryset = Hardware.objects.all()

    def has_permission(self):
        return self.request.user.is_authenticated

    def get_extra_context(self, request, instance):
        return {
            'is_superuser': request.user.is_superuser,
        }


@register_model_view(Hardware, 'add', detail=False)
@register_model_view(Hardware, 'edit')
class HardwareEditView(generic.ObjectEditView):
    queryset = Hardware.objects.all()
    form = HardwareForm

    def has_permission(self):
        return self.request.user.is_authenticated

    def _resolve_role(self, request):
        if not request.user.is_superuser:
            self.form = HardwareMemberForm
        else:
            self.form = HardwareForm

    def alter_object(self, obj, request, url_args, url_kwargs):
        if not obj.pk:
            obj.submitted_by = request.user
            if request.user.is_superuser:
                obj.approval_status = HardwareApprovalStatusChoices.APPROVED
                obj.approved_by = request.user
        return obj

    def get(self, request, *args, **kwargs):
        self._resolve_role(request)
        if 'pk' in self.kwargs:
            obj = Hardware.objects.get(pk=self.kwargs['pk'])
            if not request.user.is_superuser and request.user != obj.submitted_by:
                messages.error(request, _('你没有权限编辑此硬件'))
                return redirect(obj.get_absolute_url())
            if obj.approval_status == HardwareApprovalStatusChoices.APPROVED and not request.user.is_superuser:
                messages.error(request, _('已审核通过的硬件不可编辑，请联系管理员'))
                return redirect(obj.get_absolute_url())
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self._resolve_role(request)
        if 'pk' in self.kwargs:
            obj = Hardware.objects.get(pk=self.kwargs['pk'])
            if not request.user.is_superuser and request.user != obj.submitted_by:
                messages.error(request, _('你没有权限编辑此硬件'))
                return redirect(obj.get_absolute_url())
            if obj.approval_status == HardwareApprovalStatusChoices.APPROVED and not request.user.is_superuser:
                messages.error(request, _('已审核通过的硬件不可编辑，请联系管理员'))
                return redirect(obj.get_absolute_url())
        return super().post(request, *args, **kwargs)


@register_model_view(Hardware, 'delete')
class HardwareDeleteView(generic.ObjectDeleteView):
    queryset = Hardware.objects.all()

    def has_permission(self):
        return self.request.user.is_superuser


# ── Task ──

@register_model_view(Task, 'list', path='', detail=False)
class TaskListView(generic.ObjectListView):
    queryset = Task.objects.all()
    table = TaskTable
    filterset = TaskFilterSet
    filterset_form = TaskFilterForm

    def has_permission(self):
        """所有人可查看"""
        return self.request.user.is_authenticated


@register_model_view(Task)
class TaskView(generic.ObjectView):
    queryset = Task.objects.all()

    def has_permission(self):
        """所有人可查看"""
        return self.request.user.is_authenticated

    def get_extra_context(self, request, instance):
        attachments = instance.attachments.all().order_by('-created')
        comments = instance.comments.all().order_by('created')
        user = request.user
        # 前端按钮控制
        can_operate = instance.status != TaskStatusChoices.COMPLETED and (user.is_superuser or user == instance.created_by or user == instance.assigned_to)
        can_edit = instance.status != TaskStatusChoices.COMPLETED and (user.is_superuser or user == instance.created_by or user == instance.assigned_to) and (
            not instance.deadline or timezone.now() <= instance.deadline
        )
        comment_form = TaskCommentForm()
        return {
            'attachments': attachments,
            'comments': comments,
            'can_operate': can_operate,
            'can_edit': can_edit,
            'comment_form': comment_form,
            'is_superuser': user.is_superuser,
        }


@register_model_view(Task, 'add', detail=False)
@register_model_view(Task, 'edit')
class TaskEditView(generic.ObjectEditView):
    queryset = Task.objects.all()
    form = TaskForm
    template_name = 'lab_manager/task_edit.html'

    def has_permission(self):
        """登录即可进入，具体权限在 get/post 中检查"""
        return self.request.user.is_authenticated

    def _resolve_role(self, request):
        """切换非管理员表单和模板"""
        if not request.user.is_superuser:
            self.form = TaskMemberForm
            self.template_name = 'lab_manager/task_edit_member.html'
        else:
            self.form = TaskForm
            self.template_name = 'lab_manager/task_edit.html'

    def get(self, request, *args, **kwargs):
        """检查编辑权限 + 截止时间 + 完成状态"""
        self._resolve_role(request)
        if 'pk' in self.kwargs:
            obj = Task.objects.get(pk=self.kwargs['pk'])
            if not request.user.is_superuser and request.user != obj.created_by and request.user != obj.assigned_to:
                messages.error(request, _('你没有权限编辑此任务'))
                return redirect(obj.get_absolute_url())
            if obj.status == TaskStatusChoices.COMPLETED:
                messages.error(request, _('任务已完成，无法编辑'))
                return redirect(obj.get_absolute_url())
            if obj.deadline and timezone.now() > obj.deadline and not request.user.is_superuser:
                messages.error(request, _('任务已过截止时间，无法编辑'))
                return redirect(obj.get_absolute_url())
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """检查编辑权限 + 截止时间 + 完成状态"""
        self._resolve_role(request)
        if 'pk' in self.kwargs:
            obj = Task.objects.get(pk=self.kwargs['pk'])
            if not request.user.is_superuser and request.user != obj.created_by and request.user != obj.assigned_to:
                messages.error(request, _('你没有权限编辑此任务'))
                return redirect(obj.get_absolute_url())
            if obj.status == TaskStatusChoices.COMPLETED:
                messages.error(request, _('任务已完成，无法编辑'))
                return redirect(obj.get_absolute_url())
            if obj.deadline and timezone.now() > obj.deadline and not request.user.is_superuser:
                messages.error(request, _('任务已过截止时间，无法编辑'))
                return redirect(obj.get_absolute_url())
        return super().post(request, *args, **kwargs)


@register_model_view(Task, 'delete')
class TaskDeleteView(generic.ObjectDeleteView):
    queryset = Task.objects.all()

    def has_permission(self):
        """仅超级管理员可删除"""
        return self.request.user.is_superuser


# ── 我的任务 ──

class MyTasksView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/my_tasks.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        tasks = Task.objects.filter(assigned_to=user).order_by('-created')
        ctx['pending_tasks'] = tasks.filter(status=TaskStatusChoices.PENDING)
        ctx['in_progress_tasks'] = tasks.filter(status=TaskStatusChoices.IN_PROGRESS)
        ctx['completed_tasks'] = tasks.filter(status=TaskStatusChoices.COMPLETED)
        return ctx


# ── 上传附件 ──

class TaskUploadAttachmentView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/task_upload.html'

    def dispatch(self, request, *args, **kwargs):
        task = Task.objects.get(pk=self.kwargs['pk'])
        # 权限 + 截止时间 + 完成状态检查
        if not request.user.is_superuser and request.user != task.assigned_to and request.user != task.created_by:
            messages.error(request, _('你没有权限上传附件'))
            return redirect(task.get_absolute_url())
        if task.status == TaskStatusChoices.COMPLETED:
            messages.error(request, _('任务已完成，无法上传附件'))
            return redirect(task.get_absolute_url())
        if task.deadline and timezone.now() > task.deadline and not request.user.is_superuser:
            messages.error(request, _('任务已过截止时间，无法上传附件'))
            return redirect(task.get_absolute_url())
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['task'] = Task.objects.get(pk=self.kwargs['pk'])
        return ctx

    def post(self, request, pk):
        task = Task.objects.get(pk=pk)
        files = request.FILES.getlist('files')
        remark = request.POST.get('remark', '')
        completion_note = request.POST.get('completion_note', '')
        if not request.user.is_superuser and request.user != task.assigned_to and request.user != task.created_by:
            messages.error(request, _('你没有权限上传附件'))
            return redirect(task.get_absolute_url())

        # 更新完成说明
        if completion_note:
            task.completion_note = completion_note

        count = 0
        for f in files:
            if f:
                TaskAttachment.objects.create(
                    task=task,
                    file=f,
                    uploaded_by=request.user,
                    remark=remark,
                )
                count += 1
        if count:
            if task.status == TaskStatusChoices.PENDING:
                task.status = TaskStatusChoices.IN_PROGRESS
            task.save()
            messages.success(request, _('成功上传 {} 个附件').format(count))
        elif completion_note:
            task.save()
            messages.success(request, _('完成说明已更新'))
        return redirect('plugins:lab_manager:task', pk=task.pk)


# ── 硬件审核 ──

class HardwareApprovalView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/hardware_approval.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            hw = Hardware.objects.get(pk=self.kwargs['pk'])
            messages.error(request, _('你没有权限审核硬件'))
            return redirect(hw.get_absolute_url())
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['hardware'] = Hardware.objects.get(pk=self.kwargs['pk'])
        return ctx

    def post(self, request, pk):
        if not request.user.is_superuser:
            hw = Hardware.objects.get(pk=pk)
            messages.error(request, _('你没有权限审核硬件'))
            return redirect(hw.get_absolute_url())

        hw = Hardware.objects.get(pk=pk)
        action = request.POST.get('action')
        note = request.POST.get('approval_note', '')

        if action == 'approve':
            hw.approval_status = HardwareApprovalStatusChoices.APPROVED
            hw.approved_by = request.user
            hw.approval_note = note
            hw.save()
            messages.success(request, _('硬件已审核通过'))
        elif action == 'reject':
            hw.approval_status = HardwareApprovalStatusChoices.REJECTED
            hw.approved_by = request.user
            hw.approval_note = note
            hw.save()
            messages.success(request, _('硬件已驳回'))
        return redirect(hw.get_absolute_url())


# ── 标记完成 ──

class TaskCompleteView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/task_complete.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            task = Task.objects.get(pk=self.kwargs['pk'])
            messages.error(request, _('你没有权限操作此任务'))
            return redirect(task.get_absolute_url())
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['task'] = Task.objects.get(pk=self.kwargs['pk'])
        return ctx

    def post(self, request, pk):
        if not request.user.is_superuser:
            task = Task.objects.get(pk=pk)
            messages.error(request, _('你没有权限操作此任务'))
            return redirect(task.get_absolute_url())
        task = Task.objects.get(pk=pk)
        task.completion_note = request.POST.get('completion_note', '')
        from .signals import mark_task_completed
        mark_task_completed(task)
        messages.success(request, _('任务已标记为完成'))
        return redirect('plugins:lab_manager:task', pk=task.pk)


# ── 评论 ──

class TaskCommentView(LoginRequiredMixin, TemplateView):
    """提交评论 — 所有人可评论"""

    def post(self, request, pk):
        task = Task.objects.get(pk=pk)
        form = TaskCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.task = task
            comment.user = request.user
            comment.save()
            messages.success(request, _('评论已发布'))
        else:
            messages.error(request, _('评论内容不能为空'))
        return redirect('plugins:lab_manager:task', pk=task.pk)


# ── 删除附件 ──

class TaskAttachmentDeleteView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/task_attachment_delete.html'

    def dispatch(self, request, *args, **kwargs):
        att = TaskAttachment.objects.get(pk=self.kwargs['pk'])
        if not request.user.is_superuser and request.user != att.task.assigned_to and request.user != att.task.created_by:
            messages.error(request, _('你没有权限删除此附件'))
            return redirect(att.task.get_absolute_url())
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['attachment'] = TaskAttachment.objects.get(pk=self.kwargs['pk'])
        return ctx

    def post(self, request, pk):
        att = TaskAttachment.objects.get(pk=pk)
        task = att.task
        if not request.user.is_superuser and request.user != task.assigned_to and request.user != task.created_by:
            messages.error(request, _('你没有权限删除此附件'))
            return redirect(task.get_absolute_url())
        file = att.file
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM lab_manager_taskattachment WHERE id = %s", [att.pk])
        file.delete(save=False)
        messages.success(request, _('附件已删除'))
        return redirect('plugins:lab_manager:task', pk=task.pk)


# ── 首页 ──

class LabHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        is_admin = user.is_superuser

        if is_admin:
            ctx['is_admin'] = True
            ctx['hardware_total'] = Hardware.objects.count()
            ctx['hardware_in_use'] = Hardware.objects.filter(status='in_use').count()
            ctx['hardware_idle'] = Hardware.objects.filter(status='idle').count()
            ctx['task_total'] = Task.objects.count()
            ctx['task_in_progress'] = Task.objects.filter(status='in_progress').count()
            ctx['task_completed'] = Task.objects.filter(status='completed').count()
        else:
            ctx['my_pending_tasks'] = Task.objects.filter(
                assigned_to=user,
                status__in=[TaskStatusChoices.PENDING, TaskStatusChoices.IN_PROGRESS],
            ).order_by('-created')[:5]

        return ctx
