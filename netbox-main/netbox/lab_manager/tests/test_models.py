"""模型层测试：借出库存、逾期属性、审批状态快照。"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from lab_manager.models import Hardware, HardwareBorrowRecord, Notification, Task
from lab_manager.models.borrow import BorrowStatusChoices


class HardwareBorrowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='borrower', password='x')
        self.hardware = Hardware.objects.create(name='测试开发板', quantity=2)

    def test_is_overdue_without_attribute_error(self):
        """回归：borrow.py 曾用 self.BorrowStatusChoices 导致 AttributeError。"""
        record = HardwareBorrowRecord.objects.create(
            hardware=self.hardware, borrower=self.user,
            expected_return_date=timezone.now() - timezone.timedelta(days=1),
        )
        self.assertTrue(record.is_overdue)

        record.expected_return_date = timezone.now() + timezone.timedelta(days=1)
        record.save(update_fields=['expected_return_date'])
        self.assertFalse(record.is_overdue)

    def test_borrow_decrements_and_return_restores_stock(self):
        record = HardwareBorrowRecord.objects.create(hardware=self.hardware, borrower=self.user)
        self.hardware.refresh_from_db()
        self.assertEqual(self.hardware.quantity, 1)

        record.mark_returned(notes='归还')
        self.hardware.refresh_from_db()
        self.assertEqual(self.hardware.quantity, 2)
        self.assertEqual(record.status, BorrowStatusChoices.RETURNED)
        self.assertIsNotNone(record.actual_return_date)

    def test_queryset_delete_restores_stock(self):
        """回归：QuerySet.delete() 不会走 Model.delete()，必须由信号回补库存。"""
        record = HardwareBorrowRecord.objects.create(hardware=self.hardware, borrower=self.user)
        self.hardware.refresh_from_db()
        self.assertEqual(self.hardware.quantity, 1)

        HardwareBorrowRecord.objects.filter(pk=record.pk).delete()
        self.hardware.refresh_from_db()
        self.assertEqual(self.hardware.quantity, 2)

    def test_cannot_borrow_without_stock(self):
        self.hardware.quantity = 0
        self.hardware.save(update_fields=['quantity'])
        record = HardwareBorrowRecord(hardware=self.hardware, borrower=self.user)
        with self.assertRaises(ValidationError):
            record.full_clean()

    def test_history_is_kept_after_return(self):
        record = HardwareBorrowRecord.objects.create(hardware=self.hardware, borrower=self.user)
        record.mark_returned()
        self.assertTrue(HardwareBorrowRecord.objects.filter(pk=record.pk).exists())


class NotificationSignalTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username='admin2', password='x', is_superuser=True)
        self.member = get_user_model().objects.create_user(username='member2', password='x')

    def test_task_assignment_notifies_assignee(self):
        Task.objects.create(title='新任务', description='d', created_by=self.admin, assigned_to=self.member)
        self.assertTrue(
            Notification.objects.filter(user=self.member, notification_type='task').exists()
        )

    def test_hardware_notification_only_on_status_change(self):
        hardware = Hardware.objects.create(
            name='待审硬件', quantity=1, submitted_by=self.member, approval_status='pending',
        )
        self.assertFalse(Notification.objects.filter(user=self.member, notification_type='approval').exists())

        hardware.approval_note = '改备注不改状态'
        hardware.save()
        self.assertFalse(
            Notification.objects.filter(user=self.member, notification_type='approval').exists(),
            '状态未变化时不应重复发送审批通知',
        )

        hardware.approval_status = 'approved'
        hardware.save()
        self.assertEqual(Notification.objects.filter(user=self.member, notification_type='approval').count(), 1)

    def test_borrow_notifies_borrower(self):
        hardware = Hardware.objects.create(name='借用通知硬件', quantity=1)
        HardwareBorrowRecord.objects.create(hardware=hardware, borrower=self.member)
        self.assertTrue(Notification.objects.filter(user=self.member, notification_type='borrow').exists())
