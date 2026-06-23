from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from django.db import transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.dateparse import parse_date, parse_datetime
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from netbox.plugins.utils import get_plugin_config
from users.models import User

from .choices import (
    HardwareApprovalStatusChoices,
    HardwareCategoryChoices,
    HardwareStatusChoices,
    TaskPriorityChoices,
    TaskStatusChoices,
)
from .models import CheckInRecord, Hardware, HardwareImportBatch, MemberOpenRecord, Task, TaskAttachment
from .services import PlatformDataError, PlatformDataService

VIDEO_EXTENSIONS = {'.mp4', '.webm', '.avi', '.mov', '.mkv', '.m4v'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
SOURCE_TYPES = {'json', 'excel', 'csv', 'text'}
HARDWARE_CATEGORY_VALUES = {value for value, _label in HardwareCategoryChoices}
HARDWARE_STATUS_VALUES = {value for value, _label in HardwareStatusChoices}
HARDWARE_APPROVAL_STATUS_VALUES = {value for value, _label in HardwareApprovalStatusChoices}
TASK_STATUS_VALUES = {value for value, _label in TaskStatusChoices}
TASK_PRIORITY_VALUES = {value for value, _label in TaskPriorityChoices}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_decimal(value: Any) -> Decimal | None:
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _detect_file_type(file_name: str) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return 'video'
    if suffix in IMAGE_EXTENSIONS:
        return 'image'
    return 'other'


def _user_lookup_q(field_name: str, value: Any) -> Q:
    keyword = str(value or '').strip()
    if not keyword:
        return Q()
    return (
        Q(**{f'{field_name}__username__icontains': keyword}) |
        Q(**{f'{field_name}__first_name__icontains': keyword}) |
        Q(**{f'{field_name}__last_name__icontains': keyword}) |
        Q(**{f'{field_name}__email__icontains': keyword})
    )


def _serialize_user(user) -> dict[str, Any]:
    full_name = user.get_full_name()
    return {
        'id': user.pk,
        'username': user.username,
        'full_name': full_name,
        'display': full_name or user.username,
        'email': user.email,
    }


def _parse_agent_date_range(payload: dict[str, Any]) -> tuple[Any, Any, str]:
    date_from = parse_date(str(payload.get('date_from', '')).strip()) if payload.get('date_from') else None
    date_to = parse_date(str(payload.get('date_to', '')).strip()) if payload.get('date_to') else None
    label = ''
    if date_from or date_to:
        return date_from, date_to, label

    today = timezone.localdate()
    date_range = str(payload.get('date_range', '') or payload.get('when', '')).strip().lower()
    if payload.get('relative_days'):
        days = max(_safe_int(payload.get('relative_days'), 0), 1)
        return today - timedelta(days=days - 1), today, f'最近{days}天'
    if date_range in {'today', '今天'}:
        return today, today, '今天'
    if date_range in {'yesterday', '昨天'}:
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday, '昨天'
    if date_range in {'this_week', '本周', '这周'}:
        return today - timedelta(days=today.weekday()), today, '本周'
    if date_range in {'last_week', '上周'}:
        start = today - timedelta(days=today.weekday() + 7)
        return start, start + timedelta(days=6), '上周'
    if date_range in {'this_month', '本月', '这个月'}:
        return today.replace(day=1), today, '本月'
    return None, None, label


@method_decorator(csrf_exempt, name='dispatch')
class AgentAPIView(View):
    http_method_names = ['post']

    def dispatch(self, request, *args, **kwargs):
        self.acting_user = self._resolve_user(request)
        if isinstance(self.acting_user, JsonResponse):
            return self.acting_user
        return super().dispatch(request, *args, **kwargs)

    def _resolve_user(self, request):
        if request.user.is_authenticated:
            return request.user

        expected_token = get_plugin_config('lab_manager', 'agent_api_token', None)
        provided_token = request.headers.get('X-Agent-Token')
        if not expected_token or provided_token != expected_token:
            return self.error_response('网关鉴权失败', code='40101', status=401)

        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return self.error_response('缺少 X-User-ID', code='40002', status=400)

        try:
            return User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError):
            return self.error_response('用户不存在', code='40401', status=404)

    def parse_json_body(self, request) -> dict[str, Any] | JsonResponse:
        try:
            raw_body = request.body.decode('utf-8') if request.body else '{}'
            return json.loads(raw_body or '{}')
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self.error_response('请求体不是合法 JSON', code='40001', status=400)

    def success_response(self, data: dict[str, Any], message: str = 'ok', status: int = 200) -> JsonResponse:
        return JsonResponse(
            {
                'success': True,
                'message': message,
                'data': data,
                'meta': {
                    'request_id': self.request.headers.get('X-Request-ID', ''),
                },
            },
            status=status,
        )

    def error_response(self, message: str, *, code: str, status: int) -> JsonResponse:
        return JsonResponse(
            {
                'success': False,
                'message': message,
                'error': {
                    'code': code,
                },
                'meta': {
                    'request_id': self.request.headers.get('X-Request-ID', ''),
                },
            },
            status=status,
        )

    def ensure_admin(self):
        if not self.acting_user.is_superuser:
            return self.error_response('当前用户无权限', code='40301', status=403)
        return None

    def get_visible_hardware_queryset(self):
        queryset = Hardware.objects.all().select_related('custodian', 'submitted_by')
        if not self.acting_user.is_superuser:
            queryset = queryset.filter(
                Q(approval_status=HardwareApprovalStatusChoices.APPROVED) |
                Q(submitted_by=self.acting_user)
            )
        return queryset

    def get_visible_task_queryset(self):
        queryset = Task.objects.all().select_related('created_by', 'assigned_to')
        if not self.acting_user.is_superuser:
            queryset = queryset.filter(
                Q(created_by=self.acting_user) |
                Q(assigned_to=self.acting_user)
            )
        return queryset


class SearchHardwareAPIView(AgentAPIView):
    def post(self, request):
        payload = self.parse_json_body(request)
        if isinstance(payload, JsonResponse):
            return payload

        queryset = self.get_visible_hardware_queryset()
        keywords = payload.get('keywords') or []
        if isinstance(keywords, str):
            keywords = [keywords]

        for keyword in keywords:
            keyword = str(keyword).strip()
            if not keyword:
                continue
            queryset = queryset.filter(
                Q(name__icontains=keyword) |
                Q(model_number__icontains=keyword) |
                Q(manufacturer__icontains=keyword) |
                Q(storage_location__icontains=keyword) |
                Q(remarks__icontains=keyword)
            )

        category = payload.get('category')
        if category:
            if category not in HARDWARE_CATEGORY_VALUES:
                return self.error_response('category 不合法', code='40003', status=400)
            queryset = queryset.filter(category=category)

        status = payload.get('status')
        if status:
            if status not in HARDWARE_STATUS_VALUES:
                return self.error_response('status 不合法', code='40003', status=400)
            queryset = queryset.filter(status=status)

        approval_status = payload.get('approval_status')
        if approval_status:
            if approval_status not in HARDWARE_APPROVAL_STATUS_VALUES:
                return self.error_response('approval_status 不合法', code='40003', status=400)
            queryset = queryset.filter(approval_status=approval_status)

        custodian = payload.get('custodian')
        if custodian:
            queryset = queryset.filter(custodian__username__icontains=str(custodian).strip())

        storage_location = payload.get('storage_location')
        if storage_location:
            queryset = queryset.filter(storage_location__icontains=str(storage_location).strip())

        offset = max(_safe_int(payload.get('offset', 0), 0), 0)
        limit = min(max(_safe_int(payload.get('limit', 20), 20), 1), 100)
        total = queryset.count()
        items = []
        for hardware in queryset.order_by('name')[offset:offset + limit]:
            items.append(
                {
                    'id': hardware.pk,
                    'name': hardware.name,
                    'category': hardware.category,
                    'category_label': hardware.get_category_display(),
                    'model_number': hardware.model_number,
                    'manufacturer': hardware.manufacturer,
                    'quantity': hardware.quantity,
                    'status': hardware.status,
                    'status_label': hardware.get_status_display(),
                    'storage_location': hardware.storage_location,
                    'custodian': hardware.custodian.username if hardware.custodian else '',
                    'purchase_link': hardware.purchase_link,
                    'approval_status': hardware.approval_status,
                }
            )

        return self.success_response(
            {
                'total': total,
                'items': items,
            }
        )


class AnalyzeHardwareGapAPIView(AgentAPIView):
    def post(self, request):
        payload = self.parse_json_body(request)
        if isinstance(payload, JsonResponse):
            return payload

        requirements = payload.get('requirements') or []
        if not isinstance(requirements, list) or not requirements:
            return self.error_response('缺少 requirements', code='40002', status=400)

        visible_queryset = self.get_visible_hardware_queryset().exclude(status=HardwareStatusChoices.SCRAPPED)
        matched = []
        missing = []

        for item in requirements:
            name = str(item.get('name', '')).strip()
            required_quantity = _safe_int(item.get('required_quantity', 0), 0)
            if not name or required_quantity <= 0:
                continue

            item_queryset = visible_queryset
            category = item.get('category')
            if category:
                if category not in HARDWARE_CATEGORY_VALUES:
                    continue
                item_queryset = item_queryset.filter(category=category)

            keywords = item.get('keywords') or [name]
            if isinstance(keywords, str):
                keywords = [keywords]

            query = Q()
            for keyword in keywords:
                keyword = str(keyword).strip()
                if not keyword:
                    continue
                query |= (
                    Q(name__icontains=keyword) |
                    Q(model_number__icontains=keyword) |
                    Q(manufacturer__icontains=keyword) |
                    Q(remarks__icontains=keyword)
                )

            if query:
                item_queryset = item_queryset.filter(query)

            available_quantity = item_queryset.aggregate(total=Sum('quantity')).get('total') or 0
            gap_quantity = max(required_quantity - available_quantity, 0)
            matched_items = [
                {
                    'id': hardware.pk,
                    'name': hardware.name,
                    'quantity': hardware.quantity,
                    'status': hardware.status,
                }
                for hardware in item_queryset.order_by('name')[:10]
            ]

            entry = {
                'name': name,
                'required_quantity': required_quantity,
                'available_quantity': available_quantity,
                'gap_quantity': gap_quantity,
            }
            if matched_items:
                entry['matched_items'] = matched_items
                matched.append(entry)
            else:
                missing.append(entry)

        return self.success_response(
            {
                'project_name': str(payload.get('project_name', '')).strip(),
                'matched': matched,
                'missing': missing,
            }
        )


class SearchMembersAPIView(AgentAPIView):
    def post(self, request):
        payload = self.parse_json_body(request)
        if isinstance(payload, JsonResponse):
            return payload

        queryset = User.objects.filter(is_active=True)
        keyword = str(payload.get('keyword', '') or payload.get('name', '') or '').strip()
        if keyword:
            queryset = queryset.filter(
                Q(username__icontains=keyword) |
                Q(first_name__icontains=keyword) |
                Q(last_name__icontains=keyword) |
                Q(email__icontains=keyword)
            )

        offset = max(_safe_int(payload.get('offset', 0), 0), 0)
        limit = min(max(_safe_int(payload.get('limit', 20), 20), 1), 100)
        total = queryset.count()

        visible_tasks = self.get_visible_task_queryset()
        items = []
        for member in queryset.order_by('username')[offset:offset + limit]:
            member_tasks = visible_tasks.filter(assigned_to=member)
            items.append(
                {
                    **_serialize_user(member),
                    'task_total': member_tasks.count(),
                    'task_pending': member_tasks.filter(status=TaskStatusChoices.PENDING).count(),
                    'task_in_progress': member_tasks.filter(status=TaskStatusChoices.IN_PROGRESS).count(),
                    'task_completed': member_tasks.filter(status=TaskStatusChoices.COMPLETED).count(),
                }
            )

        return self.success_response(
            {
                'total': total,
                'items': items,
            }
        )


class PlatformQueryAPIView(AgentAPIView):
    def post(self, request):
        payload = self.parse_json_body(request)
        if isinstance(payload, JsonResponse):
            return payload

        try:
            data = PlatformDataService().execute(user=self.acting_user, payload=payload)
        except PlatformDataError as exc:
            return self.error_response(str(exc), code='40004', status=400)

        return self.success_response(data)


class SearchTasksAPIView(AgentAPIView):
    def post(self, request):
        payload = self.parse_json_body(request)
        if isinstance(payload, JsonResponse):
            return payload

        queryset = self.get_visible_task_queryset()
        assigned_to = payload.get('assigned_to')
        if assigned_to:
            queryset = queryset.filter(_user_lookup_q('assigned_to', assigned_to))

        created_by = payload.get('created_by')
        if created_by:
            queryset = queryset.filter(_user_lookup_q('created_by', created_by))

        status = payload.get('status')
        if status:
            if status not in TASK_STATUS_VALUES:
                return self.error_response('status 不合法', code='40003', status=400)
            queryset = queryset.filter(status=status)

        priority = payload.get('priority')
        if priority:
            if priority not in TASK_PRIORITY_VALUES:
                return self.error_response('priority 不合法', code='40003', status=400)
            queryset = queryset.filter(priority=priority)

        keyword = payload.get('keyword')
        if keyword:
            keyword = str(keyword).strip()
            queryset = queryset.filter(
                Q(title__icontains=keyword) |
                Q(description__icontains=keyword) |
                Q(completion_note__icontains=keyword)
            )

        date_from, date_to, date_label = _parse_agent_date_range(payload)
        if status == TaskStatusChoices.COMPLETED:
            if date_from:
                queryset = queryset.filter(completed_at__date__gte=date_from)
            if date_to:
                queryset = queryset.filter(completed_at__date__lte=date_to)
        else:
            if date_from:
                queryset = queryset.filter(created__date__gte=date_from)
            if date_to:
                queryset = queryset.filter(created__date__lte=date_to)

        offset = max(_safe_int(payload.get('offset', 0), 0), 0)
        limit = min(max(_safe_int(payload.get('limit', 20), 20), 1), 100)
        total = queryset.count()
        items = []
        for task in queryset.order_by('-created')[offset:offset + limit]:
            items.append(
                {
                    'id': task.pk,
                    'title': task.title,
                    'description': task.description,
                    'priority': task.priority,
                    'priority_label': task.get_priority_display(),
                    'status': task.status,
                    'status_label': task.get_status_display(),
                    'created_by': task.created_by.username,
                    'assigned_to': task.assigned_to.username,
                    'deadline': task.deadline.isoformat() if task.deadline else None,
                    'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                    'completion_note': task.completion_note,
                }
            )

        return self.success_response(
            {
                'total': total,
                'date_from': date_from.isoformat() if date_from else None,
                'date_to': date_to.isoformat() if date_to else None,
                'date_label': date_label,
                'items': items,
            }
        )


class CreateTaskAPIView(AgentAPIView):
    def post(self, request):
        admin_error = self.ensure_admin()
        if admin_error:
            return admin_error

        payload = self.parse_json_body(request)
        if isinstance(payload, JsonResponse):
            return payload

        title = str(payload.get('title', '')).strip()
        description = str(payload.get('description', '')).strip()
        assigned_to_value = str(payload.get('assigned_to', '') or payload.get('assignee', '')).strip()
        priority = str(payload.get('priority') or TaskPriorityChoices.MEDIUM).strip()
        deadline_raw = str(payload.get('deadline', '')).strip()

        if not title:
            return self.error_response('缺少 title', code='40002', status=400)
        if not description:
            description = title
        if not assigned_to_value:
            return self.error_response('缺少 assigned_to', code='40002', status=400)
        if priority not in TASK_PRIORITY_VALUES:
            return self.error_response('priority 不合法', code='40003', status=400)

        assignee = User.objects.filter(
            Q(username__iexact=assigned_to_value) |
            Q(email__iexact=assigned_to_value) |
            Q(first_name__icontains=assigned_to_value) |
            Q(last_name__icontains=assigned_to_value)
        ).first()
        if assignee is None:
            return self.error_response('执行人不存在', code='40401', status=404)

        deadline = parse_datetime(deadline_raw) if deadline_raw else None
        if deadline_raw and deadline is None:
            parsed_date = parse_date(deadline_raw)
            deadline = timezone.make_aware(
                timezone.datetime.combine(parsed_date, timezone.datetime.max.time())
            ) if parsed_date else None
        if deadline_raw and deadline is None:
            return self.error_response('deadline 不合法', code='40003', status=400)

        task = Task.objects.create(
            title=title,
            description=description,
            priority=priority,
            status=TaskStatusChoices.PENDING,
            created_by=self.acting_user,
            assigned_to=assignee,
            deadline=deadline,
        )

        return self.success_response(
            {
                'id': task.pk,
                'title': task.title,
                'description': task.description,
                'priority': task.priority,
                'priority_label': task.get_priority_display(),
                'status': task.status,
                'status_label': task.get_status_display(),
                'created_by': task.created_by.username,
                'assigned_to': task.assigned_to.username,
                'assigned_to_name': task.assigned_to.get_full_name() or task.assigned_to.username,
                'deadline': task.deadline.isoformat() if task.deadline else None,
            },
            message='created',
            status=201,
        )


class SearchCheckInsAPIView(AgentAPIView):
    def post(self, request):
        payload = self.parse_json_body(request)
        if isinstance(payload, JsonResponse):
            return payload

        queryset = CheckInRecord.objects.select_related('user').order_by('-created')
        if not self.acting_user.is_superuser:
            queryset = queryset.filter(user=self.acting_user)

        user_value = payload.get('user')
        if user_value:
            queryset = queryset.filter(_user_lookup_q('user', user_value))

        date_from, date_to, date_label = _parse_agent_date_range(payload)
        if date_from:
            queryset = queryset.filter(created__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created__date__lte=date_to)

        offset = max(_safe_int(payload.get('offset', 0), 0), 0)
        limit = min(max(_safe_int(payload.get('limit', 20), 20), 1), 100)
        total = queryset.count()
        items = []
        for record in queryset[offset:offset + limit]:
            items.append(
                {
                    'id': record.pk,
                    'user': record.user.username,
                    'user_name': record.user.get_full_name() or record.user.username,
                    'photo_url': record.photo.url if record.photo else '',
                    'latitude': str(record.latitude),
                    'longitude': str(record.longitude),
                    'accuracy': str(record.accuracy) if record.accuracy is not None else '',
                    'address': record.address,
                    'note': record.note,
                    'created': record.created.isoformat() if record.created else None,
                }
            )

        return self.success_response(
            {
                'total': total,
                'date_from': date_from.isoformat() if date_from else None,
                'date_to': date_to.isoformat() if date_to else None,
                'date_label': date_label,
                'items': items,
            }
        )


class SearchMemberOpenRecordsAPIView(AgentAPIView):
    def post(self, request):
        admin_error = self.ensure_admin()
        if admin_error:
            return admin_error

        payload = self.parse_json_body(request)
        if isinstance(payload, JsonResponse):
            return payload

        queryset = MemberOpenRecord.objects.select_related('user').order_by('-created')
        user_value = payload.get('user')
        if user_value:
            queryset = queryset.filter(_user_lookup_q('user', user_value))
        target_type = str(payload.get('target_type', '')).strip()
        if target_type:
            queryset = queryset.filter(target_type=target_type)

        date_from, date_to, date_label = _parse_agent_date_range(payload)
        if date_from:
            queryset = queryset.filter(created__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created__date__lte=date_to)

        offset = max(_safe_int(payload.get('offset', 0), 0), 0)
        limit = min(max(_safe_int(payload.get('limit', 20), 20), 1), 100)
        total = queryset.count()
        items = []
        for record in queryset[offset:offset + limit]:
            items.append(
                {
                    'id': record.pk,
                    'user': record.user.username,
                    'user_name': record.user.get_full_name() or record.user.username,
                    'page_title': record.page_title,
                    'path': record.path,
                    'target_type': record.target_type,
                    'target_id': record.target_id,
                    'ip_address': record.ip_address,
                    'created': record.created.isoformat() if record.created else None,
                }
            )

        return self.success_response(
            {
                'total': total,
                'date_from': date_from.isoformat() if date_from else None,
                'date_to': date_to.isoformat() if date_to else None,
                'date_label': date_label,
                'items': items,
            }
        )


class SearchTaskVideosAPIView(AgentAPIView):
    def post(self, request):
        payload = self.parse_json_body(request)
        if isinstance(payload, JsonResponse):
            return payload

        queryset = self.get_visible_task_queryset()
        task_ids = payload.get('task_ids') or []
        if task_ids:
            queryset = queryset.filter(pk__in=task_ids)

        assigned_to = payload.get('assigned_to')
        if assigned_to:
            queryset = queryset.filter(_user_lookup_q('assigned_to', assigned_to))

        status = payload.get('status')
        if status:
            if status not in TASK_STATUS_VALUES:
                return self.error_response('status 不合法', code='40003', status=400)
            queryset = queryset.filter(status=status)

        keyword = payload.get('keyword')
        if keyword:
            keyword = str(keyword).strip()
            queryset = queryset.filter(
                Q(title__icontains=keyword) |
                Q(description__icontains=keyword) |
                Q(completion_note__icontains=keyword)
            )

        date_from, date_to, date_label = _parse_agent_date_range(payload)
        if date_from:
            queryset = queryset.filter(completed_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(completed_at__date__lte=date_to)

        tasks = list(queryset.order_by('-completed_at', '-created'))
        attachments = TaskAttachment.objects.filter(task__in=tasks).select_related('task', 'uploaded_by')

        videos_by_task_id: dict[int, list[dict[str, Any]]] = {}
        export_items = []
        video_count = 0
        for attachment in attachments:
            file_name = attachment.file.name or ''
            file_type = _detect_file_type(file_name)
            if file_type != 'video':
                continue

            video_item = {
                'attachment_id': attachment.pk,
                'file_name': Path(file_name).name,
                'file_type': file_type,
                'file_url': attachment.file.url if attachment.file else '',
                'remark': attachment.remark,
                'uploaded_by': attachment.uploaded_by.username,
                'created': attachment.created.isoformat() if attachment.created else None,
            }
            videos_by_task_id.setdefault(attachment.task_id, []).append(video_item)
            export_items.append(
                {
                    **video_item,
                    'task_id': attachment.task_id,
                    'task_title': attachment.task.title,
                    'assigned_to': attachment.task.assigned_to.username,
                    'assigned_to_name': attachment.task.assigned_to.get_full_name(),
                    'completed_at': attachment.task.completed_at.isoformat() if attachment.task.completed_at else None,
                }
            )
            video_count += 1

        results = []
        for task in tasks:
            task_videos = videos_by_task_id.get(task.pk, [])
            if not task_videos:
                continue
            results.append(
                {
                    'task_id': task.pk,
                    'task_title': task.title,
                    'assigned_to': task.assigned_to.username,
                    'assigned_to_detail': _serialize_user(task.assigned_to),
                    'status': task.status,
                    'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                    'videos': task_videos,
                }
            )

        return self.success_response(
            {
                'total': len(results),
                'task_count': len(results),
                'video_count': video_count,
                'date_from': date_from.isoformat() if date_from else None,
                'date_to': date_to.isoformat() if date_to else None,
                'date_label': date_label,
                'tasks': results,
                'export_items': export_items,
            }
        )


class ValidateHardwareImportAPIView(AgentAPIView):
    def post(self, request):
        admin_error = self.ensure_admin()
        if admin_error:
            return admin_error

        payload = self.parse_json_body(request)
        if isinstance(payload, JsonResponse):
            return payload

        source_type = str(payload.get('source_type', '')).strip().lower()
        if source_type not in SOURCE_TYPES:
            return self.error_response('source_type 不合法', code='40003', status=400)

        if payload.get('import_action') != 'validate':
            return self.error_response('import_action 必须为 validate', code='40003', status=400)

        items = payload.get('items')
        if not isinstance(items, list) or not items:
            return self.error_response('缺少待导入 items', code='40002', status=400)

        valid_items = []
        duplicate_items = []
        errors = []

        existing_queryset = Hardware.objects.all()

        for index, item in enumerate(items, start=1):
            row_no = index
            name = str(item.get('name', '')).strip()
            category = str(item.get('category', '')).strip()
            quantity = item.get('quantity', 0)
            status = str(item.get('status', HardwareStatusChoices.IN_USE)).strip() or HardwareStatusChoices.IN_USE
            model_number = str(item.get('model_number', '')).strip()

            row_errors = []
            if not name:
                row_errors.append(('name', '名称不能为空'))
            if category not in HARDWARE_CATEGORY_VALUES:
                row_errors.append(('category', '类别不合法'))

            quantity = _safe_int(quantity, 0)
            if quantity <= 0:
                row_errors.append(('quantity', '数量必须大于 0'))

            if status not in HARDWARE_STATUS_VALUES:
                row_errors.append(('status', '状态不合法'))

            if row_errors:
                for field, message in row_errors:
                    errors.append(
                        {
                            'row_no': row_no,
                            'field': field,
                            'code': '40003',
                            'message': message,
                        }
                    )
                continue

            duplicate_query = Q(name__iexact=name)
            if model_number:
                duplicate_query &= Q(model_number__iexact=model_number)
            duplicate_hardware = existing_queryset.filter(duplicate_query).first()
            if duplicate_hardware:
                duplicate_items.append(
                    {
                        'row_no': row_no,
                        'name': name,
                        'matched_hardware_id': duplicate_hardware.pk,
                        'reason': '名称或名称+型号命中现有库存',
                    }
                )
                continue

            valid_items.append(
                {
                    'row_no': row_no,
                    'name': name,
                    'category': category,
                    'model_number': model_number,
                    'manufacturer': str(item.get('manufacturer', '')).strip(),
                    'quantity': quantity,
                    'unit_price': str(item.get('unit_price', '')).strip(),
                    'status': status,
                    'storage_location': str(item.get('storage_location', '')).strip(),
                    'purchase_link': str(item.get('purchase_link', '')).strip(),
                    'remarks': str(item.get('remarks', '')).strip(),
                }
            )

        batch = HardwareImportBatch.objects.create(
            created_by=self.acting_user,
            source_type=source_type,
            status='validated',
            raw_payload=items,
            validated_payload={
                'valid_items': valid_items,
                'duplicate_items': duplicate_items,
                'errors': errors,
            },
            result_summary={
                'total': len(items),
                'valid_count': len(valid_items),
                'error_count': len(errors),
                'duplicate_count': len(duplicate_items),
            },
        )

        return self.success_response(
            {
                'batch_id': batch.batch_id,
                'status': batch.status,
                'summary': batch.result_summary,
                'valid_items': valid_items,
                'duplicate_items': duplicate_items,
                'errors': errors,
            },
            message='validated',
        )


class CommitHardwareImportAPIView(AgentAPIView):
    def post(self, request):
        admin_error = self.ensure_admin()
        if admin_error:
            return admin_error

        payload = self.parse_json_body(request)
        if isinstance(payload, JsonResponse):
            return payload

        if payload.get('import_action') != 'commit':
            return self.error_response('import_action 必须为 commit', code='40003', status=400)

        if payload.get('confirm') is not True:
            return self.error_response('confirm 必须为 true', code='40002', status=400)

        batch_id = str(payload.get('batch_id', '')).strip()
        if not batch_id:
            return self.error_response('缺少 batch_id', code='40002', status=400)

        try:
            batch = HardwareImportBatch.objects.get(batch_id=batch_id)
        except HardwareImportBatch.DoesNotExist:
            return self.error_response('批次不存在', code='40401', status=404)

        if batch.status == 'imported':
            return self.error_response('批次已导入，禁止重复提交', code='40902', status=409)

        if batch.status != 'validated':
            return self.error_response('预校验未通过，无法提交', code='42201', status=422)

        valid_items = (batch.validated_payload or {}).get('valid_items') or []
        if not valid_items:
            return self.error_response('批次没有可导入的数据', code='42201', status=422)

        created_ids = []
        try:
            with transaction.atomic():
                for item in valid_items:
                    unit_price = _safe_decimal(item.get('unit_price'))
                    hardware = Hardware.objects.create(
                        name=item['name'],
                        category=item['category'],
                        model_number=item.get('model_number', ''),
                        manufacturer=item.get('manufacturer', ''),
                        quantity=int(item['quantity']),
                        unit_price=unit_price,
                        status=item.get('status') or HardwareStatusChoices.IN_USE,
                        storage_location=item.get('storage_location', ''),
                        purchase_link=item.get('purchase_link', ''),
                        remarks=item.get('remarks', ''),
                        submitted_by=self.acting_user,
                        approval_status=HardwareApprovalStatusChoices.APPROVED,
                        approved_by=self.acting_user,
                    )
                    created_ids.append(hardware.pk)

                batch.status = 'imported'
                batch.result_summary = {
                    'total': len(valid_items),
                    'success_count': len(created_ids),
                    'failed_count': 0,
                    'created_ids': created_ids,
                }
                batch.save(update_fields=['status', 'result_summary', 'last_updated'])
        except Exception:
            return self.error_response('平台内部异常', code='50001', status=500)

        return self.success_response(
            {
                'batch_id': batch.batch_id,
                'status': batch.status,
                'summary': {
                    'total': len(valid_items),
                    'success_count': len(created_ids),
                    'failed_count': 0,
                },
                'created_ids': created_ids,
            },
            message='imported',
        )
