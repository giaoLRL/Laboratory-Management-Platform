import csv
import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .logging_config import logger
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView, View
from netbox.views import generic
from utilities.views import register_model_view

from .choices import HardwareApprovalStatusChoices, HardwareStatusChoices, TaskStatusChoices
from .filtersets import (
    AgentToolFilterSet, HardwareBorrowRecordFilterSet, HardwareFilterSet,
    LabProjectFilterSet, TaskFilterSet,
)
from .forms.filtersets import (
    AgentToolFilterForm, HardwareBorrowRecordFilterForm, HardwareFilterForm,
    LabProjectFilterForm, TaskFilterForm,
)
from .forms.model_forms import (
    AgentToolForm, CheckInForm, HardwareBorrowRecordForm,
    HardwareBorrowRecordMemberForm, HardwareForm,
    HardwareMemberForm, LabProjectForm, TaskForm, TaskMemberForm, TaskCommentForm,
)
from .models import (
    AgentConversation, AgentMessage, AgentTool, CheckInRecord, Hardware,
    HardwareBorrowRecord, LabProject, MemberOpenRecord, Notification,
    Task, TaskAttachment, TaskComment,
)
from .models.borrow import BorrowStatusChoices
from users.models import User
from .services import AgentToolOrchestrator, BackendAgentService, LangChainAgentService
from .tables.agent_tool import AgentToolTable
from .tables.borrow import HardwareBorrowRecordTable
from .tables.hardware import HardwareTable
from .tables.project import LabProjectTable
from .tables.task import TaskTable


def _safe_int(value, default, minimum=None, maximum=None):
    """把 GET 参数安全地转成整数并夹取范围；非法输入回退默认值，绝不抛异常。"""
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def _safe_redirect_target(url):
    """只允许站内相对路径，避免开放重定向。"""
    if not url:
        return None
    if url.startswith('/') and not url.startswith('//'):
        return url
    return None

# ── Hardware ──

@register_model_view(Hardware, 'list', path='', detail=False)
class HardwareListView(generic.ObjectListView):
    queryset = Hardware.objects.select_related('custodian', 'submitted_by')
    table = HardwareTable
    filterset = HardwareFilterSet
    filterset_form = HardwareFilterForm
    template_name = 'lab_manager/object_list.html'

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
        # 一次聚合：在借数量（供库存水位条使用，避免逐行查询）
        return qs.annotate(
            outstanding=Count(
                'borrow_records',
                filter=Q(borrow_records__status=BorrowStatusChoices.BORROWED),
            )
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['low_stock'] = list(
            Hardware.objects.filter(minimum_stock__gt=0, quantity__lt=F('minimum_stock'))
            .order_by('quantity')[:5]
        )
        return ctx


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
    template_name = 'lab_manager/object_edit_base.html'

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
            obj = get_object_or_404(Hardware, pk=self.kwargs['pk'])
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
            obj = get_object_or_404(Hardware, pk=self.kwargs['pk'])
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
    template_name = 'lab_manager/object_delete_base.html'

    def has_permission(self):
        return self.request.user.is_superuser


# ── Task ──

@register_model_view(Task, 'list', path='', detail=False)
class TaskListView(generic.ObjectListView):
    queryset = Task.objects.select_related('assigned_to', 'created_by')
    table = TaskTable
    filterset = TaskFilterSet
    filterset_form = TaskFilterForm
    template_name = 'lab_manager/object_list.html'

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
            obj = get_object_or_404(Task, pk=self.kwargs['pk'])
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
            obj = get_object_or_404(Task, pk=self.kwargs['pk'])
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
    template_name = 'lab_manager/object_delete_base.html'

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
    template_name = 'lab_manager/object_list.html'

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

    def get(self, request, *args, **kwargs):
        obj = get_object_or_404(HardwareBorrowRecord, pk=kwargs['pk'])
        if not request.user.is_superuser and request.user != obj.borrower:
            messages.error(request, _('你没有权限查看此借出记录'))
            return redirect('plugins:lab_manager:hardwareborrowrecord_list')
        return super().get(request, *args, **kwargs)

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
    template_name = 'lab_manager/object_edit_base.html'

    def has_permission(self):
        return self.request.user.is_authenticated

    def _resolve_role(self, request):
        # 普通成员用受限表单，不能把借用人改成别人
        self.form = (
            HardwareBorrowRecordForm if request.user.is_superuser
            else HardwareBorrowRecordMemberForm
        )

    def _owner_denied(self, request):
        if 'pk' not in self.kwargs:
            return None
        obj = get_object_or_404(HardwareBorrowRecord, pk=self.kwargs['pk'])
        if not request.user.is_superuser and request.user != obj.borrower:
            messages.error(request, _('你没有权限编辑此借出记录'))
            return redirect('plugins:lab_manager:hardwareborrowrecord_list')
        return None

    def alter_object(self, obj, request, url_args, url_kwargs):
        if not obj.pk:
            obj.borrower = request.user
            obj.status = BorrowStatusChoices.BORROWED
        return obj

    def get(self, request, *args, **kwargs):
        self._resolve_role(request)
        denied = self._owner_denied(request)
        return denied or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self._resolve_role(request)
        denied = self._owner_denied(request)
        return denied or super().post(request, *args, **kwargs)


@register_model_view(HardwareBorrowRecord, 'delete')
class HardwareBorrowRecordDeleteView(generic.ObjectDeleteView):
    queryset = HardwareBorrowRecord.objects.all()
    template_name = 'lab_manager/object_delete_base.html'

    def has_permission(self):
        return self.request.user.is_superuser


# ── 归还硬件 ──

class HardwareBorrowReturnView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/hardwareborrowrecord_return.html'

    def dispatch(self, request, *args, **kwargs):
        record = get_object_or_404(
            HardwareBorrowRecord.objects.select_related('hardware', 'borrower'),
            pk=self.kwargs['pk'],
        )
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
        record = get_object_or_404(HardwareBorrowRecord, pk=pk)
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
    template_name = 'lab_manager/object_list.html'

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
    template_name = 'lab_manager/object_edit_base.html'

    def has_permission(self):
        return self.request.user.is_authenticated


@register_model_view(LabProject, 'delete')
class LabProjectDeleteView(generic.ObjectDeleteView):
    queryset = LabProject.objects.all()
    template_name = 'lab_manager/object_delete_base.html'

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


# 打卡防重复提交时间窗（秒）
CHECKIN_DEDUPE_SECONDS = 60

# 统一分页配置
PAGE_SIZE_CHOICES = (25, 50, 100, 200)
DEFAULT_PAGE_SIZE = 50


def csv_response(filename, headers, rows):
    """统一的 CSV 下载响应（带 BOM，Excel 可直接打开）。"""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return response


def filter_checkins(request, queryset):
    """打卡记录的公共筛选（列表与导出共用）。"""
    if not request.user.is_superuser:
        queryset = queryset.filter(user=request.user)
    username = (request.GET.get('username') or '').strip()
    keyword = (request.GET.get('q') or '').strip()
    date_from = (request.GET.get('date_from') or '').strip()
    date_to = (request.GET.get('date_to') or '').strip()
    if username:
        queryset = queryset.filter(
            Q(user__username__icontains=username) | Q(user__first_name__icontains=username)
            | Q(user__last_name__icontains=username) | Q(user__email__icontains=username)
        )
    if keyword:
        queryset = queryset.filter(Q(address__icontains=keyword) | Q(note__icontains=keyword))
    if date_from:
        queryset = queryset.filter(created__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created__date__lte=date_to)
    return queryset


def filter_member_open_records(request, queryset):
    """浏览记录的公共筛选（列表与导出共用）。"""
    username = (request.GET.get('username') or '').strip()
    target_type = (request.GET.get('target_type') or '').strip()
    keyword = (request.GET.get('q') or '').strip()
    date_from = (request.GET.get('date_from') or '').strip()
    date_to = (request.GET.get('date_to') or '').strip()
    if username:
        queryset = queryset.filter(
            Q(user__username__icontains=username) | Q(user__first_name__icontains=username)
            | Q(user__last_name__icontains=username) | Q(user__email__icontains=username)
        )
    if target_type:
        queryset = queryset.filter(target_type=target_type)
    if keyword:
        queryset = queryset.filter(Q(path__icontains=keyword) | Q(page_title__icontains=keyword))
    if date_from:
        queryset = queryset.filter(created__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created__date__lte=date_to)
    return queryset


def build_page(request, queryset, default_size=DEFAULT_PAGE_SIZE):
    """统一的列表分页：?page=&per_page=（页大小限定在 PAGE_SIZE_CHOICES 内）。"""
    from django.core.paginator import Paginator
    try:
        per_page = int(request.GET.get('per_page', default_size))
    except (TypeError, ValueError):
        per_page = default_size
    if per_page not in PAGE_SIZE_CHOICES:
        per_page = default_size
    return Paginator(queryset, per_page).get_page(request.GET.get('page'))


def add_pagination(ctx, request, queryset, default_size=DEFAULT_PAGE_SIZE):
    """把分页对象与页大小选项塞进上下文，返回 page_obj。"""
    page_obj = build_page(request, queryset, default_size)
    ctx['page_obj'] = page_obj
    ctx['per_page'] = page_obj.paginator.per_page
    ctx['per_page_choices'] = PAGE_SIZE_CHOICES
    return page_obj


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

    def get(self, request, *args, **kwargs):
        if request.GET.get('export') == 'csv':
            records = filter_member_open_records(
                request, MemberOpenRecord.objects.select_related('user').order_by('-created')
            )[:5000]
            return csv_response(
                'lab_member_open_records.csv',
                ['时间', '成员', '对象类型', '页面', '路径', 'IP', '纬度', '经度'],
                records.values_list('created', 'user__username', 'target_type', 'page_title',
                                    'path', 'ip_address', 'latitude', 'longitude'),
            )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        records = filter_member_open_records(
            self.request, MemberOpenRecord.objects.select_related('user').order_by('-created')
        )
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
        keyword = (self.request.GET.get('q') or '').strip()
        date_from = (self.request.GET.get('date_from') or '').strip()
        date_to = (self.request.GET.get('date_to') or '').strip()
        if keyword:
            records = records.filter(Q(path__icontains=keyword) | Q(page_title__icontains=keyword))
        if date_from:
            records = records.filter(created__date__gte=date_from)
        if date_to:
            records = records.filter(created__date__lte=date_to)
        page_obj = add_pagination(ctx, self.request, records, default_size=25)
        ctx['records'] = page_obj.object_list
        ctx['username'] = username or ''
        ctx['target_type'] = target_type or ''
        ctx['filter_q'] = keyword
        ctx['filter_date_from'] = date_from
        ctx['filter_date_to'] = date_to
        ctx['filtered_count'] = page_obj.paginator.count

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
        # 打卡数直接以 CheckInRecord 为准（MemberOpenRecord 记录的是页面浏览行为，
        # 浏览打卡详情页也曾被计入打卡数，导致统计虚高）
        ctx['today_checkins'] = CheckInRecord.objects.filter(created__gte=today_start).count()

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
        self.record = get_object_or_404(
            MemberOpenRecord.objects.select_related('user'), pk=self.kwargs['pk']
        )
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
        # 防重复提交：时间窗内已有打卡记录则忽略本次提交（连点/刷新不会产生重复打卡）
        if CheckInRecord.objects.filter(
            user=request.user,
            created__gte=timezone.now() - timedelta(seconds=CHECKIN_DEDUPE_SECONDS),
        ).exists():
            messages.warning(request, _('刚刚已完成打卡，请勿重复提交'))
            return redirect('plugins:lab_manager:checkin_list')
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
        if request.GET.get('export') == 'csv':
            records = filter_checkins(
                request, CheckInRecord.objects.select_related('user').order_by('-created')
            )[:5000]
            return csv_response(
                'lab_checkins.csv',
                ['时间', '成员', '纬度', '经度', '精度', '地址备注', '备注', '照片'],
                records.values_list('created', 'user__username', 'latitude', 'longitude',
                                    'accuracy', 'address', 'note', 'photo'),
            )
        record_member_open(request, page_title='打卡记录', target_type='checkin_list')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        request = self.request
        records = filter_checkins(
            request, CheckInRecord.objects.select_related('user').order_by('-created')
        )
        page_obj = add_pagination(ctx, request, records, default_size=25)
        ctx['records'] = page_obj.object_list
        ctx['is_superuser'] = request.user.is_superuser
        ctx['filter_username'] = (request.GET.get('username') or '').strip()
        ctx['filter_q'] = (request.GET.get('q') or '').strip()
        ctx['filter_date_from'] = (request.GET.get('date_from') or '').strip()
        ctx['filter_date_to'] = (request.GET.get('date_to') or '').strip()
        ctx['filtered_count'] = page_obj.paginator.count
        ctx['checkin_create_url'] = reverse('plugins:lab_manager:checkin_create')
        return ctx


class CheckInDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/checkin_detail.html'

    def dispatch(self, request, *args, **kwargs):
        record = get_object_or_404(
            CheckInRecord.objects.select_related('user'), pk=self.kwargs['pk']
        )
        if not request.user.is_superuser and record.user != request.user:
            messages.error(request, _('你没有权限查看此打卡记录'))
            return redirect('plugins:lab_manager:checkin_list')
        self.record = record
        record_member_open(request, page_title='打卡详情', target_type='checkin_detail', target_id=record.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['record'] = self.record
        return ctx


# ── 上传附件 ──

class TaskUploadAttachmentView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/task_upload.html'

    def dispatch(self, request, *args, **kwargs):
        task = get_object_or_404(Task, pk=self.kwargs['pk'])
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
        ctx['task'] = get_object_or_404(Task, pk=self.kwargs['pk'])
        return ctx

    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
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
            hw = get_object_or_404(Hardware, pk=self.kwargs['pk'])
            messages.error(request, _('你没有权限审核硬件'))
            return redirect(hw.get_absolute_url())
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['hardware'] = get_object_or_404(Hardware, pk=self.kwargs['pk'])
        return ctx

    def post(self, request, pk):
        if not request.user.is_superuser:
            hw = get_object_or_404(Hardware, pk=pk)
            messages.error(request, _('你没有权限审核硬件'))
            return redirect(hw.get_absolute_url())

        hw = get_object_or_404(Hardware, pk=pk)
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
            task = get_object_or_404(Task, pk=self.kwargs['pk'])
            messages.error(request, _('你没有权限操作此任务'))
            return redirect(task.get_absolute_url())
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['task'] = get_object_or_404(Task, pk=self.kwargs['pk'])
        return ctx

    def post(self, request, pk):
        if not request.user.is_superuser:
            task = get_object_or_404(Task, pk=pk)
            messages.error(request, _('你没有权限操作此任务'))
            return redirect(task.get_absolute_url())
        task = get_object_or_404(Task, pk=pk)
        task.completion_note = request.POST.get('completion_note', '')
        from .services.task_utils import mark_task_completed
        mark_task_completed(task)
        messages.success(request, _('任务已标记为完成'))
        return redirect('plugins:lab_manager:task', pk=task.pk)


# ── 评论 ──

class TaskCommentView(LoginRequiredMixin, View):
    """提交评论 — 所有人可评论（仅接受 POST）"""

    http_method_names = ['post', 'head', 'options']

    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        form = TaskCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.task = task
            comment.user = request.user
            comment.save()
            form.save_m2m()
            messages.success(request, _('评论已发布'))
        else:
            messages.error(request, _('评论内容不能为空'))
        return redirect('plugins:lab_manager:task', pk=task.pk)


# ── 删除附件 ──

class TaskAttachmentDeleteView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/task_attachment_delete.html'

    def dispatch(self, request, *args, **kwargs):
        att = get_object_or_404(TaskAttachment, pk=self.kwargs['pk'])
        if not request.user.is_superuser and request.user != att.task.assigned_to and request.user != att.task.created_by:
            messages.error(request, _('你没有权限删除此附件'))
            return redirect(att.task.get_absolute_url())
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['attachment'] = get_object_or_404(TaskAttachment, pk=self.kwargs['pk'])
        return ctx

    def post(self, request, pk):
        att = get_object_or_404(TaskAttachment, pk=pk)
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


# ── 界面增强：指挥舱（投屏大屏）+ 设计系统 ──────────────────────

class MissionControlView(LoginRequiredMixin, TemplateView):
    """指挥舱：一屏 KPI + 待办队列 + 库存水位 + 实时事件流 + 考勤热力图。"""

    template_name = 'lab_manager/mission_control.html'

    def get_context_data(self, **kwargs):
        from django.db.models.functions import TruncDate

        ctx = super().get_context_data(**kwargs)
        request = self.request
        now = timezone.now()
        today = timezone.localdate()

        tasks = Task.objects.all() if request.user.is_superuser else Task.objects.filter(
            Q(assigned_to=request.user) | Q(created_by=request.user)
        )
        hardware = Hardware.objects.all()
        if not request.user.is_superuser:
            hardware = hardware.filter(
                Q(approval_status=HardwareApprovalStatusChoices.APPROVED) | Q(submitted_by=request.user)
            )

        ctx['kpis'] = [
            {'label': _('硬件总数'), 'value': hardware.count(), 'hint': _('含待审批')},
            {'label': _('在用硬件'), 'value': hardware.filter(status=HardwareStatusChoices.IN_USE).count(),
             'hint': _('状态=在用'), 'tone': 'ok'},
            {'label': _('进行中任务'), 'value': tasks.filter(status=TaskStatusChoices.IN_PROGRESS).count(),
             'hint': f"{tasks.filter(status=TaskStatusChoices.PENDING).count()} " + str(_('待开始'))},
            {'label': _('今日打卡'), 'value': CheckInRecord.objects.filter(created__date=today).count(),
             'hint': _('今天'), 'tone': 'warning'},
        ]

        pending_hw = hardware.filter(approval_status=HardwareApprovalStatusChoices.PENDING)[:5]
        overdue_tasks = tasks.filter(
            status__in=[TaskStatusChoices.PENDING, TaskStatusChoices.IN_PROGRESS], deadline__lt=now
        )[:5]
        overdue_borrows = HardwareBorrowRecord.objects.filter(
            status=BorrowStatusChoices.BORROWED, expected_return_date__lt=now
        ).select_related('hardware', 'borrower')[:5]
        low_stock = hardware.filter(minimum_stock__gt=0, quantity__lt=F('minimum_stock'))[:5]
        ctx['todos'] = {
            'pending_hardware': list(pending_hw),
            'overdue_tasks': list(overdue_tasks),
            'overdue_borrows': list(overdue_borrows),
            'low_stock': list(low_stock),
        }

        # 实时事件流：浏览记录 + 通知 + 打卡合并
        stream = []
        for rec in MemberOpenRecord.objects.select_related('user').order_by('-created')[:20]:
            stream.append({'time': rec.created, 'icon': 'mdi-history',
                           'text': f'{rec.user} · {rec.page_title or rec.path}'})
        for ck in CheckInRecord.objects.select_related('user').order_by('-created')[:10]:
            stream.append({'time': ck.created, 'icon': 'mdi-map-marker-check-outline',
                           'text': f'{ck.user} · {_("完成打卡")} {ck.address or ""}'.strip()})
        for nf in Notification.objects.select_related('user').order_by('-created')[:10]:
            stream.append({'time': nf.created, 'icon': 'mdi-bell-outline', 'text': f'{nf.user} · {nf.title}'})
        stream.sort(key=lambda x: x['time'], reverse=True)
        ctx['stream'] = stream[:24]

        # 库存水位（按类别聚合）
        ctx['waterlines'] = list(
            hardware.values('category').annotate(
                available=Sum('quantity'), minimum=Sum('minimum_stock'), items=Count('id')
            ).order_by('category')[:8]
        )

        # 近 26 周考勤热力图
        start = today - timedelta(days=today.weekday() + 7 * 25)
        counts = {
            row['d']: row['n']
            for row in CheckInRecord.objects.filter(created__date__gte=start)
            .annotate(d=TruncDate('created')).values('d').annotate(n=Count('id'))
        }
        weeks, day = [], start
        while day <= today:
            week = []
            for _i in range(7):
                n = counts.get(day, 0)
                level = 0 if n == 0 else (1 if n == 1 else 2 if n == 2 else 3 if n < 5 else 4)
                week.append({'date': day, 'count': n, 'level': level,
                             'future': day > today})
                day += timedelta(days=1)
            weeks.append(week)
        ctx['heatmap_weeks'] = weeks
        ctx['heatmap_total'] = sum(counts.values())

        # 近 30 天趋势（任务完成 / 打卡 / 借出），服务端算好折线点
        days = [today - timedelta(days=i) for i in range(29, -1, -1)]
        def series(queryset, date_field):
            rows = (queryset.filter(**{f'{date_field}__date__gte': days[0]})
                    .annotate(d=TruncDate(date_field)).values('d').annotate(n=Count('id')))
            mapping = {r['d']: r['n'] for r in rows}
            return [mapping.get(d, 0) for d in days]

        raw = {
            '任务完成': series(Task.objects.filter(completed_at__isnull=False), 'completed_at'),
            '打卡': series(CheckInRecord.objects.all(), 'created'),
            '借出': series(HardwareBorrowRecord.objects.all(), 'borrow_date'),
        }
        chart_w, chart_h = 600, 120
        peak = max([1] + [v for s in raw.values() for v in s])
        chart = []
        for idx, (label, values) in enumerate(raw.items()):
            points = ' '.join(
                f'{(i / (len(values) - 1)) * chart_w:.1f},{chart_h - (v / peak) * (chart_h - 8):.1f}'
                for i, v in enumerate(values)
            )
            chart.append({'label': label, 'points': points, 'total': sum(values),
                          'color': ['var(--lm-accent)', 'var(--lm-ok)', 'var(--lm-warning)'][idx % 3]})
        ctx['trend'] = {'chart_w': chart_w, 'chart_h': chart_h, 'peak': peak,
                        'series': chart, 'start': days[0], 'end': days[-1]}
        return ctx


class DesignSystemView(LoginRequiredMixin, TemplateView):
    """设计系统展示页：令牌与组件示例（团队设计资产单一来源）。"""

    template_name = 'lab_manager/design_system.html'


# ── 界面增强：命令面板索引 / 任务看板 ──────────────────────────

class CommandIndexView(LoginRequiredMixin, View):
    """命令面板索引：导航 + 常用操作 + 少量动态对象（按需加载，不进入页面渲染）。"""

    http_method_names = ['get']

    def get(self, request):
        def nav(label, url_name, icon, group, keywords=''):
            try:
                return {'label': label, 'url': reverse(f'plugins:lab_manager:{url_name}'),
                        'icon': icon, 'group': group, 'keywords': keywords, 'action': 'goto'}
            except NoReverseMatch:
                return None

        items = [x for x in [
            nav('仪表板', 'home', 'mdi-view-dashboard-outline', '导航', 'home dashboard 首页'),
            nav('硬件列表', 'hardware_list', 'mdi-cube-outline', '导航', 'hardware 设备'),
            nav('任务列表', 'task_list', 'mdi-clipboard-text-outline', '导航', 'tasks 待办'),
            nav('任务看板', 'task_board', 'mdi-view-column-outline', '导航', 'kanban 看板'),
            nav('我的任务', 'my_tasks', 'mdi-account-check-outline', '导航', 'my tasks'),
            nav('借出记录', 'hardwareborrowrecord_list', 'mdi-swap-horizontal', '导航', 'borrow 借出'),
            nav('实验项目', 'labproject_list', 'mdi-flask-outline', '导航', 'project'),
            nav('打卡记录', 'checkin_list', 'mdi-map-marker-check-outline', '导航', 'checkin 签到'),
            nav('成员列表', 'member_list', 'mdi-account-group-outline', '导航', 'members'),
            nav('任务日历', 'calendar', 'mdi-calendar-month-outline', '导航', 'calendar'),
            nav('浏览记录', 'member_open_records', 'mdi-history', '导航', 'audit 审计'),
            nav('通知中心', 'notifications', 'mdi-bell-outline', '导航', 'notifications'),
            nav('智能体控制台', 'agent_console', 'mdi-robot-happy-outline', '导航', 'agent ai'),
            nav('指挥舱', 'mission_control', 'mdi-monitor-dashboard', '导航', 'mission control 大屏'),
            nav('数据导出', 'export_data', 'mdi-download-outline', '导航', 'export csv'),
            nav('设计系统', 'design_system', 'mdi-palette-outline', '导航', 'design tokens 组件'),
            nav('新增硬件', 'hardware_add', 'mdi-plus-thick', '操作', 'add hardware 提交'),
            nav('新增任务', 'task_add', 'mdi-plus-thick', '操作', 'add task 派发'),
            nav('登记借出', 'hardwareborrowrecord_add', 'mdi-plus-thick', '操作', 'borrow 借出'),
            nav('新增项目', 'labproject_add', 'mdi-plus-thick', '操作', 'project'),
            nav('拍照打卡', 'checkin_create', 'mdi-camera', '操作', 'checkin 打卡'),
            nav('发送通知', 'notification_send', 'mdi-send', '操作', 'notify'),
        ] if x]

        if request.user.is_superuser:
            for hw in Hardware.objects.order_by('name')[:40]:
                items.append({'label': hw.name, 'url': hw.get_absolute_url(), 'icon': 'mdi-cube-outline',
                              'group': '硬件', 'keywords': f'{hw.category} {hw.model_number} 硬件',
                              'action': 'goto'})
            for task in Task.objects.select_related('assigned_to').order_by('-created')[:30]:
                items.append({'label': task.title, 'url': task.get_absolute_url(),
                              'icon': 'mdi-clipboard-text-outline', 'group': '任务',
                              'keywords': f'{task.status} {getattr(task.assigned_to, "username", "")}',
                              'action': 'goto'})
        else:
            for task in Task.objects.filter(assigned_to=request.user).order_by('-created')[:30]:
                items.append({'label': task.title, 'url': task.get_absolute_url(),
                              'icon': 'mdi-clipboard-text-outline', 'group': '我的任务',
                              'keywords': task.status, 'action': 'goto'})

        return JsonResponse({'items': items})


@method_decorator(require_POST, name='dispatch')
class TaskStatusUpdateView(LoginRequiredMixin, View):
    """看板拖拽改状态（JSON）。"""

    def post(self, request):
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse({'ok': False, 'error': '请求体不是合法 JSON'}, status=400)
        pk = payload.get('pk')
        status = str(payload.get('status') or '').strip()
        if status not in {c[0] for c in Task._meta.get_field('status').choices}:
            return JsonResponse({'ok': False, 'error': 'status 不合法'}, status=400)
        task = get_object_or_404(Task, pk=pk)
        if not (request.user.is_superuser or request.user in (task.created_by, task.assigned_to)):
            return JsonResponse({'ok': False, 'error': '无权修改该任务'}, status=403)
        task.status = status
        if status == TaskStatusChoices.COMPLETED:
            task.completed_at = timezone.now()
        else:
            task.completed_at = None
        task.save(update_fields=['status', 'completed_at', 'last_updated'])
        return JsonResponse({'ok': True, 'status': task.status})


class TaskBoardView(LoginRequiredMixin, TemplateView):
    """任务看板：按状态三列，可拖拽流转。"""

    template_name = 'lab_manager/task_board.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        request = self.request
        tasks = Task.objects.select_related('assigned_to', 'created_by', 'project')
        if not request.user.is_superuser:
            tasks = tasks.filter(Q(assigned_to=request.user) | Q(created_by=request.user))
        tasks = tasks.order_by('deadline', '-created')
        now = timezone.now()
        columns = []
        for value, label in Task._meta.get_field('status').choices:
            rows = [t for t in tasks if t.status == value]
            columns.append({
                'value': value, 'label': label, 'tasks': rows, 'count': len(rows),
                'overdue': sum(1 for t in rows if t.deadline and t.deadline < now and value != TaskStatusChoices.COMPLETED),
            })
        ctx['columns'] = columns
        ctx['now'] = now
        return ctx


# ── 站内通知 ──

class NotificationListView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/notification_list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        notifications = Notification.objects.filter(user=user).order_by('-created')
        ctx['unread_count'] = notifications.filter(is_read=False).count()
        page_obj = add_pagination(ctx, self.request, notifications)
        ctx['notifications'] = page_obj.object_list
        return ctx


class NotificationMarkReadView(LoginRequiredMixin, View):
    """标记通知已读。

    - POST /notifications/read-all/ → 全部已读（不接受 GET，避免被 <img> 之类触发状态变更）
    - POST /notifications/<pk>/read/ → 单条已读
    - GET  /notifications/<pk>/read/ → 单条已读并跳转（纯导航，只影响本人的已读标记）
    """

    def post(self, request, pk=None):
        if pk is None:
            Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': True})
            messages.success(request, _('已全部标为已读'))
            return redirect('plugins:lab_manager:notifications')
        return self._mark_single(request, pk)

    def get(self, request, pk=None):
        if pk is None:
            return HttpResponseNotAllowed(['POST'])
        return self._mark_single(request, pk)

    def _mark_single(self, request, pk):
        notif = get_object_or_404(Notification, pk=pk, user=request.user)
        if not notif.is_read:
            notif.is_read = True
            notif.save(update_fields=['is_read'])
        return redirect(_safe_redirect_target(notif.link) or 'plugins:lab_manager:notifications')

class AgentConversationDeleteView(LoginRequiredMixin, View):
    """删除本人的智能体会话（连同消息）。仅 POST。"""

    http_method_names = ['post']

    def post(self, request, pk):
        conversation = get_object_or_404(AgentConversation, pk=pk, user=request.user)
        conversation.delete()
        return JsonResponse({'ok': True})


class NotificationSendView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/notification_send.html'

    def has_permission(self, request):
        return request.user.is_superuser

    def dispatch(self, request, *args, **kwargs):
        if not self.has_permission(request):
            messages.error(request, _('仅管理员可发送通知'))
            return redirect('plugins:lab_manager:notifications')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['users'] = User.objects.filter(is_active=True).order_by('username')
        return ctx

    def post(self, request):
        title = request.POST.get('title', '').strip()
        message = request.POST.get('message', '').strip()
        link = request.POST.get('link', '').strip()
        ntype = request.POST.get('notification_type', 'system')
        target = request.POST.get('target', 'all')  # all or specific user

        if not title:
            messages.error(request, _('请输入通知标题'))
            return redirect('plugins:lab_manager:notification_send')

        if target == 'all':
            users = User.objects.filter(is_active=True)
            count = 0
            for user in users:
                Notification.objects.create(
                    user=user, title=title, message=message,
                    link=link, notification_type=ntype
                )
                count += 1
            messages.success(request, _(f'已向 {count} 位用户发送通知'))
        else:
            user_id = request.POST.get('user_id')
            if user_id:
                try:
                    user = User.objects.get(pk=user_id, is_active=True)
                    Notification.objects.create(
                        user=user, title=title, message=message,
                        link=link, notification_type=ntype
                    )
                    messages.success(request, _(f'已向 {user.username} 发送通知'))
                except User.DoesNotExist:
                    messages.error(request, _('用户不存在'))

        return redirect('plugins:lab_manager:notifications')



# ── 任务日历 ──

class TaskCalendarView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/calendar.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        import calendar
        from datetime import date, timedelta

        today = timezone.localdate()
        year = _safe_int(self.request.GET.get('year'), today.year, minimum=1970, maximum=2999)
        month = _safe_int(self.request.GET.get('month'), today.month, minimum=1, maximum=12)

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

        page_obj = add_pagination(
            ctx, self.request, User.objects.filter(is_active=True).order_by('username')
        )
        ctx['members_page'] = page_obj
        users = list(page_obj.object_list)
        user_ids = [u.pk for u in users]
        today = timezone.localdate()
        now = timezone.now()

        def counts(queryset, key, **filters):
            return {
                row[key]: row['n']
                for row in queryset.filter(**filters).values(key).annotate(n=Count('pk'))
            }

        assigned_qs = Task.objects.filter(assigned_to_id__in=user_ids)
        task_total_map = counts(assigned_qs, 'assigned_to_id')
        task_completed_map = counts(assigned_qs, 'assigned_to_id', status=TaskStatusChoices.COMPLETED)
        task_progress_map = counts(assigned_qs, 'assigned_to_id', status=TaskStatusChoices.IN_PROGRESS)
        task_pending_map = counts(assigned_qs, 'assigned_to_id', status=TaskStatusChoices.PENDING)
        task_overdue_map = counts(
            assigned_qs, 'assigned_to_id',
            status__in=[TaskStatusChoices.PENDING, TaskStatusChoices.IN_PROGRESS], deadline__lt=now,
        )
        borrow_qs = HardwareBorrowRecord.objects.filter(borrower_id__in=user_ids)
        borrowed_total_map = counts(borrow_qs, 'borrower_id')
        borrowed_current_map = counts(borrow_qs, 'borrower_id', status=BorrowStatusChoices.BORROWED)
        checkin_qs = CheckInRecord.objects.filter(user_id__in=user_ids)
        checkin_total_map = counts(checkin_qs, 'user_id')
        checkin_today_map = counts(checkin_qs, 'user_id', created__date=today)
        member_projects = counts(LabProject.objects.filter(members__in=user_ids), 'members')
        led_projects = counts(LabProject.objects.filter(leader_id__in=user_ids), 'leader_id')
        last_open_map = dict(
            MemberOpenRecord.objects.filter(user_id__in=user_ids)
            .order_by('user_id', '-created').distinct('user_id')
            .values_list('user_id', 'created')
        )
        last_checkin_map = dict(
            CheckInRecord.objects.filter(user_id__in=user_ids)
            .order_by('user_id', '-created').distinct('user_id')
            .values_list('user_id', 'created')
        )

        members = []
        for user in users:
            uid = user.pk
            task_total = task_total_map.get(uid, 0)
            task_completed = task_completed_map.get(uid, 0)
            task_in_progress = task_progress_map.get(uid, 0)
            task_pending = task_pending_map.get(uid, 0)
            task_overdue = task_overdue_map.get(uid, 0)
            borrowed_total = borrowed_total_map.get(uid, 0)
            borrowed_current = borrowed_current_map.get(uid, 0)
            checkin_total = checkin_total_map.get(uid, 0)
            checkin_today = checkin_today_map.get(uid, 0)
            project_count = member_projects.get(uid, 0) + led_projects.get(uid, 0)
            last_open = last_open_map.get(uid)
            last_checkin = last_checkin_map.get(uid)

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
        ctx['total_members'] = page_obj.paginator.count
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

        cal_year = _safe_int(self.request.GET.get('cal_year'), today.year, minimum=1970, maximum=2999)
        cal_month = _safe_int(self.request.GET.get('cal_month'), today.month, minimum=1, maximum=12)
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
        page_obj = add_pagination(ctx, self.request, conversations, default_size=25)
        ctx['conversations'] = page_obj.object_list
        ctx['active_conversation'] = active_conversation
        # 长会话只加载最近 200 条，避免整表加载与渲染
        if active_conversation:
            recent_messages = list(active_conversation.messages.order_by('-created')[:200])
            recent_messages.reverse()
        else:
            recent_messages = []
        ctx['conversation_messages'] = recent_messages
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
    template_name = 'lab_manager/object_list.html'

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
    template_name = 'lab_manager/object_edit_base.html'

    def has_permission(self):
        return self.request.user.is_superuser


@register_model_view(AgentTool, 'delete')
class AgentToolDeleteView(generic.ObjectDeleteView):
    queryset = AgentTool.objects.all()
    template_name = 'lab_manager/object_delete_base.html'

    def has_permission(self):
        return self.request.user.is_superuser


@register_model_view(AgentTool, 'bulk_delete', path='bulk-delete', detail=False)
class AgentToolBulkDeleteView(generic.BulkDeleteView):
    queryset = AgentTool.objects.all()
    table = AgentToolTable
    template_name = 'lab_manager/object_delete_base.html'

    def has_permission(self):
        return self.request.user.is_superuser


@register_model_view(AgentTool, 'bulk_edit', path='bulk-edit', detail=False)
class AgentToolBulkEditView(generic.BulkEditView):
    queryset = AgentTool.objects.all()
    filterset = AgentToolFilterSet
    table = AgentToolTable
    form = AgentToolForm
    template_name = 'lab_manager/object_edit_base.html'

    def has_permission(self):
        return self.request.user.is_superuser







