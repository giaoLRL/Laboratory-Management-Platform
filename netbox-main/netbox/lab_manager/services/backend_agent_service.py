from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

from django.db.models import Count, Q, Sum
from django.utils import timezone

from ..choices import HardwareApprovalStatusChoices, HardwareCategoryChoices, HardwareStatusChoices, TaskStatusChoices
from ..models import Hardware, HardwareImportBatch, Task, TaskAttachment


VIDEO_EXTENSIONS = {'.mp4', '.webm', '.avi', '.mov', '.mkv', '.m4v'}
STOP_WORDS = {
    '现在', '目前', '实验室', '帮我', '一下', '看看', '查询', '检索', '读取', '统计', '列出', '告诉我',
    '有哪些', '有什么', '多少', '情况', '资源', '硬件', '库存', '设备', '任务', '最近', '完成',
    '上传', '视频', '附件', '列表', '导入', '批量', '两段式', '应该', '怎么', '使用',
}
GENERIC_HARDWARE_TERMS = {
    '开发板', '单片机', '主控', '传感器', '模块', '电源', '电池', '工具', '线材', '设备', '库存', '硬件',
}
MESSAGE_NOISE_PATTERNS = (
    '现在实验室', '当前实验室', '实验室里', '实验室内', '实验室', '帮我', '请帮我', '看一下', '看一看',
    '看看', '查询', '检索', '读取', '统计', '列出', '告诉我', '有哪些', '有什么', '多少', '情况',
    '资源', '最近', '已完成', '完成的', '完成时', '任务里', '任务中的',
)
PROJECT_TEMPLATES = (
    {
        'keywords': ('温室', '农业', '环境监测', '智能温室', '种植'),
        'requirements': [
            {'name': '主控开发板', 'category': HardwareCategoryChoices.MCU, 'keywords': ['stm32', 'esp32', 'arduino', '开发板'], 'required_quantity': 1},
            {'name': '温湿度传感器', 'category': HardwareCategoryChoices.SENSOR, 'keywords': ['温湿度', 'dht', 'sht'], 'required_quantity': 2},
            {'name': '土壤湿度传感器', 'category': HardwareCategoryChoices.SENSOR, 'keywords': ['土壤湿度', '土壤'], 'required_quantity': 2},
            {'name': '光照传感器', 'category': HardwareCategoryChoices.SENSOR, 'keywords': ['光照', '照度', '光敏'], 'required_quantity': 1},
            {'name': '继电器或驱动模块', 'category': HardwareCategoryChoices.MODULE, 'keywords': ['继电器', '驱动', '模块'], 'required_quantity': 1},
            {'name': '供电模块', 'category': HardwareCategoryChoices.POWER, 'keywords': ['电源', '电池', '适配器'], 'required_quantity': 1},
            {'name': '连接线材', 'category': HardwareCategoryChoices.WIRE, 'keywords': ['杜邦线', '线材', '连接器'], 'required_quantity': 1},
        ],
    },
    {
        'keywords': ('小车', '机器人', '避障', '巡线'),
        'requirements': [
            {'name': '主控开发板', 'category': HardwareCategoryChoices.MCU, 'keywords': ['stm32', 'esp32', 'arduino', '开发板'], 'required_quantity': 1},
            {'name': '电机驱动模块', 'category': HardwareCategoryChoices.MODULE, 'keywords': ['驱动', 'l298', '电机驱动'], 'required_quantity': 1},
            {'name': '电源模块', 'category': HardwareCategoryChoices.POWER, 'keywords': ['电池', '锂电', '电源'], 'required_quantity': 1},
            {'name': '传感器组件', 'category': HardwareCategoryChoices.SENSOR, 'keywords': ['超声波', '红外', '循迹', '传感器'], 'required_quantity': 2},
            {'name': '结构工具', 'category': HardwareCategoryChoices.TOOL, 'keywords': ['螺丝刀', '焊台', '工具'], 'required_quantity': 1},
        ],
    },
    {
        'keywords': ('摄像头', '视觉', '图像', '识别', '监控'),
        'requirements': [
            {'name': '视觉主控板', 'category': HardwareCategoryChoices.MCU, 'keywords': ['树莓派', 'jetson', 'esp32', '开发板'], 'required_quantity': 1},
            {'name': '摄像头模块', 'category': HardwareCategoryChoices.MODULE, 'keywords': ['摄像头', 'camera', 'ov2640'], 'required_quantity': 1},
            {'name': '存储与供电', 'category': HardwareCategoryChoices.POWER, 'keywords': ['电源', '电池', '适配器'], 'required_quantity': 1},
            {'name': '连接线材', 'category': HardwareCategoryChoices.WIRE, 'keywords': ['排线', '杜邦线', '线材'], 'required_quantity': 1},
        ],
    },
)


@dataclass
class BackendAgentResponse:
    handled: bool
    intent: str = ''
    answer_text: str = ''
    data: dict[str, Any] = field(default_factory=dict)
    raw_payload: dict[str, Any] = field(default_factory=dict)


class BackendAgentService:
    def process_message(self, *, user, message: str) -> BackendAgentResponse:
        normalized_message = str(message or '').strip()
        if not normalized_message:
            return BackendAgentResponse(handled=False)

        intent = self._detect_intent(normalized_message)

        if intent == 'task_videos':
            data = self._search_task_videos(user, normalized_message)
            return BackendAgentResponse(
                handled=True,
                intent=intent,
                answer_text=self._format_task_video_answer(data),
                data=data,
                raw_payload={'intent': intent, 'data': data},
            )

        if intent == 'task_summary':
            data = self._search_tasks(user, normalized_message)
            return BackendAgentResponse(
                handled=True,
                intent=intent,
                answer_text=self._format_task_summary_answer(data),
                data=data,
                raw_payload={'intent': intent, 'data': data},
            )

        if intent == 'hardware_gap':
            data = self._analyze_hardware_gap(user, normalized_message)
            return BackendAgentResponse(
                handled=True,
                intent=intent,
                answer_text=self._format_hardware_gap_answer(data),
                data=data,
                raw_payload={'intent': intent, 'data': data},
            )

        if intent == 'import_guide':
            data = self._build_import_guide(user)
            return BackendAgentResponse(
                handled=True,
                intent=intent,
                answer_text=self._format_import_guide_answer(data),
                data=data,
                raw_payload={'intent': intent, 'data': data},
            )

        if intent == 'hardware_search':
            data = self._search_hardware(user, normalized_message)
            return BackendAgentResponse(
                handled=True,
                intent=intent,
                answer_text=self._format_hardware_answer(data),
                data=data,
                raw_payload={'intent': intent, 'data': data},
            )

        data = self._build_overview(user)
        return BackendAgentResponse(
            handled=True,
            intent='overview',
            answer_text=self._format_overview_answer(data),
            data=data,
            raw_payload={'intent': 'overview', 'data': data},
        )

    def _detect_intent(self, message: str) -> str:
        if self._contains_any(message, ('导入', '批量上传', '批量导入', '一键上传', '一键导入', '两段式')):
            return 'import_guide'
        if self._contains_any(message, ('视频', '录像', '录屏', '附件')) and self._contains_any(message, ('任务', '完成', '已完成')):
            return 'task_videos'
        if self._contains_any(message, ('任务', '待办', '进度', '负责人', '执行人', '成员')):
            return 'task_summary'
        if self._contains_any(message, ('缺什么', '缺哪些', '还缺', '采购', '购买', '方案', '做一个', '做个', '产品', '项目', '系统')):
            return 'hardware_gap'
        if self._contains_any(message, ('硬件', '库存', '资源', '设备', '开发板', '模块', '传感器', '有哪些', '有什么')):
            return 'hardware_search'
        return 'overview'

    def _visible_hardware_queryset(self, user):
        queryset = Hardware.objects.all().select_related('custodian', 'submitted_by')
        if not user.is_superuser:
            queryset = queryset.filter(
                Q(approval_status=HardwareApprovalStatusChoices.APPROVED) |
                Q(submitted_by=user)
            )
        return queryset

    def _visible_task_queryset(self, user):
        queryset = Task.objects.all().select_related('created_by', 'assigned_to')
        if not user.is_superuser:
            queryset = queryset.filter(Q(created_by=user) | Q(assigned_to=user))
        return queryset

    def _search_hardware(self, user, message: str) -> dict[str, Any]:
        queryset = self._visible_hardware_queryset(user)
        keywords = self._extract_keywords(message)
        category = self._match_hardware_category(message)
        if category:
            queryset = queryset.filter(category=category)

        filtered_keywords = [keyword for keyword in keywords if keyword not in GENERIC_HARDWARE_TERMS]

        for keyword in filtered_keywords:
            queryset = queryset.filter(
                Q(name__icontains=keyword) |
                Q(model_number__icontains=keyword) |
                Q(manufacturer__icontains=keyword) |
                Q(storage_location__icontains=keyword) |
                Q(remarks__icontains=keyword)
            )

        total_count = queryset.count()
        total_quantity = queryset.aggregate(total=Sum('quantity')).get('total') or 0
        category_summary = list(
            queryset.values('category').annotate(item_count=Count('id'), total_quantity=Sum('quantity')).order_by('-total_quantity', 'category')[:8]
        )
        items = []
        for hardware in queryset.order_by('name')[:12]:
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
                    'approval_status': hardware.approval_status,
                    'purchase_link': hardware.purchase_link,
                }
            )

        return {
            'keywords': filtered_keywords,
            'category': category,
            'total_count': total_count,
            'total_quantity': total_quantity,
            'category_summary': category_summary,
            'items': items,
        }

    def _analyze_hardware_gap(self, user, message: str) -> dict[str, Any]:
        requirements = self._build_requirements_from_message(message)
        queryset = self._visible_hardware_queryset(user).exclude(status=HardwareStatusChoices.SCRAPPED)
        matched = []
        missing = []

        for requirement in requirements:
            item_queryset = queryset
            category = requirement.get('category')
            if category:
                item_queryset = item_queryset.filter(category=category)

            keyword_query = Q()
            for keyword in requirement.get('keywords') or []:
                keyword_query |= (
                    Q(name__icontains=keyword) |
                    Q(model_number__icontains=keyword) |
                    Q(manufacturer__icontains=keyword) |
                    Q(remarks__icontains=keyword)
                )
            if keyword_query:
                item_queryset = item_queryset.filter(keyword_query)

            available_quantity = item_queryset.aggregate(total=Sum('quantity')).get('total') or 0
            gap_quantity = max(int(requirement['required_quantity']) - int(available_quantity), 0)
            recommendation_items = []
            for hardware in item_queryset.order_by('-quantity', 'name')[:3]:
                recommendation_items.append(
                    {
                        'id': hardware.pk,
                        'name': hardware.name,
                        'quantity': hardware.quantity,
                        'status_label': hardware.get_status_display(),
                        'purchase_link': hardware.purchase_link,
                    }
                )

            item_data = {
                'name': requirement['name'],
                'category': category,
                'category_label': self._get_hardware_category_label(category),
                'required_quantity': int(requirement['required_quantity']),
                'available_quantity': int(available_quantity),
                'gap_quantity': int(gap_quantity),
                'keywords': requirement.get('keywords') or [],
                'recommendation_items': recommendation_items,
            }
            if gap_quantity > 0:
                missing.append(item_data)
            else:
                matched.append(item_data)

        return {
            'project_name': self._extract_project_name(message),
            'requirements': requirements,
            'matched': matched,
            'missing': missing,
        }

    def _search_tasks(self, user, message: str) -> dict[str, Any]:
        queryset = self._visible_task_queryset(user)
        requested_status = None
        if '已完成' in message or '完成' in message:
            requested_status = TaskStatusChoices.COMPLETED
        elif '进行中' in message:
            requested_status = TaskStatusChoices.IN_PROGRESS
        elif '待开始' in message or '待办' in message:
            requested_status = TaskStatusChoices.PENDING
        if requested_status:
            queryset = queryset.filter(status=requested_status)

        date_from = self._parse_date_from_message(message)
        if date_from:
            if requested_status == TaskStatusChoices.COMPLETED:
                queryset = queryset.filter(completed_at__gte=date_from)
            else:
                queryset = queryset.filter(created__gte=date_from)

        usernames = self._find_usernames_in_message(message, queryset.values_list('assigned_to__username', flat=True))
        if usernames:
            queryset = queryset.filter(assigned_to__username__in=usernames)

        keyword_fragments = self._extract_keywords(message)
        keyword_query = Q()
        for keyword in keyword_fragments:
            keyword_query |= (
                Q(title__icontains=keyword) |
                Q(description__icontains=keyword) |
                Q(completion_note__icontains=keyword)
            )
        if keyword_query:
            queryset = queryset.filter(keyword_query)

        total = queryset.count()
        items = []
        for task in queryset.order_by('-completed_at', '-created')[:10]:
            items.append(
                {
                    'id': task.pk,
                    'title': task.title,
                    'status': task.status,
                    'status_label': task.get_status_display(),
                    'priority': task.priority,
                    'priority_label': task.get_priority_display(),
                    'assigned_to': task.assigned_to.username,
                    'created_by': task.created_by.username,
                    'deadline': task.deadline.isoformat() if task.deadline else None,
                    'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                    'completion_note': task.completion_note,
                }
            )

        status_summary = list(queryset.values('status').annotate(count=Count('id')).order_by('status'))
        return {
            'total': total,
            'requested_status': requested_status,
            'date_from': date_from.isoformat() if date_from else None,
            'items': items,
            'status_summary': status_summary,
        }

    def _search_task_videos(self, user, message: str) -> dict[str, Any]:
        queryset = self._visible_task_queryset(user).filter(status=TaskStatusChoices.COMPLETED)
        date_from = self._parse_date_from_message(message)
        if date_from:
            queryset = queryset.filter(completed_at__gte=date_from)

        keyword_fragments = self._extract_keywords(message)
        keyword_query = Q()
        for keyword in keyword_fragments:
            keyword_query |= (
                Q(title__icontains=keyword) |
                Q(description__icontains=keyword) |
                Q(completion_note__icontains=keyword)
            )
        if keyword_query:
            queryset = queryset.filter(keyword_query)

        tasks = list(queryset.order_by('-completed_at', '-created')[:20])
        attachments = TaskAttachment.objects.filter(task__in=tasks).select_related('task', 'uploaded_by').order_by('-created')

        results = []
        total_videos = 0
        videos_by_task_id: dict[int, list[dict[str, Any]]] = {}
        for attachment in attachments:
            file_name = attachment.file.name or ''
            if Path(file_name).suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            videos_by_task_id.setdefault(attachment.task_id, []).append(
                {
                    'attachment_id': attachment.pk,
                    'file_name': Path(file_name).name,
                    'file_url': attachment.file.url if attachment.file else '',
                    'remark': attachment.remark,
                    'uploaded_by': attachment.uploaded_by.username,
                    'created': attachment.created.isoformat() if attachment.created else None,
                }
            )
            total_videos += 1

        for task in tasks:
            task_videos = videos_by_task_id.get(task.pk) or []
            if not task_videos:
                continue
            results.append(
                {
                    'task_id': task.pk,
                    'task_title': task.title,
                    'assigned_to': task.assigned_to.username,
                    'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                    'videos': task_videos,
                }
            )

        return {
            'date_from': date_from.isoformat() if date_from else None,
            'task_count': len(results),
            'video_count': total_videos,
            'tasks': results,
        }

    def _build_import_guide(self, user) -> dict[str, Any]:
        latest_batch = HardwareImportBatch.objects.filter(created_by=user).order_by('-created').first()
        return {
            'is_admin': bool(user.is_superuser),
            'latest_batch': (
                {
                    'batch_id': latest_batch.batch_id,
                    'status': latest_batch.status,
                    'summary': latest_batch.result_summary,
                    'created': latest_batch.created.isoformat() if latest_batch.created else None,
                }
                if latest_batch else None
            ),
            'steps': [
                '先准备 JSON / CSV / Excel 数据，至少包含 name、category、quantity。',
                '先执行 validate 预校验，系统会检查重复项、必填项和非法状态。',
                '确认 valid_items 后，再执行 commit 正式入库，避免脏数据直接写入库存。',
            ],
        }

    def _build_overview(self, user) -> dict[str, Any]:
        hardware_queryset = self._visible_hardware_queryset(user)
        task_queryset = self._visible_task_queryset(user)
        completed_recent = task_queryset.filter(
            status=TaskStatusChoices.COMPLETED,
            completed_at__gte=timezone.now() - timedelta(days=7),
        ).count()
        return {
            'hardware_total': hardware_queryset.count(),
            'hardware_quantity': hardware_queryset.aggregate(total=Sum('quantity')).get('total') or 0,
            'task_total': task_queryset.count(),
            'task_completed_recent': completed_recent,
            'top_categories': list(
                hardware_queryset.values('category').annotate(total_quantity=Sum('quantity')).order_by('-total_quantity', 'category')[:5]
            ),
        }

    def _format_hardware_answer(self, data: dict[str, Any]) -> str:
        if data['total_count'] == 0:
            if data['keywords']:
                return f"🤖 抱歉，我翻遍了库存，没有找到与“**{', '.join(data['keywords'])}**”相关的硬件资源。要不换个型号或品牌再试试？"
            return '🤖 当前你可见范围内还没有硬件资源记录哦。'

        lines = [
            f"🤖 没问题！我已经为你找到了 **{data['total_count']}** 条相关的硬件记录，合计 **{data['total_quantity']}** 件。",
            ""
        ]
        if data['category_summary']:
            summary_parts = []
            for entry in data['category_summary'][:5]:
                summary_parts.append(f"**{self._get_hardware_category_label(entry['category'])}**({entry['total_quantity']}件)")
            lines.append(f"📦 **类别概览**：{'，'.join(summary_parts)}")
            lines.append("")
            
        if data['items']:
            lines.append('📋 **硬件明细如下**：')
            for item in data['items'][:6]:
                detail_parts = [f"**{item['name']}**"]
                if item['model_number']:
                    detail_parts.append(f"型号:{item['model_number']}")
                detail_parts.append(f"库存:**{item['quantity']}件**")
                detail_parts.append(f"状态:{item['status_label']}")
                if item['storage_location']:
                    detail_parts.append(f"位置:{item['storage_location']}")
                lines.append(f"- {' | '.join(detail_parts)}")
            
            if data['total_count'] > 6:
                lines.append(f"\n*...还有 {data['total_count'] - 6} 条记录未展示，可以通过更具体的关键词进行搜索。*")
                
        return '\n'.join(lines)

    def _format_hardware_gap_answer(self, data: dict[str, Any]) -> str:
        lines = []
        project_name = data.get('project_name') or '当前项目'
        lines.append(f"🤖 你好！我已经根据你的需求“**{project_name}**”分析了实验室当前的库存情况。")
        lines.append("")
        
        if data['matched']:
            lines.append("### ✅ 库存充足可直接领用的物料：")
            for item in data['matched'][:6]:
                lines.append(
                    f"- **{item['name']}**：你需要 {item['required_quantity']} 个，当前库存有 {item['available_quantity']} 个。完美覆盖！"
                )
            lines.append("")

        if data['missing']:
            lines.append("### ⚠️ 存在缺口需要采购的物料：")
            for item in data['missing'][:8]:
                line = f"- **{item['name']}**：你需要 {item['required_quantity']} 个，但当前库存只有 {item['available_quantity']} 个（**缺口：{item['gap_quantity']}**）。"
                if item['recommendation_items']:
                    recommendations = [entry['name'] for entry in item['recommendation_items'][:2]]
                    line = f"{line}\n  💡 *平替建议：实验室有相近物料（{', '.join(recommendations)}），可以看看能否替代。*"
                lines.append(line)
            lines.append("")

        if not data['matched'] and not data['missing']:
            lines.append("🤔 抱歉，我暂时无法从你的描述中提炼出具体的物料清单。你可以尝试描述得更具体一些，比如“做一个基于ESP32的智能温室监测系统”或“巡线避障小车”。")
        else:
            lines.append("📝 **下一步建议**：如果你确认需要采购以上缺口物料，我可以帮你把它们整理成采购申请清单的格式。需要我继续吗？")
            
        return '\n'.join(lines)

    def _format_task_summary_answer(self, data: dict[str, Any]) -> str:
        if data['total'] == 0:
            return '🤖 没有查询到匹配的任务哦。你可以尝试补充具体的任务状态、负责人或时间范围。'

        lines = [f"🤖 好的，我为你找到了 **{data['total']}** 个任务。", ""]
        if data['status_summary']:
            summary_parts = [f"**{self._get_task_status_label(item['status'])}**({item['count']}个)" for item in data['status_summary']]
            lines.append(f"📊 **状态分布**：{'，'.join(summary_parts)}")
            lines.append("")
            
        lines.append('📋 **任务明细**：')
        for task in data['items'][:6]:
            detail = f"- **{task['title']}** | 状态: {task['status_label']} | 负责人: {task['assigned_to']}"
            if task['completed_at']:
                detail = f"{detail} | 完成时间: {task['completed_at'][:10]}"
            elif task['deadline']:
                detail = f"{detail} | 截止时间: {task['deadline'][:10]}"
            lines.append(detail)
            
        if data['total'] > 6:
            lines.append(f"\n*...还有 {data['total'] - 6} 个任务未展示，可以通过关键词进一步筛选。*")
            
        return '\n'.join(lines)

    def _format_task_video_answer(self, data: dict[str, Any]) -> str:
        if data['video_count'] == 0:
            return '🤖 找了一圈，没有找到匹配的任务视频附件。你可以试着放宽时间范围或换一个关键词。'

        lines = [f"🤖 我找到了 **{data['task_count']}** 个相关任务，共提取出 **{data['video_count']}** 个视频附件：", ""]
        for task in data['tasks'][:5]:
            lines.append(f"📁 **任务：{task['task_title']}** (负责人: {task['assigned_to']})")
            for video in task['videos'][:2]:
                lines.append(f"  - 🎬 `{video['file_name']}` [点击查看]({video['file_url'] or '#'})")
            lines.append("")
        return '\n'.join(lines)

    def _format_import_guide_answer(self, data: dict[str, Any]) -> str:
        lines = ["🤖 **关于两段式硬件导入的说明**", ""]
        if data['is_admin']:
            lines.append('✅ 你当前拥有**管理员权限**，可以直接执行导入操作。')
        else:
            lines.append('⚠️ 你当前**不是管理员**。我可以在聊天里帮你整理数据，但正式提交入库需要管理员执行。')
            
        lines.append("")
        lines.append('**推荐的操作流程**：')
        for step in data['steps']:
            lines.append(f"1. {step}")
            
        if data['latest_batch']:
            lines.append("")
            latest_batch = data['latest_batch']
            lines.append(
                f"📌 **最近一次导入批次**：`{latest_batch['batch_id']}` | 状态: **{latest_batch['status']}**"
            )
            
        lines.append("")
        lines.append('💡 **提示**：你可以直接把待导入的 JSON/CSV 数据文本发给我，我会帮你校验和整理。')
        return '\n'.join(lines)

    def _format_overview_answer(self, data: dict[str, Any]) -> str:
        category_parts = []
        for item in data['top_categories']:
            category_parts.append(f"**{self._get_hardware_category_label(item['category'])}**({item['total_quantity']}件)")
        category_text = '，'.join(category_parts) if category_parts else '暂无分类统计'
        
        return (
            f"🤖 你好！我是实验室智能体助手。\n\n"
            f"📊 **当前概况**：\n"
            f"- 硬件资源：共 **{data['hardware_total']}** 条记录，合计 **{data['hardware_quantity']}** 件。\n"
            f"- 任务进度：共有 **{data['task_total']}** 个任务，最近 7 天已完成 **{data['task_completed_recent']}** 个。\n\n"
            f"📦 **硬件类别概览**：\n{category_text}\n\n"
            f"💡 **你可以这样问我**：\n"
            f"- “现在实验室有哪些开发板？”\n"
            f"- “我想做一个智能温室监测系统，看看缺哪些硬件”\n"
            f"- “帮我找最近7天已完成任务里的视频”\n"
            f"- “解释一下两段式硬件导入怎么用”"
        )

    @staticmethod
    def _contains_any(message: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in message for keyword in keywords)

    def _extract_keywords(self, message: str) -> list[str]:
        normalized_message = message
        for noise in MESSAGE_NOISE_PATTERNS:
            normalized_message = normalized_message.replace(noise, ' ')
        tokens: list[str] = []
        ascii_tokens = re.findall(r'[A-Za-z][A-Za-z0-9\-_+/.]{1,}', normalized_message)
        chinese_tokens = re.findall(r'[\u4e00-\u9fff]{2,8}', normalized_message)
        for token in ascii_tokens + chinese_tokens:
            clean_token = token.strip().lower()
            if not clean_token or clean_token in STOP_WORDS:
                continue
            if clean_token not in tokens:
                tokens.append(clean_token)
        return tokens[:6]

    def _match_hardware_category(self, message: str) -> str | None:
        category_keywords = {
            HardwareCategoryChoices.MCU: ('开发板', '单片机', '主控', 'mcu', 'stm32', 'esp32', 'arduino'),
            HardwareCategoryChoices.SENSOR: ('传感器', '检测', '温湿度', '超声波', '土壤'),
            HardwareCategoryChoices.POWER: ('电源', '电池', '供电', '适配器'),
            HardwareCategoryChoices.INSTRUMENT: ('仪器', '示波器', '万用表'),
            HardwareCategoryChoices.TOOL: ('工具', '焊台', '螺丝刀'),
            HardwareCategoryChoices.WIRE: ('线材', '杜邦线', '排线', '连接器'),
            HardwareCategoryChoices.MODULE: ('模块', '继电器', '驱动', '摄像头'),
        }
        lowered_message = message.lower()
        for category, keywords in category_keywords.items():
            if any(keyword in lowered_message for keyword in keywords):
                return category
        return None

    def _build_requirements_from_message(self, message: str) -> list[dict[str, Any]]:
        lowered_message = message.lower()
        for template in PROJECT_TEMPLATES:
            if any(keyword in lowered_message for keyword in template['keywords']):
                return template['requirements']

        requirements = []
        category = self._match_hardware_category(message)
        extracted_keywords = self._extract_keywords(message)
        if category or extracted_keywords:
            requirements.append(
                {
                    'name': self._extract_project_name(message) or '核心物料',
                    'category': category or HardwareCategoryChoices.MODULE,
                    'keywords': extracted_keywords or ['模块'],
                    'required_quantity': 1,
                }
            )
        return requirements

    @staticmethod
    def _extract_project_name(message: str) -> str:
        cleaned_message = re.sub(r'[，。！？,.!?]', ' ', message).strip()
        cleaned_message = re.sub(r'^(我想做(一个)?|想做(一个)?|帮我分析|看看|请分析)', '', cleaned_message).strip()
        return cleaned_message[:40] or '当前项目'

    @staticmethod
    def _parse_date_from_message(message: str):
        match = re.search(r'最近\s*(\d+)\s*天', message)
        if match:
            return timezone.now() - timedelta(days=int(match.group(1)))
        if '最近一周' in message or '近一周' in message:
            return timezone.now() - timedelta(days=7)
        if '最近一个月' in message or '近一个月' in message:
            return timezone.now() - timedelta(days=30)
        if '今天' in message:
            return timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return None

    @staticmethod
    def _find_usernames_in_message(message: str, usernames) -> list[str]:
        found = []
        for username in usernames:
            if username and str(username) in message:
                found.append(str(username))
        return found

    @staticmethod
    def _get_hardware_category_label(category: str | None) -> str:
        if not category:
            return '未分类'
        return dict(HardwareCategoryChoices.CHOICES).get(category, category)

    @staticmethod
    def _get_task_status_label(status: str) -> str:
        return dict(TaskStatusChoices.CHOICES).get(status, status)
