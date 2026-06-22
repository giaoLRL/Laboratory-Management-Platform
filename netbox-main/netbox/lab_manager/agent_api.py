from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from django.db import transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.utils.dateparse import parse_date
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
from .models import Hardware, HardwareImportBatch, Task, TaskAttachment

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


class SearchTasksAPIView(AgentAPIView):
    def post(self, request):
        payload = self.parse_json_body(request)
        if isinstance(payload, JsonResponse):
            return payload

        queryset = self.get_visible_task_queryset()
        assigned_to = payload.get('assigned_to')
        if assigned_to:
            queryset = queryset.filter(assigned_to__username__icontains=str(assigned_to).strip())

        created_by = payload.get('created_by')
        if created_by:
            queryset = queryset.filter(created_by__username__icontains=str(created_by).strip())

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

        date_from = parse_date(str(payload.get('date_from', '')).strip()) if payload.get('date_from') else None
        date_to = parse_date(str(payload.get('date_to', '')).strip()) if payload.get('date_to') else None
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
            queryset = queryset.filter(assigned_to__username__icontains=str(assigned_to).strip())

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

        date_from = parse_date(str(payload.get('date_from', '')).strip()) if payload.get('date_from') else None
        date_to = parse_date(str(payload.get('date_to', '')).strip()) if payload.get('date_to') else None
        if date_from:
            queryset = queryset.filter(completed_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(completed_at__date__lte=date_to)

        tasks = list(queryset.order_by('-completed_at', '-created'))
        attachments = TaskAttachment.objects.filter(task__in=tasks).select_related('task', 'uploaded_by')

        videos_by_task_id: dict[int, list[dict[str, Any]]] = {}
        for attachment in attachments:
            file_name = attachment.file.name or ''
            file_type = _detect_file_type(file_name)
            if file_type != 'video':
                continue

            videos_by_task_id.setdefault(attachment.task_id, []).append(
                {
                    'attachment_id': attachment.pk,
                    'file_name': Path(file_name).name,
                    'file_type': file_type,
                    'file_url': attachment.file.url if attachment.file else '',
                    'remark': attachment.remark,
                    'uploaded_by': attachment.uploaded_by.username,
                    'created': attachment.created.isoformat() if attachment.created else None,
                }
            )

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
                    'status': task.status,
                    'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                    'videos': task_videos,
                }
            )

        return self.success_response({'tasks': results})


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
