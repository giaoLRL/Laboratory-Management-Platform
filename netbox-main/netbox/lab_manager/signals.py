from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from .models import Hardware, HardwareBorrowRecord, Task, TaskAttachment, Notification
from .models.notification import send_notification
from .choices import HardwareApprovalStatusChoices


@receiver(pre_delete, sender=TaskAttachment)
def cleanup_attachment_file(sender, instance, **kwargs):
    """删除 TaskAttachment 记录时同步删除物理文件。"""
    if instance.file:
        instance.file.delete(save=False)


# ── 通知信号 ──

@receiver(post_save, sender=Task)
def notify_task_assigned(sender, instance, created, **kwargs):
    """新任务分配时通知执行人。"""
    if created and instance.assigned_to:
        send_notification(
            user=instance.assigned_to,
            title=f'新任务：{instance.title}',
            message=f'你被分配了一个新任务，优先级：{instance.get_priority_display()}。',
            link=instance.get_absolute_url(),
            notification_type='task',
        )


@receiver(post_save, sender=Hardware)
def notify_hardware_approved(sender, instance, **kwargs):
    """硬件审批状态变更时通知提交人。"""
    from django.db import transaction
    # 只在实际状态变更时通知
    if instance.approval_status == HardwareApprovalStatusChoices.APPROVED and instance.submitted_by:
        send_notification(
            user=instance.submitted_by,
            title=f'硬件已通过审核：{instance.name}',
            message=f'你提交的硬件 "{instance.name}" 已通过审核。',
            link=instance.get_absolute_url(),
            notification_type='approval',
        )
    elif instance.approval_status == HardwareApprovalStatusChoices.REJECTED and instance.submitted_by:
        send_notification(
            user=instance.submitted_by,
            title=f'硬件已驳回：{instance.name}',
            message=f'你提交的硬件 "{instance.name}" 已被驳回，理由：{instance.approval_note or "未填写"}。',
            link=instance.get_absolute_url(),
            notification_type='approval',
        )


@receiver(post_save, sender=HardwareBorrowRecord)
def notify_borrow_created(sender, instance, created, **kwargs):
    """借出记录创建时通知借用人。"""
    if created and instance.borrower:
        send_notification(
            user=instance.borrower,
            title=f'硬件借出确认：{instance.hardware.name}',
            message=f'你已借出 "{instance.hardware.name}"。{"请于 " + instance.expected_return_date.strftime("%Y-%m-%d") + " 前归还" if instance.expected_return_date else ""}',
            link=instance.get_absolute_url(),
            notification_type='borrow',
        )


# mark_task_completed has been moved to services.task_utils
# Keep a re-export here for backward compatibility
from .services.task_utils import mark_task_completed  # noqa: F401, E402
