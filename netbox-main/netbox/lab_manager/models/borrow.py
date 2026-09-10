from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel
from users.models import User

from .hardware import Hardware


class BorrowStatusChoices(models.TextChoices):
    BORROWED = 'borrowed', _('借出中')
    RETURNED = 'returned', _('已归还')
    OVERDUE = 'overdue', _('已逾期')


class HardwareBorrowRecord(NetBoxModel):
    """硬件借用记录"""
    hardware = models.ForeignKey(
        to=Hardware,
        on_delete=models.CASCADE,
        related_name='borrow_records',
        verbose_name=_('硬件'),
        help_text=_('借出的硬件设备'),
    )
    borrower = models.ForeignKey(
        to=User,
        on_delete=models.CASCADE,
        related_name='borrowed_hardware',
        verbose_name=_('借用人'),
        help_text=_('借用该硬件的人员'),
    )
    borrow_date = models.DateTimeField(
        verbose_name=_('借出时间'),
        auto_now_add=True,
        help_text=_('借出操作的时间'),
    )
    expected_return_date = models.DateTimeField(
        verbose_name=_('预计归还时间'),
        null=True,
        blank=True,
        help_text=_('计划归还的日期'),
    )
    actual_return_date = models.DateTimeField(
        verbose_name=_('实际归还时间'),
        null=True,
        blank=True,
        help_text=_('实际归还的日期'),
    )
    status = models.CharField(
        verbose_name=_('状态'),
        max_length=20,
        choices=BorrowStatusChoices.choices,
        default=BorrowStatusChoices.BORROWED,
        db_index=True,
        help_text=_('借用状态：借出中 / 已归还 / 已逾期'),
    )
    purpose = models.TextField(
        verbose_name=_('借用用途'),
        blank=True,
        help_text=_('说明借用该硬件的目的'),
    )
    notes = models.TextField(
        verbose_name=_('备注'),
        blank=True,
        help_text=_('归还时可填写使用情况或损坏说明'),
    )

    class Meta(NetBoxModel.Meta):
        verbose_name = _('硬件借用记录')
        verbose_name_plural = _('硬件借用记录')
        ordering = ('-borrow_date',)

    def __str__(self):
        return f'{self.borrower} 借用 {self.hardware.name}'

    def get_absolute_url(self):
        return reverse('plugins:lab_manager:hardwareborrowrecord', args=[self.pk])

    @property
    def is_overdue(self):
        if self.status != BorrowStatusChoices.BORROWED:
            return False
        if self.expected_return_date:
            from django.utils import timezone
            return timezone.now() > self.expected_return_date
        return False

    def clean(self):
        super().clean()
        # 借出前校验可用库存（quantity 表示在库可用数量）
        if self._state.adding and self.status == BorrowStatusChoices.BORROWED and self.hardware_id:
            hardware = Hardware.objects.filter(pk=self.hardware_id).only('quantity').first()
            if hardware is not None and hardware.quantity < 1:
                raise ValidationError({'hardware': _('该硬件当前可用数量为 0，无法借出。')})

    def save(self, *args, **kwargs):
        """借出时扣减库存、归还时回补库存（行级锁 + 事务，避免并发超借）。"""
        creating = self._state.adding
        previous_status = None
        if not creating and self.pk:
            previous_status = (
                HardwareBorrowRecord.objects.filter(pk=self.pk)
                .values_list('status', flat=True).first()
            )
        becomes_borrowed = self.status == BorrowStatusChoices.BORROWED
        was_borrowed = previous_status == BorrowStatusChoices.BORROWED

        if becomes_borrowed and not was_borrowed:
            delta = -1
        elif was_borrowed and not becomes_borrowed:
            delta = 1
        else:
            delta = 0

        with transaction.atomic():
            if delta:
                hardware = Hardware.objects.select_for_update().get(pk=self.hardware_id)
                new_quantity = hardware.quantity + delta
                if new_quantity < 0:
                    raise ValidationError(_('该硬件当前可用数量为 0，无法借出。'))
                hardware.quantity = new_quantity
                hardware.save(update_fields=['quantity', 'last_updated'])
            super().save(*args, **kwargs)

    def mark_returned(self, notes=''):
        from django.utils import timezone
        self.status = BorrowStatusChoices.RETURNED
        self.actual_return_date = timezone.now()
        if notes:
            self.notes = notes
        self.save(update_fields=['status', 'actual_return_date', 'notes'])
