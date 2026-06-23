import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import connection
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView, View
from netbox.views import generic
from utilities.views import register_model_view

from .choices import HardwareApprovalStatusChoices, TaskStatusChoices
from .filtersets import HardwareFilterSet, TaskFilterSet
from .forms.filtersets import HardwareFilterForm, TaskFilterForm
from .forms.model_forms import CheckInForm, HardwareForm, HardwareMemberForm, TaskForm, TaskMemberForm, TaskCommentForm
from .models import AgentConversation, AgentMessage, CheckInRecord, Hardware, MemberOpenRecord, Task, TaskAttachment, TaskComment
from .services import AgentToolOrchestrator, BackendAgentService, LangChainAgentService
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
            ctx['checkin_today'] = CheckInRecord.objects.filter(created__date=timezone.localdate()).count()
        else:
            ctx['my_pending_tasks'] = Task.objects.filter(
                assigned_to=user,
                status__in=[TaskStatusChoices.PENDING, TaskStatusChoices.IN_PROGRESS],
            ).order_by('-created')[:5]
            ctx['my_recent_checkins'] = CheckInRecord.objects.filter(user=user).order_by('-created')[:3]

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


@method_decorator(csrf_exempt, name='dispatch')
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

        except Exception:
            pass

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







