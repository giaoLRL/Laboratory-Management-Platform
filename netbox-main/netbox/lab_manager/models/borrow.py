from django.db import models
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
        from django.utils import timezone
        if self.status != self.BorrowStatusChoices.BORROWED:
            return False
        if self.expected_return_date:
            return timezone.now() > self.expected_return_date
        return False

    def mark_returned(self, notes=''):
        from django.utils import timezone
        self.status = self.BorrowStatusChoices.RETURNED
        self.actual_return_date = timezone.now()
        if notes:
            self.notes = notes
        self.save(update_fields=['status', 'actual_return_date', 'notes'])
