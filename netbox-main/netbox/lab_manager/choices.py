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
