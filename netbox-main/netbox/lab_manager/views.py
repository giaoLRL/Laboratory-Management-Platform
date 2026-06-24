import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .logging_config import logger
from django.views.generic import TemplateView, View
from netbox.views import generic
from utilities.views import register_model_view

from .choices import HardwareApprovalStatusChoices, TaskStatusChoices
from .filtersets import (
    AgentToolFilterSet, HardwareBorrowRecordFilterSet, HardwareFilterSet,
    LabProjectFilterSet, TaskFilterSet,
)
from .forms.filtersets import (
    AgentToolFilterForm, HardwareBorrowRecordFilterForm, HardwareFilterForm,
    LabProjectFilterForm, TaskFilterForm,
)
from .forms.model_forms import (
    AgentToolForm, CheckInForm, HardwareBorrowRecordForm, HardwareForm,
    HardwareMemberForm, LabProjectForm, TaskForm, TaskMemberForm, TaskCommentForm,
)
from .models import (
    AgentConversation, AgentMessage, AgentTool, CheckInRecord, Hardware,
    HardwareBorrowRecord, LabProject, MemberOpenRecord, Notification,
    Task, TaskAttachment, TaskComment,
)
from .models.borrow import BorrowStatusChoices
from .services import AgentToolOrchestrator, BackendAgentService, LangChainAgentService
from .tables.agent_tool import AgentToolTable
from .tables.borrow import HardwareBorrowRecordTable
from .tables.hardware import HardwareTable
from .tables.project import LabProjectTable
from .tables.task import TaskTable

# ── Hardware ──

@register_model_view(Hardware, 'list', path='', detail=False)
class HardwareListView(generic.ObjectListView):
    queryset = Hardware.objects.select_related('custodian', 'submitted_by')
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
    queryset = Task.objects.select_related('assigned_to', 'created_by')
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

    def alter_object(self, obj, request, url_args, url_kwargs):
        """创建任务时自动设置创建者"""
        if not obj.pk:
            obj.created_by = request.user
        return obj

    def get(self, request, *args, **kwargs):
        """检查编辑权限 + 截止时间 + 完成状态"""
        self._resolve_role(request)
        # 非管理员不能创建任务
        if 'pk' not in self.kwargs and not request.user.is_superuser:
            messages.error(request, _('你没有权限创建任务，请联系管理员'))
            return redirect('plugins:lab_manager:task_list')
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
        # 非管理员不能创建任务
        if 'pk' not in self.kwargs and not request.user.is_superuser:
            messages.error(request, _('你没有权限创建任务，请联系管理员'))
            return redirect('plugins:lab_manager:task_list')
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


# ── 硬件借出/归还 ──

@register_model_view(HardwareBorrowRecord, 'list', path='', detail=False)
class HardwareBorrowRecordListView(generic.ObjectListView):
    queryset = HardwareBorrowRecord.objects.select_related('hardware', 'borrower')
    table = HardwareBorrowRecordTable
    filterset = HardwareBorrowRecordFilterSet
    filterset_form = HardwareBorrowRecordFilterForm

    def has_permission(self):
        return self.request.user.is_authenticated

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if self.request.user.is_authenticated and not self.request.user.is_superuser:
            qs = qs.filter(borrower=self.request.user)
        return qs


@register_model_view(HardwareBorrowRecord)
class HardwareBorrowRecordView(generic.ObjectView):
    queryset = HardwareBorrowRecord.objects.select_related('hardware', 'borrower')

    def has_permission(self):
        return self.request.user.is_authenticated

    def get_extra_context(self, request, instance):
        return {
            'is_overdue': instance.is_overdue,
            'can_return': (
                instance.status == BorrowStatusChoices.BORROWED
                and (request.user.is_superuser or request.user == instance.borrower)
            ),
        }


@register_model_view(HardwareBorrowRecord, 'add', detail=False)
@register_model_view(HardwareBorrowRecord, 'edit')
class HardwareBorrowRecordEditView(generic.ObjectEditView):
    queryset = HardwareBorrowRecord.objects.all()
    form = HardwareBorrowRecordForm

    def has_permission(self):
        return self.request.user.is_authenticated

    def alter_object(self, obj, request, url_args, url_kwargs):
        if not obj.pk:
            obj.borrower = request.user
            obj.status = BorrowStatusChoices.BORROWED
        return obj


@register_model_view(HardwareBorrowRecord, 'delete')
class HardwareBorrowRecordDeleteView(generic.ObjectDeleteView):
    queryset = HardwareBorrowRecord.objects.all()

    def has_permission(self):
        return self.request.user.is_superuser


# ── 归还硬件 ──

class HardwareBorrowReturnView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/hardwareborrowrecord_return.html'

    def dispatch(self, request, *args, **kwargs):
        record = HardwareBorrowRecord.objects.select_related('hardware', 'borrower').get(pk=self.kwargs['pk'])
        if record.status != BorrowStatusChoices.BORROWED:
            messages.error(request, _('该记录不是借出中状态，无法归还'))
            return redirect(record.get_absolute_url())
        if not request.user.is_superuser and request.user != record.borrower:
            messages.error(request, _('你没有权限归还此硬件'))
            return redirect(record.get_absolute_url())
        self.record = record
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['record'] = self.record
        ctx['is_overdue'] = self.record.is_overdue
        return ctx

    def post(self, request, pk):
        record = HardwareBorrowRecord.objects.get(pk=pk)
        notes = request.POST.get('notes', '')
        record.mark_returned(notes=notes)
        messages.success(request, _('硬件已归还'))
        return redirect(record.get_absolute_url())


# ── 实验项目管理 ──

@register_model_view(LabProject, 'list', path='', detail=False)
class LabProjectListView(generic.ObjectListView):
    queryset = LabProject.objects.select_related('leader').prefetch_related('members')
    table = LabProjectTable
    filterset = LabProjectFilterSet
    filterset_form = LabProjectFilterForm

    def has_permission(self):
        return self.request.user.is_authenticated


@register_model_view(LabProject)
class LabProjectView(generic.ObjectView):
    queryset = LabProject.objects.select_related('leader').prefetch_related('members')

    def has_permission(self):
        return self.request.user.is_authenticated

    def get_extra_context(self, request, instance):
        from .models.task import Task
        project_tasks = instance.tasks.all().order_by('-created')
        return {
            'project_tasks': project_tasks,
            'hardware_count': instance.hardware_count,
            'task_count': instance.task_count,
        }


@register_model_view(LabProject, 'add', detail=False)
@register_model_view(LabProject, 'edit')
class LabProjectEditView(generic.ObjectEditView):
    queryset = LabProject.objects.all()
    form = LabProjectForm

    def has_permission(self):
        return self.request.user.is_authenticated


@register_model_view(LabProject, 'delete')
class LabProjectDeleteView(generic.ObjectDeleteView):
    queryset = LabProject.objects.all()

    def has_permission(self):
        return self.request.user.is_superuser


# ── 我的任务 ──

class MyTasksView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/my_tasks.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        tasks = Task.objects.filter(assigned_to=user).select_related('assigned_to', 'created_by').order_by('-created')
        ctx['pending_tasks'] = tasks.filter(status=TaskStatusChoices.PENDING)
        ctx['in_progress_tasks'] = tasks.filter(status=TaskStatusChoices.IN_PROGRESS)
        ctx['completed_tasks'] = tasks.filter(status=TaskStatusChoices.COMPLETED)
        return ctx


def _client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def record_member_open(request, *, page_title='', target_type='', target_id=None):
    if not request.user.is_authenticated:
        return
    MemberOpenRecord.objects.create(
        user=request.user,
        path=request.get_full_path()[:500],
        page_title=page_title[:100],
        target_type=target_type[:50],
        target_id=target_id,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:1000],
        ip_address=_client_ip(request),
    )


class MemberOpenRecordListView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'lab_manager/member_open_record_list.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        records = MemberOpenRecord.objects.select_related('user').order_by('-created')
        username = self.request.GET.get('username')
        target_type = self.request.GET.get('target_type')
        if username:
            records = records.filter(
                Q(user__username__icontains=username) |
                Q(user__first_name__icontains=username) |
                Q(user__last_name__icontains=username) |
                Q(user__email__icontains=username)
            )
        if target_type:
            records = records.filter(target_type=target_type)
        ctx['records'] = records[:300]
        ctx['username'] = username or ''
        ctx['target_type'] = target_type or ''

        # ── 统计数据 ──
        today = timezone.localdate()
        today_start = timezone.make_aware(
            timezone.datetime.combine(today, timezone.datetime.min.time())
        )
        week_start = today - timedelta(days=today.weekday())

        base_qs = MemberOpenRecord.objects.all()

        # 今日统计
        today_records = base_qs.filter(created__gte=today_start)
        ctx['today_total'] = today_records.count()
        ctx['today_users'] = today_records.values('user').distinct().count()
        ctx['today_checkins'] = today_records.filter(target_type='checkin').count()

        # 本周统计
        week_records = base_qs.filter(created__date__gte=week_start)
        ctx['week_total'] = week_records.count()
        ctx['week_users'] = week_records.values('user').distinct().count()

        # 本月统计
        month_start = today.replace(day=1)
        month_records = base_qs.filter(created__date__gte=month_start)
        ctx['month_total'] = month_records.count()
        ctx['month_users'] = month_records.values('user').distinct().count()

        # 总览
        ctx['all_total'] = base_qs.count()
        ctx['all_users'] = base_qs.values('user').distinct().count()

        # 最近7天每日趋势
        daily_trend = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            day_start = timezone.make_aware(
                timezone.datetime.combine(d, timezone.datetime.min.time())
            )
            day_end = timezone.make_aware(
                timezone.datetime.combine(d + timedelta(days=1), timezone.datetime.min.time())
            )
            cnt = base_qs.filter(created__gte=day_start, created__lt=day_end).count()
            users_cnt = base_qs.filter(
                created__gte=day_start, created__lt=day_end,
            ).values('user').distinct().count()
            daily_trend.append({
                'date': d,
                'label': d.strftime('%m/%d'),
                'count': cnt,
                'users': users_cnt,
                'is_today': d == today,
            })
        ctx['daily_trend'] = daily_trend

        # 最活跃成员 Top 10
        from django.db.models import Count as AggCount
        ctx['top_users'] = (
            base_qs.values('user__username', 'user__first_name', 'user__last_name')
            .annotate(cnt=AggCount('id'))
            .order_by('-cnt')[:10]
        )

        return ctx


class MemberOpenRecordDetailView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'lab_manager/member_open_record_detail.html'

    def test_func(self):
        return self.request.user.is_superuser

    def dispatch(self, request, *args, **kwargs):
        self.record = MemberOpenRecord.objects.select_related('user').get(pk=self.kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['record'] = self.record
        return ctx


# ── 拍照定位打卡 ──

class CheckInCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/checkin_form.html'

    def get(self, request, *args, **kwargs):
        record_member_open(request, page_title='拍照定位打卡', target_type='checkin_create')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = CheckInForm()
        ctx['recent_checkins'] = CheckInRecord.objects.filter(user=self.request.user).order_by('-created')[:5]
        return ctx

    def post(self, request):
        form = CheckInForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                checkin = form.save(commit=False)
                checkin.user = request.user
                checkin.save()
                form.save_m2m()
                # 同步创建成员打卡记录，带上照片和定位
                MemberOpenRecord.objects.create(
                user=request.user,
                path=request.get_full_path()[:500],
                page_title='拍照定位打卡',
                target_type='checkin',
                target_id=checkin.pk,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:1000],
                ip_address=_client_ip(request),
                photo=checkin.photo,
                latitude=checkin.latitude,
                longitude=checkin.longitude,
                accuracy=checkin.accuracy,
                address=checkin.address,
                note=checkin.note,
            )
            messages.success(request, _('打卡成功'))
            return redirect('plugins:lab_manager:checkin_detail', pk=checkin.pk)

        messages.error(request, _('打卡失败，请确认已上传照片并允许浏览器获取定位'))
        return self.render_to_response({
            'form': form,
            'recent_checkins': CheckInRecord.objects.filter(user=request.user).order_by('-created')[:5],
        })


class CheckInListView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/checkin_list.html'

    def get(self, request, *args, **kwargs):
        record_member_open(request, page_title='打卡记录', target_type='checkin_list')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        records = CheckInRecord.objects.select_related('user').order_by('-created')
        if not self.request.user.is_superuser:
            records = records.filter(user=self.request.user)
        ctx['records'] = records[:200]
        ctx['is_superuser'] = self.request.user.is_superuser
        return ctx


class CheckInDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/checkin_detail.html'

    def dispatch(self, request, *args, **kwargs):
        record = CheckInRecord.objects.select_related('user').get(pk=self.kwargs['pk'])
        if not request.user.is_superuser and record.user != request.user:
            messages.error(request, _('你没有权限查看此打卡记录'))
            return redirect('plugins:lab_manager:checkin_list')
        self.record = record
        record_member_open(request, page_title='打卡详情', target_type='checkin', target_id=record.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['record'] = self.record
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
        from .services.task_utils import mark_task_completed
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
        att.delete()  # ORM delete — signals.py 的 pre_delete 信号自动清理物理文件
        # If the signal didn't fire (edge case), clean up manually
        if file and file.storage.exists(file.name):
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
        today = timezone.localdate()

        if is_admin:
            ctx['is_admin'] = True
            # 基础统计
            ctx['hardware_total'] = Hardware.objects.count()
            ctx['hardware_in_use'] = Hardware.objects.filter(status='in_use').count()
            ctx['hardware_idle'] = Hardware.objects.filter(status='idle').count()
            ctx['task_total'] = Task.objects.count()
            ctx['task_in_progress'] = Task.objects.filter(status='in_progress').count()
            ctx['task_completed'] = Task.objects.filter(status='completed').count()
            ctx['checkin_today'] = CheckInRecord.objects.filter(created__date=today).count()
            # 新增统计
            ctx['pending_approval_count'] = Hardware.objects.filter(
                approval_status=HardwareApprovalStatusChoices.PENDING,
            ).count()
            ctx['overdue_tasks'] = Task.objects.filter(
                deadline__lt=timezone.now(),
                status__in=['pending', 'in_progress'],
            ).count()
            ctx['borrowed_count'] = HardwareBorrowRecord.objects.filter(status='borrowed').count()
            # 低库存告警
            from django.db.models import F
            ctx['low_stock_items'] = Hardware.objects.filter(
                minimum_stock__gt=0,
            ).filter(quantity__lt=F('minimum_stock'))[:10]
            # 待审批列表
            ctx['pending_approvals'] = Hardware.objects.filter(
                approval_status=HardwareApprovalStatusChoices.PENDING,
            ).select_related('submitted_by').order_by('-created')[:5]
            # 逾期借出
            ctx['overdue_borrows'] = HardwareBorrowRecord.objects.filter(
                status='borrowed',
                expected_return_date__lt=timezone.now(),
            ).select_related('hardware', 'borrower').order_by('expected_return_date')[:5]
            # 最近活动
            from django.db.models import Q as Q2
            ctx['recent_activity'] = MemberOpenRecord.objects.select_related('user').order_by('-created')[:10]
        else:
            ctx['my_pending_tasks'] = Task.objects.filter(
                assigned_to=user,
                status__in=[TaskStatusChoices.PENDING, TaskStatusChoices.IN_PROGRESS],
            ).order_by('-created')[:5]
            ctx['my_recent_checkins'] = CheckInRecord.objects.filter(user=user).order_by('-created')[:3]
            ctx['my_borrowed'] = HardwareBorrowRecord.objects.filter(
                borrower=user, status='borrowed',
            ).select_related('hardware').order_by('-borrow_date')[:5]

        return ctx


# ── 站内通知 ──

class NotificationListView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/notification_list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        notifications = Notification.objects.filter(user=user).order_by('-created')
        ctx['notifications'] = notifications[:50]
        ctx['unread_count'] = notifications.filter(is_read=False).count()
        return ctx


class NotificationMarkReadView(LoginRequiredMixin, View):
    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'ok': True})

    def get(self, request, pk=None):
        # pk=None → 全部已读（来自 /notifications/read-all/）
        if pk is None:
            Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
            return redirect('plugins:lab_manager:notifications')
        notif = Notification.objects.get(pk=pk, user=request.user)
        if not notif.is_read:
            notif.is_read = True
            notif.save(update_fields=['is_read'])
        if notif.link:
            return redirect(notif.link)
        return redirect('plugins:lab_manager:notifications')


# ── 任务日历 ──

class TaskCalendarView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/calendar.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        import calendar
        from datetime import date, timedelta

        today = timezone.localdate()
        year = int(self.request.GET.get('year', today.year))
        month = int(self.request.GET.get('month', today.month))
        # 限制范围
        month = max(1, min(12, month))

        # 该月有 deadline 的任务
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        tasks_with_deadline = Task.objects.filter(
            deadline__date__gte=first_day,
            deadline__date__lte=last_day,
        ).select_related('assigned_to', 'project').order_by('deadline')

        # 按日期分组
        tasks_by_day = {}
        for task in tasks_with_deadline:
            d = task.deadline.date()
            tasks_by_day.setdefault(d, []).append(task)

        # 转为有序列表供模板迭代（Django 模板无法直接 .items 字典）
        tasks_by_day_items = sorted(tasks_by_day.items(), key=lambda x: x[0])

        # 构建日历
        cal = calendar.Calendar(firstweekday=0)
        month_days = cal.monthdayscalendar(year, month)

        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1

        ctx['calendar_year'] = year
        ctx['calendar_month'] = month
        ctx['month_name'] = date(year, month, 1).strftime('%Y年%m月')
        ctx['prev_month'] = f'?year={prev_year}&month={prev_month}'
        ctx['next_month'] = f'?year={next_year}&month={next_month}'
        ctx['month_days'] = month_days
        ctx['tasks_by_day'] = tasks_by_day
        ctx['tasks_by_day_items'] = tasks_by_day_items
        ctx['today'] = today
        ctx['weekday_names'] = ['一', '二', '三', '四', '五', '六', '日']
        return ctx


# ── 成员管理 ──

class MemberListView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/member_list.html'

    def get_context_data(self, **kwargs):
        from collections import defaultdict
        from datetime import timedelta

        ctx = super().get_context_data(**kwargs)
        from users.models import User

        users = User.objects.filter(is_active=True).order_by('username')
        today = timezone.localdate()

        members = []
        for user in users:
            # 任务统计
            assigned = user.assigned_tasks.all()
            task_total = assigned.count()
            task_completed = assigned.filter(status=TaskStatusChoices.COMPLETED).count()
            task_in_progress = assigned.filter(status=TaskStatusChoices.IN_PROGRESS).count()
            task_pending = assigned.filter(status=TaskStatusChoices.PENDING).count()
            task_overdue = assigned.filter(
                status__in=[TaskStatusChoices.PENDING, TaskStatusChoices.IN_PROGRESS],
                deadline__lt=timezone.now(),
            ).count()

            # 借出统计
            borrowed_total = user.borrowed_hardware.count()
            borrowed_current = user.borrowed_hardware.filter(
                status=BorrowStatusChoices.BORROWED,
            ).count()

            # 打卡统计
            checkin_total = user.lab_checkins.count()
            checkin_today = user.lab_checkins.filter(
                created__date=today,
            ).count()

            # 项目统计
            project_count = user.project_memberships.count() + user.led_projects.count()

            # 最近活动
            last_open = user.lab_open_records.order_by('-created').first()
            last_checkin = user.lab_checkins.order_by('-created').first()

            members.append({
                'user': user,
                'task_total': task_total,
                'task_completed': task_completed,
                'task_in_progress': task_in_progress,
                'task_pending': task_pending,
                'task_overdue': task_overdue,
                'completion_rate': round(task_completed / task_total * 100) if task_total > 0 else 0,
                'borrowed_total': borrowed_total,
                'borrowed_current': borrowed_current,
                'checkin_total': checkin_total,
                'checkin_today': checkin_today,
                'project_count': project_count,
                'last_open': last_open,
                'last_checkin': last_checkin,
            })

        ctx['members'] = members
        ctx['total_members'] = len(members)
        return ctx


class MemberDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/member_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from users.models import User

        member = get_object_or_404(User, pk=kwargs['pk'], is_active=True)
        today = timezone.localdate()

        # 任务统计
        assigned = member.assigned_tasks.all()
        task_total = assigned.count()
        task_completed = assigned.filter(status=TaskStatusChoices.COMPLETED).count()
        task_in_progress = assigned.filter(status=TaskStatusChoices.IN_PROGRESS).count()
        task_pending = assigned.filter(status=TaskStatusChoices.PENDING).count()
        task_overdue = assigned.filter(
            status__in=[TaskStatusChoices.PENDING, TaskStatusChoices.IN_PROGRESS],
            deadline__lt=timezone.now(),
        ).count()
        completion_rate = round(task_completed / task_total * 100) if task_total > 0 else 0

        # 最近任务
        recent_tasks = assigned.select_related('created_by', 'project').order_by('-created')[:20]

        # 借出记录
        borrow_records = member.borrowed_hardware.select_related('hardware').order_by('-borrow_date')[:20]
        borrowed_current = member.borrowed_hardware.filter(
            status=BorrowStatusChoices.BORROWED,
        ).count()
        borrowed_overdue = sum(
            1 for r in member.borrowed_hardware.filter(status=BorrowStatusChoices.BORROWED)
            if r.is_overdue
        )

        # 打卡记录
        checkin_total = member.lab_checkins.count()
        checkins = member.lab_checkins.order_by('-created')[:10]

        # 项目
        led_projects = member.led_projects.all()
        member_projects = member.project_memberships.all()

        # 最近活动（页面浏览）
        recent_activity = member.lab_open_records.order_by('-created')[:15]

        # 本周活跃天数
        week_start = today - timedelta(days=today.weekday())
        active_days_this_week = member.lab_checkins.filter(
            created__date__gte=week_start,
        ).dates('created', 'day').count()

        # ── 活动日历：合并打卡 + 页面浏览的日期 ──
        import calendar as cal_mod
        from datetime import date

        cal_year = int(self.request.GET.get('cal_year', today.year))
        cal_month = int(self.request.GET.get('cal_month', today.month))
        cal_month = max(1, min(12, cal_month))

        cal_first = date(cal_year, cal_month, 1)
        cal_last = date(cal_year, cal_month, cal_mod.monthrange(cal_year, cal_month)[1])

        # 查询该月有打卡或页面浏览的日期
        checkin_dates = set(
            member.lab_checkins.filter(
                created__date__gte=cal_first, created__date__lte=cal_last,
            ).dates('created', 'day')
        )
        open_dates = set(
            member.lab_open_records.filter(
                created__date__gte=cal_first, created__date__lte=cal_last,
            ).dates('created', 'day')
        )
        active_dates = checkin_dates | open_dates  # 并集 — 任意一种活动都算

        # 转为 day 数字列表供模板使用（Django 模板 in 不支持 set）
        active_day_nums = sorted({d.day for d in active_dates})
        checkin_day_nums = sorted({d.day for d in checkin_dates})

        cal_obj = cal_mod.Calendar(firstweekday=0)
        cal_weeks = cal_obj.monthdayscalendar(cal_year, cal_month)

        prev_cal_month = cal_month - 1 if cal_month > 1 else 12
        prev_cal_year = cal_year if cal_month > 1 else cal_year - 1
        next_cal_month = cal_month + 1 if cal_month < 12 else 1
        next_cal_year = cal_year if cal_month < 12 else cal_year + 1

        activity_calendar = {
            'year': cal_year,
            'month': cal_month,
            'month_label': cal_first.strftime('%Y年%m月'),
            'weeks': cal_weeks,
            'active_day_nums': active_day_nums,
            'checkin_day_nums': checkin_day_nums,
            'today': today,
            'weekday_names': ['一', '二', '三', '四', '五', '六', '日'],
            'prev_year': prev_cal_year,
            'prev_month': prev_cal_month,
            'next_year': next_cal_year,
            'next_month': next_cal_month,
            'total_active_days': len(active_dates),
            'total_checkin_days': len(checkin_dates),
        }

        ctx.update({
            'member': member,
            'task_total': task_total,
            'task_completed': task_completed,
            'task_in_progress': task_in_progress,
            'task_pending': task_pending,
            'task_overdue': task_overdue,
            'completion_rate': completion_rate,
            'recent_tasks': recent_tasks,
            'borrow_records': borrow_records,
            'borrowed_current': borrowed_current,
            'borrowed_overdue': borrowed_overdue,
            'checkin_total': checkin_total,
            'checkins': checkins,
            'led_projects': led_projects,
            'member_projects': member_projects,
            'recent_activity': recent_activity,
            'active_days_this_week': active_days_this_week,
            'activity_calendar': activity_calendar,
        })
        return ctx


# ── 数据导出 ──

class ExportDataView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/export.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        model = self.request.GET.get('model', 'hardware')
        fmt = self.request.GET.get('format', 'csv')
        ctx['model'] = model
        ctx['format'] = fmt
        return ctx


# ── 智能体助手 ──

class AgentAssistantView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/agent_console.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        conversations = AgentConversation.objects.filter(user=self.request.user).order_by('-last_updated', '-created')
        active_conversation = None
        conversation_pk = self.request.GET.get('conversation')
        start_new = self.request.GET.get('new') == '1'
        if conversation_pk:
            active_conversation = conversations.filter(pk=conversation_pk).first()
        if active_conversation is None and not start_new:
            active_conversation = conversations.first()

        ctx['quick_prompts'] = [
            '现在实验室有哪些 STM32 开发板？',
            '我想做一个智能温室监测系统，看看缺哪些硬件？',
            '帮我找出最近 7 天已完成任务里的视频附件',
            '请帮我解释一下两段式硬件导入应该怎么用',
        ]
        ctx['conversations'] = conversations[:20]
        ctx['active_conversation'] = active_conversation
        ctx['conversation_messages'] = active_conversation.messages.all() if active_conversation else []
        ctx['active_conversation_id'] = active_conversation.pk if active_conversation else ''
        ctx['initial_workflow_alias'] = ''
        return ctx


class AgentChatProxyView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body.decode('utf-8') if request.body else '{}')
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse(
                {'success': False, 'message': '请求体不是合法 JSON'},
                status=400,
            )

        message = str(payload.get('message', '')).strip()
        if not message:
            return JsonResponse(
                {'success': False, 'message': 'message 不能为空'},
                status=400,
            )

        conversation_pk = str(payload.get('conversation_pk', '')).strip()

        conversation = None
        if conversation_pk:
            conversation = AgentConversation.objects.filter(pk=conversation_pk, user=request.user).first()
            if conversation is None:
                return JsonResponse(
                    {'success': False, 'message': '会话不存在或无权限访问'},
                    status=404,
                )

        created_new_conversation = False
        if conversation is None:
            conversation = AgentConversation.objects.create(
                user=request.user,
                title=message[:60],
                mode='backend',
                workflow_alias='',
                coze_conversation_id='',
                last_message_preview=message[:255],
            )
            created_new_conversation = True
        else:
            conversation.last_message_preview = message[:255]
            conversation.save()

        AgentMessage.objects.create(
            conversation=conversation,
            role='user',
            content=message,
            raw_payload={},
        )

        try:
            # LangChain 大模型（DeepSeek）→ 失败降级到本地编排器
            langchain_response = LangChainAgentService().process_message(
                user=request.user,
                message=message,
                conversation=conversation,
            )
            agent_response = langchain_response if langchain_response.handled else AgentToolOrchestrator().process_message(
                user=request.user,
                message=message,
                conversation=conversation,
            )
            if agent_response.handled:
                final_answer = agent_response.answer_text
                AgentMessage.objects.create(
                    conversation=conversation,
                    role='assistant',
                    content=final_answer,
                    raw_payload=agent_response.raw_payload,
                    coze_chat_id='',
                )
                conversation.mode = 'langchain_agent' if agent_response.intent == 'langchain_agent' else 'agent_tools'
                conversation.last_message_preview = final_answer[:255]
                conversation.workflow_alias = ''
                conversation.save()
                return JsonResponse(
                    {
                        'success': True,
                        'mode': conversation.mode,
                        'message': 'ok',
                        'conversation_pk': conversation.pk,
                        'created_new_conversation': created_new_conversation,
                        'intent': agent_response.intent,
                        'answer_text': final_answer,
                        'data': agent_response.data,
                        'raw_payload': agent_response.raw_payload,
                    }
                )

        except Exception as e:
            logger.warning('LangChain/tool orchestrator failed for user %s: %s', request.user.username, e)

        # 最终兜底：本地后端服务
        backend_response = BackendAgentService().process_message(
            user=request.user,
            message=message,
        )
        if backend_response.handled:
            final_answer = backend_response.answer_text
            AgentMessage.objects.create(
                conversation=conversation,
                role='assistant',
                content=final_answer,
                raw_payload=backend_response.raw_payload,
                coze_chat_id='',
            )
            conversation.mode = 'backend'
            conversation.last_message_preview = final_answer[:255]
            conversation.workflow_alias = ''
            conversation.save()
            return JsonResponse(
                {
                    'success': True,
                    'mode': 'backend',
                    'message': 'ok',
                    'conversation_pk': conversation.pk,
                    'created_new_conversation': created_new_conversation,
                    'intent': backend_response.intent,
                    'answer_text': final_answer,
                    'data': backend_response.data,
                    'raw_payload': backend_response.raw_payload,
                }
            )

        return JsonResponse(
            {'success': False, 'message': '智能体代理调用失败'},
            status=500,
        )

    @staticmethod
    def _is_write_operation(message: str) -> bool:
        """检测是否包含任务创建意图。"""
        import re
        return bool(re.search(r'(创建|新建|布置|安排|派发|分配).{0,4}任务', message))


# ── 智能体工具管理 ──

@register_model_view(AgentTool, 'list', path='', detail=False)
class AgentToolListView(generic.ObjectListView):
    queryset = AgentTool.objects.all()
    table = AgentToolTable
    filterset = AgentToolFilterSet
    filterset_form = AgentToolFilterForm

    def has_permission(self):
        return self.request.user.is_superuser


@register_model_view(AgentTool)
class AgentToolView(generic.ObjectView):
    queryset = AgentTool.objects.all()

    def has_permission(self):
        return self.request.user.is_superuser

    def get_extra_context(self, request, instance):
        import json
        return {
            'params_schema_json': json.dumps(instance.parameters_schema, ensure_ascii=False, indent=2),
            'default_args_json': json.dumps(instance.default_args, ensure_ascii=False, indent=2),
        }


@register_model_view(AgentTool, 'add', detail=False)
@register_model_view(AgentTool, 'edit')
class AgentToolEditView(generic.ObjectEditView):
    queryset = AgentTool.objects.all()
    form = AgentToolForm

    def has_permission(self):
        return self.request.user.is_superuser


@register_model_view(AgentTool, 'delete')
class AgentToolDeleteView(generic.ObjectDeleteView):
    queryset = AgentTool.objects.all()

    def has_permission(self):
        return self.request.user.is_superuser


@register_model_view(AgentTool, 'bulk_delete')
class AgentToolBulkDeleteView(generic.BulkDeleteView):
    queryset = AgentTool.objects.all()
    table = AgentToolTable

    def has_permission(self):
        return self.request.user.is_superuser


@register_model_view(AgentTool, 'bulk_edit')
class AgentToolBulkEditView(generic.BulkEditView):
    queryset = AgentTool.objects.all()
    filterset = AgentToolFilterSet
    table = AgentToolTable
    form = AgentToolForm

    def has_permission(self):
        return self.request.user.is_superuser







