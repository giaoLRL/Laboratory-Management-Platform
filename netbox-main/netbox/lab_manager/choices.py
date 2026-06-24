from utilities.choices import ChoiceSet


class HardwareCategoryChoices(ChoiceSet):
    key = 'Hardware.category'

    MCU = 'mcu'
    SENSOR = 'sensor'
    POWER = 'power'
    INSTRUMENT = 'instrument'
    TOOL = 'tool'
    WIRE = 'wire'
    MODULE = 'module'
    OTHER = 'other'

    CHOICES = [
        (MCU, '单片机/开发板'),
        (SENSOR, '传感器'),
        (POWER, '电源/电池'),
        (INSTRUMENT, '仪器仪表'),
        (TOOL, '工具'),
        (WIRE, '线材/连接器'),
        (MODULE, '模块/外设'),
        (OTHER, '其他'),
    ]


class HardwareStatusChoices(ChoiceSet):
    key = 'Hardware.status'

    IN_USE = 'in_use'
    IDLE = 'idle'
    REPAIR = 'repair'
    SCRAPPED = 'scrapped'

    CHOICES = [
        (IN_USE, '在用'),
        (IDLE, '闲置'),
        (REPAIR, '维修中'),
        (SCRAPPED, '已报废'),
    ]


class HardwareApprovalStatusChoices(ChoiceSet):
    key = 'Hardware.approval_status'

    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'

    CHOICES = [
        (PENDING, '待审核'),
        (APPROVED, '已通过'),
        (REJECTED, '已驳回'),
    ]


class TaskStatusChoices(ChoiceSet):
    key = 'Task.status'

    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'

    CHOICES = [
        (PENDING, '待开始'),
        (IN_PROGRESS, '进行中'),
        (COMPLETED, '已完成'),
    ]


class AgentToolTypeChoices(ChoiceSet):
    key = 'AgentTool.tool_type'

    PLATFORM_QUERY = 'platform_query'
    TASK_CREATE = 'task_create'
    VIDEO_SEARCH = 'video_search'
    HARDWARE_GAP = 'hardware_gap'
    DESCRIBE_DATA = 'describe_data'
    CUSTOM_FUNCTION = 'custom_function'

    CHOICES = [
        (PLATFORM_QUERY, '平台数据查询'),
        (TASK_CREATE, '任务创建'),
        (VIDEO_SEARCH, '视频检索'),
        (HARDWARE_GAP, '硬件缺口分析'),
        (DESCRIBE_DATA, '数据模型描述'),
        (CUSTOM_FUNCTION, '自定义函数'),
    ]


class AgentToolCategoryChoices(ChoiceSet):
    key = 'AgentTool.category'

    DATA_QUERY = 'data_query'
    TASK_MANAGEMENT = 'task_management'
    ANALYSIS = 'analysis'
    SYSTEM = 'system'

    CHOICES = [
        (DATA_QUERY, '数据查询'),
        (TASK_MANAGEMENT, '任务管理'),
        (ANALYSIS, '分析诊断'),
        (SYSTEM, '系统管理'),
    ]


class TaskPriorityChoices(ChoiceSet):
    key = 'Task.priority'

    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    URGENT = 'urgent'

    CHOICES = [
        (LOW, '低'),
        (MEDIUM, '中'),
        (HIGH, '高'),
        (URGENT, '紧急'),
    ]
