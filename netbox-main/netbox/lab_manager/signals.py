from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from .models import Hardware, HardwareBorrowRecord, Task, TaskAttachment, Notification
from .models.notification import send_notification
from .choices import HardwareApprovalStatusChoices
from .models.borrow import BorrowStatusChoices


@receiver(pre_delete, sender=TaskAttachment)
def cleanup_attachment_file(sender, instance, **kwargs):
    """删除 TaskAttachment 记录时同步删除物理文件。"""
    if instance.file:
        instance.file.delete(save=False)


@receiver(post_delete, sender=HardwareBorrowRecord)
def restore_hardware_stock(sender, instance, **kwargs):
    """借出记录被删除时把占用的库存加回去。

    必须用信号实现：QuerySet.delete() 不会调用 Model.delete()。
    """
    if instance.status != BorrowStatusChoices.BORROWED or not instance.hardware_id:
        return
    try:
        with transaction.atomic():
            hardware = Hardware.objects.select_for_update().get(pk=instance.hardware_id)
            hardware.quantity += 1
            hardware.save(update_fields=['quantity', 'last_updated'])
    except Hardware.DoesNotExist:
        # 硬件本身正在被删除（级联），无需回补
        pass


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
def notify_hardware_approved(sender, instance, created=False, **kwargs):
    """硬件审批状态**发生变化**时通知提交人（新建不通知，避免批量导入刷屏）。"""
    previous = getattr(instance, '_previous_approval_status', None)
    if created or previous == instance.approval_status:
        return
    instance._previous_approval_status = instance.approval_status
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
