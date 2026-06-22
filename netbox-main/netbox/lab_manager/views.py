import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
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
from .forms.model_forms import HardwareForm, HardwareMemberForm, TaskForm, TaskMemberForm, TaskCommentForm
from .models import AgentConversation, AgentMessage, Hardware, Task, TaskAttachment, TaskComment
from .services import BackendAgentService, CozeGateway, CozeGatewayConfigError, CozeGatewayRequestError
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


# ── 智能体助手 ──

class AgentAssistantView(LoginRequiredMixin, TemplateView):
    template_name = 'lab_manager/agent_console.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        conversations = AgentConversation.objects.filter(user=self.request.user).order_by('-last_updated', '-created')
        active_conversation = None
        conversation_pk = self.request.GET.get('conversation')
        if conversation_pk:
            active_conversation = conversations.filter(pk=conversation_pk).first()
        if active_conversation is None:
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
        ctx['active_coze_conversation_id'] = active_conversation.coze_conversation_id if active_conversation else ''
        # 方案 B 默认走本地后端，不再自动回填历史工作流别名，避免旧会话持续命中外部工作流。
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

        workflow_alias = str(payload.get('workflow_alias', '')).strip()
        conversation_id = str(payload.get('conversation_id', '')).strip() or None
        conversation_pk = str(payload.get('conversation_pk', '')).strip()
        force_external = bool(payload.get('force_external'))

        conversation = None
        if conversation_pk:
            conversation = AgentConversation.objects.filter(pk=conversation_pk, user=request.user).first()
            if conversation is None:
                return JsonResponse(
                    {'success': False, 'message': '会话不存在或无权限访问'},
                    status=404,
                )

        if conversation is None and conversation_id:
            conversation = AgentConversation.objects.filter(
                user=request.user,
                coze_conversation_id=conversation_id,
            ).first()

        created_new_conversation = False
        if conversation is None:
            conversation = AgentConversation.objects.create(
                user=request.user,
                title=message[:60],
                mode='workflow' if workflow_alias else ('chat' if force_external else 'backend'),
                workflow_alias=workflow_alias,
                coze_conversation_id=conversation_id or '',
                last_message_preview=message[:255],
            )
            created_new_conversation = True
        else:
            conversation.mode = 'workflow' if workflow_alias else ('chat' if force_external else 'backend')
            if workflow_alias:
                conversation.workflow_alias = workflow_alias
            conversation.last_message_preview = message[:255]
            if conversation_id and not conversation.coze_conversation_id:
                conversation.coze_conversation_id = conversation_id
            conversation.save()

        AgentMessage.objects.create(
            conversation=conversation,
            role='user',
            content=message,
            raw_payload={},
        )

        try:
            if not workflow_alias and not force_external:
                backend_response = BackendAgentService().process_message(
                    user=request.user,
                    message=message,
                )
                if backend_response.handled:
                    final_answer = backend_response.answer_text
                    
                    # === 尝试调用外部工作流，让其基于本地真实数据做二次润色 ===
                    gateway = CozeGateway()
                    if gateway.has_site_workflow():
                        try:
                            # 提取本地查询到的结构化数据转为文本，或者直接传完整回答作为参考
                            # 如果有具体数据，就传 data 里的，如果没有，就传拼接好的 text
                            if backend_response.data:
                                hardware_items_str = json.dumps(backend_response.data, ensure_ascii=False)
                            else:
                                hardware_items_str = backend_response.answer_text

                            parameters = {
                                'user_query': message,
                                'hardware_items_str': hardware_items_str,
                                'intent': backend_response.intent,
                            }
                            
                            workflow_response = gateway.run_workflow(
                                workflow_alias='site_workflow',
                                parameters=parameters,
                                user_id=str(request.user.pk),
                            )
                            workflow_data = workflow_response.payload.get('data')
                            
                            # 只有当工作流真正返回了有意义的字符串内容，才替换掉本地的 Markdown
                            if isinstance(workflow_data, str) and len(workflow_data.strip()) > 5:
                                final_answer = workflow_data.strip()
                        except Exception as e:
                            # 如果请求工作流超时、报错，静默失败，保留使用本地高质量 Markdown
                            print(f"[Agent] Workflow fallback failed: {e}")
                    
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

            gateway = CozeGateway()
            if not workflow_alias and gateway.has_site_workflow() and not gateway.has_chat_bot():
                workflow_alias = 'site_workflow'

            if workflow_alias:
                parameters = payload.get('parameters')
                if not isinstance(parameters, dict):
                    parameters = {'user_query': message}
                else:
                    parameters.setdefault('user_query', message)

                workflow_response = gateway.run_workflow(
                    workflow_alias=workflow_alias,
                    parameters=parameters,
                    user_id=str(request.user.pk),
                )
                workflow_data = workflow_response.payload.get('data')
                workflow_content = workflow_data if isinstance(workflow_data, str) else json.dumps(
                    workflow_data,
                    ensure_ascii=False,
                    indent=2,
                )
                AgentMessage.objects.create(
                    conversation=conversation,
                    role='assistant',
                    content=workflow_content,
                    raw_payload=workflow_response.payload,
                    coze_chat_id='',
                )
                conversation.last_message_preview = workflow_content[:255]
                conversation.save()
                return JsonResponse(
                    {
                        'success': True,
                        'mode': 'workflow',
                        'message': 'ok',
                        'conversation_pk': conversation.pk,
                        'created_new_conversation': created_new_conversation,
                        'data': workflow_response.payload.get('data'),
                        'debug_url': workflow_response.debug_url,
                        'raw_payload': workflow_response.payload,
                    }
                )

            chat_result = gateway.run_chat_and_wait_answer(
                message=message,
                user_id=str(request.user.pk),
                conversation_id=conversation.coze_conversation_id or conversation_id,
            )
            answer_text = chat_result.get('answer_text', '')
            conversation.mode = 'chat'
            conversation.workflow_alias = ''
            conversation.coze_conversation_id = chat_result.get('conversation_id') or conversation.coze_conversation_id
            conversation.last_message_preview = answer_text[:255] if answer_text else message[:255]
            conversation.save()
            AgentMessage.objects.create(
                conversation=conversation,
                role='assistant',
                content=answer_text,
                raw_payload=chat_result.get('messages_payload') or {},
                coze_chat_id=chat_result.get('chat_id') or '',
            )
            return JsonResponse(
                {
                    'success': True,
                    'mode': 'chat',
                    'message': 'ok',
                    'conversation_pk': conversation.pk,
                    'created_new_conversation': created_new_conversation,
                    'answer_text': answer_text,
                    'conversation_id': chat_result.get('conversation_id'),
                    'chat_id': chat_result.get('chat_id'),
                    'status': chat_result.get('status'),
                    'raw_payload': chat_result.get('messages_payload'),
                }
            )
        except (CozeGatewayConfigError, CozeGatewayRequestError) as exc:
            return JsonResponse(
                {'success': False, 'message': str(exc)},
                status=400,
            )
        except Exception:
            return JsonResponse(
                {'success': False, 'message': '智能体代理调用失败'},
                status=500,
            )
