from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.db.models import Count, Q, Sum
from django.utils.dateparse import parse_date, parse_datetime
from users.models import User

from ..choices import HardwareApprovalStatusChoices
from ..models import Hardware, Task, TaskAttachment


LOOKUP_MAP = {
    'eq': '',
    'ne': '',
    'contains': '__icontains',
    'icontains': '__icontains',
    'in': '__in',
    'gte': '__gte',
    'lte': '__lte',
    'gt': '__gt',
    'lt': '__lt',
    'isnull': '__isnull',
}

VIDEO_EXTENSIONS = {'.mp4', '.webm', '.avi', '.mov', '.mkv', '.m4v'}


class PlatformDataError(ValueError):
    pass


@dataclass(frozen=True)
class FieldSpec:
    path: str
    label: str = ''
    kind: str = 'text'
    choices: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelSpec:
    key: str
    model: Any
    fields: dict[str, FieldSpec]
    default_fields: tuple[str, ...]
    search_fields: tuple[str, ...] = ()
    default_ordering: tuple[str, ...] = ('id',)
    selectable_related: tuple[str, ...] = ()


def _choice_dict(choices) -> dict[str, str]:
    return {value: str(label) for value, label in choices}


class PlatformDataService:
    """Whitelist-based data access layer for the lab manager agent."""

    REGISTRY = {
        'hardware': ModelSpec(
            key='hardware',
            model=Hardware,
            fields={
                'id': FieldSpec('id', 'ID', 'number'),
                'name': FieldSpec('name', '名称'),
                'category': FieldSpec('category', '类别', 'choice'),
                'category_label': FieldSpec('category', '类别', 'choice_label'),
                'model_number': FieldSpec('model_number', '型号'),
                'manufacturer': FieldSpec('manufacturer', '厂家/品牌'),
                'quantity': FieldSpec('quantity', '数量', 'number'),
                'unit_price': FieldSpec('unit_price', '单价', 'decimal'),
                'purchase_date': FieldSpec('purchase_date', '购买日期', 'date'),
                'purchase_link': FieldSpec('purchase_link', '购买链接', 'url'),
                'status': FieldSpec('status', '状态', 'choice'),
                'status_label': FieldSpec('status', '状态', 'choice_label'),
                'storage_location': FieldSpec('storage_location', '存放位置'),
                'custodian': FieldSpec('custodian__username', '保管人'),
                'custodian_name': FieldSpec('custodian', '保管人姓名', 'user_display'),
                'submitted_by': FieldSpec('submitted_by__username', '提交人'),
                'approval_status': FieldSpec('approval_status', '审批状态', 'choice'),
                'approval_status_label': FieldSpec('approval_status', '审批状态', 'choice_label'),
                'approved_by': FieldSpec('approved_by__username', '审核人'),
                'approval_note': FieldSpec('approval_note', '审核备注'),
                'remarks': FieldSpec('remarks', '备注'),
                'created': FieldSpec('created', '创建时间', 'datetime'),
                'last_updated': FieldSpec('last_updated', '更新时间', 'datetime'),
            },
            default_fields=('id', 'name', 'category_label', 'quantity', 'status_label', 'approval_status_label', 'storage_location', 'custodian_name'),
            search_fields=('name', 'model_number', 'manufacturer', 'storage_location', 'remarks', 'custodian__username', 'submitted_by__username'),
            default_ordering=('name',),
            selectable_related=('custodian', 'submitted_by', 'approved_by'),
        ),
        'hardware_approval': ModelSpec(
            key='hardware_approval',
            model=Hardware,
            fields={
                'id': FieldSpec('id', 'ID', 'number'),
                'name': FieldSpec('name', '名称'),
                'approval_status': FieldSpec('approval_status', '审批状态', 'choice'),
                'approval_status_label': FieldSpec('approval_status', '审批状态', 'choice_label'),
                'submitted_by': FieldSpec('submitted_by__username', '提交人'),
                'approved_by': FieldSpec('approved_by__username', '审核人'),
                'approval_note': FieldSpec('approval_note', '审核备注'),
                'created': FieldSpec('created', '创建时间', 'datetime'),
                'last_updated': FieldSpec('last_updated', '更新时间', 'datetime'),
            },
            default_fields=('id', 'name', 'approval_status_label', 'submitted_by', 'approved_by', 'approval_note', 'created'),
            search_fields=('name', 'submitted_by__username', 'approved_by__username', 'approval_note'),
            default_ordering=('-created',),
            selectable_related=('submitted_by', 'approved_by'),
        ),
        'task': ModelSpec(
            key='task',
            model=Task,
            fields={
                'id': FieldSpec('id', 'ID', 'number'),
                'title': FieldSpec('title', '标题'),
                'description': FieldSpec('description', '任务描述'),
                'priority': FieldSpec('priority', '优先级', 'choice'),
                'priority_label': FieldSpec('priority', '优先级', 'choice_label'),
                'status': FieldSpec('status', '状态', 'choice'),
                'status_label': FieldSpec('status', '状态', 'choice_label'),
                'created_by': FieldSpec('created_by__username', '创建人'),
                'created_by_name': FieldSpec('created_by', '创建人姓名', 'user_display'),
                'assigned_to': FieldSpec('assigned_to__username', '执行人'),
                'assigned_to_name': FieldSpec('assigned_to', '执行人姓名', 'user_display'),
                'deadline': FieldSpec('deadline', '截止日期', 'datetime'),
                'completed_at': FieldSpec('completed_at', '完成时间', 'datetime'),
                'completion_note': FieldSpec('completion_note', '完成说明'),
                'created': FieldSpec('created', '创建时间', 'datetime'),
                'last_updated': FieldSpec('last_updated', '更新时间', 'datetime'),
            },
            default_fields=('id', 'title', 'status_label', 'priority_label', 'assigned_to_name', 'deadline', 'completed_at'),
            search_fields=('title', 'description', 'completion_note', 'created_by__username', 'assigned_to__username', 'assigned_to__first_name', 'assigned_to__last_name'),
            default_ordering=('-completed_at', '-created'),
            selectable_related=('created_by', 'assigned_to'),
        ),
        'task_attachment': ModelSpec(
            key='task_attachment',
            model=TaskAttachment,
            fields={
                'id': FieldSpec('id', 'ID', 'number'),
                'task_id': FieldSpec('task_id', '任务ID', 'number'),
                'task_title': FieldSpec('task__title', '任务标题'),
                'task_status': FieldSpec('task__status', '任务状态', 'choice'),
                'task_status_label': FieldSpec('task__status', '任务状态', 'choice_label'),
                'assigned_to': FieldSpec('task__assigned_to__username', '任务执行人'),
                'assigned_to_name': FieldSpec('task__assigned_to', '任务执行人姓名', 'user_display'),
                'file_name': FieldSpec('file', '文件名', 'file_name'),
                'file_url': FieldSpec('file', '文件URL', 'file_url'),
                'file_type': FieldSpec('file', '文件类型', 'file_type'),
                'remark': FieldSpec('remark', '附件说明'),
                'uploaded_by': FieldSpec('uploaded_by__username', '上传者'),
                'uploaded_by_name': FieldSpec('uploaded_by', '上传者姓名', 'user_display'),
                'created': FieldSpec('created', '上传时间', 'datetime'),
                'last_updated': FieldSpec('last_updated', '更新时间', 'datetime'),
            },
            default_fields=('id', 'task_title', 'file_name', 'file_type', 'file_url', 'uploaded_by_name', 'created'),
            search_fields=('task__title', 'task__description', 'remark', 'uploaded_by__username', 'task__assigned_to__username'),
            default_ordering=('-created',),
            selectable_related=('task', 'task__assigned_to', 'uploaded_by'),
        ),
        'user': ModelSpec(
            key='user',
            model=User,
            fields={
                'id': FieldSpec('id', 'ID', 'number'),
                'username': FieldSpec('username', '用户名'),
                'first_name': FieldSpec('first_name', '名'),
                'last_name': FieldSpec('last_name', '姓'),
                'full_name': FieldSpec('self', '姓名', 'user_display'),
                'email': FieldSpec('email', '邮箱'),
                'is_active': FieldSpec('is_active', '是否启用', 'boolean'),
                'is_superuser': FieldSpec('is_superuser', '是否管理员', 'boolean'),
                'date_joined': FieldSpec('date_joined', '加入时间', 'datetime'),
                'task_total': FieldSpec('assigned_tasks', '任务总数', 'related_count'),
                'task_completed': FieldSpec('assigned_tasks_completed', '已完成任务数', 'computed_count'),
                'task_in_progress': FieldSpec('assigned_tasks_in_progress', '进行中任务数', 'computed_count'),
                'task_pending': FieldSpec('assigned_tasks_pending', '待开始任务数', 'computed_count'),
            },
            default_fields=('id', 'username', 'full_name', 'email', 'is_active', 'task_total', 'task_pending', 'task_in_progress', 'task_completed'),
            search_fields=('username', 'first_name', 'last_name', 'email'),
            default_ordering=('username',),
        ),
    }

    def describe_registry(self) -> dict[str, Any]:
        return {
            key: {
                'fields': [
                    {'name': field_name, 'label': field.label, 'kind': field.kind}
                    for field_name, field in spec.fields.items()
                ],
                'default_fields': list(spec.default_fields),
                'search_fields': list(spec.search_fields),
            }
            for key, spec in self.REGISTRY.items()
        }

    def execute(self, *, user, payload: dict[str, Any]) -> dict[str, Any]:
        action = str(payload.get('action') or 'list_records').strip()
        model_key = str(payload.get('model') or '').strip()
        spec = self._get_spec(model_key)

        queryset = self._visible_queryset(user, spec)
        queryset = self._apply_filters(queryset, spec, payload.get('filters') or {})

        if payload.get('keyword'):
            queryset = self._apply_keyword(queryset, spec, str(payload['keyword']).strip())

        if action == 'list_records':
            return self._list_records(queryset, spec, payload)
        if action == 'count_records':
            return self._count_records(queryset, spec, payload)
        if action == 'get_record_detail':
            return self._get_record_detail(queryset, spec, payload)
        if action == 'aggregate_records':
            return self._aggregate_records(queryset, spec, payload)
        if action == 'search_records':
            keyword = str(payload.get('keyword', '')).strip()
            if not keyword:
                raise PlatformDataError('search_records 需要 keyword')
            return self._list_records(self._apply_keyword(queryset, spec, keyword), spec, payload)
        if action == 'describe_registry':
            return {'models': self.describe_registry()}

        raise PlatformDataError(f'action 不支持: {action}')

    def infer_query(self, message: str) -> dict[str, Any] | None:
        message = str(message or '').strip()
        if not message:
            return None

        if any(word in message for word in ('能查询', '可查询', '查询哪些数据', '哪些数据', '数据能力', '能读取', '可读取')):
            return {'action': 'describe_registry', 'model': 'hardware'}

        if '管理员' in message or '超级管理员' in message or 'admin' in message.lower():
            return {
                'action': 'list_records',
                'model': 'user',
                'filters': {'is_superuser': True},
                'fields': ('id', 'username', 'full_name', 'email', 'is_active', 'is_superuser', 'date_joined', 'task_total'),
                'limit': 20,
            }

        if any(word in message for word in ('人员名单', '人员信息', '成员名单', '成员信息', '用户列表', '用户信息', '有哪些成员', '有哪些人员')):
            return {'action': 'list_records', 'model': 'user', 'limit': 50}

        if '待审核' in message or '待审批' in message:
            return {
                'action': 'list_records',
                'model': 'hardware_approval',
                'filters': {'approval_status': 'pending'},
                'limit': 50,
            }

        if '已驳回' in message or '驳回' in message:
            return {
                'action': 'list_records',
                'model': 'hardware_approval',
                'filters': {'approval_status': 'rejected'},
                'limit': 50,
            }

        if '报废' in message or '已报废' in message:
            return {
                'action': 'list_records',
                'model': 'hardware',
                'filters': {'status': 'scrapped'},
                'fields': ('id', 'name', 'category_label', 'quantity', 'status_label', 'storage_location', 'custodian_name'),
                'limit': 50,
            }

        if any(word in message for word in ('每个人', '每位成员', '按成员', '按人员')) and any(word in message for word in ('任务', '未完成', '待办')):
            return {
                'action': 'list_records',
                'model': 'user',
                'fields': ('username', 'full_name', 'task_pending', 'task_in_progress', 'task_completed', 'task_total'),
                'limit': 100,
            }

        explicit_query_words = ('查询', '查一下', '查看', '列出', '统计', '多少', '哪些', '信息', '名单', '列表', '明细')

        if '任务' in message and any(word in message for word in explicit_query_words):
            query = {
                'action': 'list_records',
                'model': 'task',
                'limit': 50,
                'filters': {},
            }
            if '已完成' in message:
                query['filters']['status'] = 'completed'
            elif '进行中' in message:
                query['filters']['status'] = 'in_progress'
            elif '待开始' in message or '待办' in message or '未完成' in message:
                query['filters']['status__in'] = ['pending', 'in_progress']
            member = self._find_member_name(message)
            if member:
                query['filters']['assigned_to'] = member
            return query

        if any(word in message for word in ('硬件', '库存', '设备', '器材')) and any(word in message for word in explicit_query_words):
            query = {'action': 'list_records', 'model': 'hardware', 'limit': 50, 'filters': {}}
            if '闲置' in message:
                query['filters']['status'] = 'idle'
            elif '在用' in message:
                query['filters']['status'] = 'in_use'
            elif '维修' in message:
                query['filters']['status'] = 'repair'
            if '待审核' in message:
                query['filters']['approval_status'] = 'pending'
            return query

        return None

    def _get_spec(self, model_key: str) -> ModelSpec:
        spec = self.REGISTRY.get(model_key)
        if not spec:
            raise PlatformDataError(f'model 不支持: {model_key}')
        return spec

    def _visible_queryset(self, user, spec: ModelSpec):
        queryset = spec.model.objects.all()
        if spec.selectable_related:
            queryset = queryset.select_related(*spec.selectable_related)

        if spec.model is Hardware:
            if spec.key == 'hardware_approval' and not user.is_superuser:
                queryset = queryset.filter(submitted_by=user)
            elif not user.is_superuser:
                queryset = queryset.filter(Q(approval_status=HardwareApprovalStatusChoices.APPROVED) | Q(submitted_by=user))
        elif spec.model is Task:
            if not user.is_superuser:
                queryset = queryset.filter(Q(created_by=user) | Q(assigned_to=user))
        elif spec.model is TaskAttachment:
            if not user.is_superuser:
                queryset = queryset.filter(Q(task__created_by=user) | Q(task__assigned_to=user))
        elif spec.model is User:
            queryset = queryset.filter(is_active=True)

        return queryset

    def _apply_filters(self, queryset, spec: ModelSpec, filters: dict[str, Any]):
        if not isinstance(filters, dict):
            raise PlatformDataError('filters 必须是对象')

        for raw_key, value in filters.items():
            field_name, lookup = self._split_filter_key(str(raw_key))
            field = self._get_field(spec, field_name)
            lookup_suffix = LOOKUP_MAP.get(lookup)
            if lookup_suffix is None:
                raise PlatformDataError(f'过滤操作不支持: {lookup}')

            if field.kind in {'choice_label', 'user_display', 'file_name', 'file_url', 'file_type', 'related_count', 'computed_count'}:
                raise PlatformDataError(f'字段不支持过滤: {field_name}')

            path = field.path
            if path.endswith('__username') and lookup in {'eq', 'contains', 'icontains'}:
                relation = path[:-len('__username')]
                keyword = str(value or '').strip()
                user_query = (
                    Q(**{f'{relation}__username__icontains': keyword}) |
                    Q(**{f'{relation}__first_name__icontains': keyword}) |
                    Q(**{f'{relation}__last_name__icontains': keyword}) |
                    Q(**{f'{relation}__email__icontains': keyword})
                )
                queryset = queryset.exclude(user_query) if lookup == 'ne' else queryset.filter(user_query)
                continue

            coerced = self._coerce_filter_value(value, field.kind, lookup)
            if lookup == 'ne':
                queryset = queryset.exclude(**{path: coerced})
            else:
                queryset = queryset.filter(**{f'{path}{lookup_suffix}': coerced})

        return queryset

    def _apply_keyword(self, queryset, spec: ModelSpec, keyword: str):
        if not keyword:
            return queryset
        query = Q()
        for field_path in spec.search_fields:
            query |= Q(**{f'{field_path}__icontains': keyword})
        return queryset.filter(query) if query else queryset

    def _list_records(self, queryset, spec: ModelSpec, payload: dict[str, Any]) -> dict[str, Any]:
        fields = self._resolve_fields(spec, payload.get('fields'))
        offset = max(self._safe_int(payload.get('offset'), 0), 0)
        limit = min(max(self._safe_int(payload.get('limit'), 20), 1), 100)
        ordering = self._resolve_ordering(spec, payload.get('order_by'))
        total = queryset.count()

        items = [
            self._serialize_record(obj, spec, fields)
            for obj in queryset.order_by(*ordering)[offset:offset + limit]
        ]
        return {
            'action': 'list_records',
            'model': spec.key,
            'total': total,
            'offset': offset,
            'limit': limit,
            'fields': list(fields),
            'items': items,
        }

    def _count_records(self, queryset, spec: ModelSpec, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            'action': 'count_records',
            'model': spec.key,
            'total': queryset.count(),
        }

    def _get_record_detail(self, queryset, spec: ModelSpec, payload: dict[str, Any]) -> dict[str, Any]:
        record_id = payload.get('id')
        if not record_id:
            raise PlatformDataError('get_record_detail 需要 id')
        fields = self._resolve_fields(spec, payload.get('fields'), include_default=True)
        try:
            obj = queryset.get(pk=record_id)
        except spec.model.DoesNotExist as exc:
            raise PlatformDataError('记录不存在或无权限访问') from exc
        return {
            'action': 'get_record_detail',
            'model': spec.key,
            'item': self._serialize_record(obj, spec, fields),
        }

    def _aggregate_records(self, queryset, spec: ModelSpec, payload: dict[str, Any]) -> dict[str, Any]:
        group_by = payload.get('group_by')
        if isinstance(group_by, str):
            group_by = [group_by]
        if not group_by:
            raise PlatformDataError('aggregate_records 需要 group_by')
        group_by = [str(field) for field in group_by]
        for field_name in group_by:
            field = self._get_field(spec, field_name)
            if field.kind in {'choice_label', 'user_display', 'file_name', 'file_url', 'file_type', 'related_count', 'computed_count'}:
                raise PlatformDataError(f'字段不支持分组: {field_name}')

        values = [self._get_field(spec, field_name).path for field_name in group_by]
        metrics = payload.get('metrics') or {'count': 'id'}
        annotations = {'count': Count('id')}
        if isinstance(metrics, dict):
            for metric_name, field_name in metrics.items():
                if metric_name == 'count':
                    annotations['count'] = Count(self._get_field(spec, str(field_name)).path if field_name else 'id')
                elif metric_name.startswith('sum_'):
                    annotations[metric_name] = Sum(self._get_field(spec, str(field_name)).path)
                else:
                    raise PlatformDataError(f'聚合指标不支持: {metric_name}')

        rows = list(queryset.values(*values).annotate(**annotations).order_by(*values)[:100])
        return {
            'action': 'aggregate_records',
            'model': spec.key,
            'group_by': group_by,
            'items': rows,
        }

    def _resolve_fields(self, spec: ModelSpec, requested_fields, include_default: bool = False) -> tuple[str, ...]:
        if not requested_fields:
            return spec.default_fields
        if isinstance(requested_fields, str):
            requested_fields = [requested_fields]
        fields = []
        for field_name in requested_fields:
            field_name = str(field_name)
            self._get_field(spec, field_name)
            if field_name not in fields:
                fields.append(field_name)
        if include_default:
            for field_name in spec.default_fields:
                if field_name not in fields:
                    fields.append(field_name)
        return tuple(fields[:40])

    def _resolve_ordering(self, spec: ModelSpec, order_by) -> tuple[str, ...]:
        if not order_by:
            return spec.default_ordering
        if isinstance(order_by, str):
            order_by = [order_by]
        ordering = []
        for raw_field in order_by:
            raw_field = str(raw_field)
            descending = raw_field.startswith('-')
            field_name = raw_field[1:] if descending else raw_field
            field = self._get_field(spec, field_name)
            if field.kind in {'choice_label', 'user_display', 'file_name', 'file_url', 'file_type', 'related_count', 'computed_count'}:
                raise PlatformDataError(f'字段不支持排序: {field_name}')
            ordering.append(f'-{field.path}' if descending else field.path)
        return tuple(ordering[:3]) or spec.default_ordering

    def _serialize_record(self, obj, spec: ModelSpec, fields: tuple[str, ...]) -> dict[str, Any]:
        return {field_name: self._serialize_field(obj, spec, field_name) for field_name in fields}

    def _serialize_field(self, obj, spec: ModelSpec, field_name: str) -> Any:
        field = self._get_field(spec, field_name)
        if field.kind == 'computed_count':
            return self._computed_user_count(obj, field.path)

        value = self._resolve_attr(obj, field.path)

        if field.kind == 'choice_label':
            display_method = f'get_{field.path.replace("__", "_")}_display'
            if hasattr(obj, display_method):
                return str(getattr(obj, display_method)())
            if field.path.startswith('task__') and hasattr(obj.task, 'get_status_display'):
                return str(obj.task.get_status_display())
            return value
        if field.kind == 'user_display':
            if value is None:
                return ''
            return value.get_full_name() or value.username
        if field.kind == 'file_name':
            return Path(value.name).name if value else ''
        if field.kind == 'file_url':
            return value.url if value else ''
        if field.kind == 'file_type':
            suffix = Path(value.name).suffix.lower() if value else ''
            if suffix in VIDEO_EXTENSIONS:
                return 'video'
            return 'other'
        if field.kind == 'related_count':
            return value.count() if value is not None else 0
        if isinstance(value, Decimal):
            return str(value)
        if hasattr(value, 'isoformat'):
            return value.isoformat()
        return value

    def _computed_user_count(self, user, key: str) -> int:
        queryset = Task.objects.filter(assigned_to=user)
        if key.endswith('_completed'):
            return queryset.filter(status='completed').count()
        if key.endswith('_in_progress'):
            return queryset.filter(status='in_progress').count()
        if key.endswith('_pending'):
            return queryset.filter(status='pending').count()
        return queryset.count()

    def _split_filter_key(self, raw_key: str) -> tuple[str, str]:
        for lookup in sorted(LOOKUP_MAP.keys(), key=len, reverse=True):
            suffix = f'__{lookup}'
            if raw_key.endswith(suffix):
                return raw_key[:-len(suffix)], lookup
        return raw_key, 'eq'

    def _get_field(self, spec: ModelSpec, field_name: str) -> FieldSpec:
        field = spec.fields.get(field_name)
        if not field:
            raise PlatformDataError(f'字段不允许访问: {field_name}')
        return field

    def _resolve_attr(self, obj, path: str):
        if path == 'self':
            return obj
        value = obj
        for part in path.split('__'):
            if value is None:
                return None
            value = getattr(value, part)
        return value

    def _coerce_filter_value(self, value: Any, kind: str, lookup: str) -> Any:
        if lookup == 'in':
            if not isinstance(value, list):
                value = [value]
            return [self._coerce_filter_value(item, kind, 'eq') for item in value]
        if kind == 'boolean':
            if isinstance(value, bool):
                return value
            return str(value).lower() in {'1', 'true', 'yes', '是', '启用'}
        if kind in {'number'}:
            return self._safe_int(value, 0)
        if kind in {'date', 'datetime'} and isinstance(value, str):
            return parse_datetime(value) or parse_date(value) or value
        if lookup == 'isnull':
            return bool(value)
        return value

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _find_member_name(self, message: str) -> str:
        users = User.objects.filter(is_active=True).only('username', 'first_name', 'last_name', 'email')
        for user in users:
            candidates = [user.username, user.email, user.first_name, user.last_name, user.get_full_name()]
            for candidate in candidates:
                if candidate and candidate in message:
                    return candidate
        return ''
