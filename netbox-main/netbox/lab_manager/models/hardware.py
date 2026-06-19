from django.db import models
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel
from users.models import User

from ..choices import HardwareApprovalStatusChoices, HardwareCategoryChoices, HardwareStatusChoices


class Hardware(NetBoxModel):
    """硬件资源"""
    name = models.CharField(
        verbose_name=_('名称'),
        max_length=200,
    )
    category = models.CharField(
        verbose_name=_('类别'),
        max_length=30,
        choices=HardwareCategoryChoices,
        default=HardwareCategoryChoices.MCU,
    )
    model_number = models.CharField(
        verbose_name=_('型号'),
        max_length=100,
        blank=True,
    )
    manufacturer = models.CharField(
        verbose_name=_('厂家/品牌'),
        max_length=100,
        blank=True,
    )
    quantity = models.PositiveIntegerField(
        verbose_name=_('数量'),
        default=1,
    )
    unit_price = models.DecimalField(
        verbose_name=_('单价'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    purchase_date = models.DateField(
        verbose_name=_('购买日期'),
        null=True,
        blank=True,
    )
    purchase_link = models.URLField(
        verbose_name=_('购买链接'),
        max_length=500,
        blank=True,
    )
    status = models.CharField(
        verbose_name=_('状态'),
        max_length=20,
        choices=HardwareStatusChoices,
        default=HardwareStatusChoices.IN_USE,
    )
    storage_location = models.CharField(
        verbose_name=_('存放位置'),
        max_length=100,
        blank=True,
    )
    custodian = models.ForeignKey(
        to=User,
        on_delete=models.SET_NULL,
        related_name='hardware_items',
        verbose_name=_('保管人'),
        blank=True,
        null=True,
    )
    image = models.ImageField(
        verbose_name=_('实物照片'),
        upload_to='hardware/physical/',
        blank=True,
        null=True,
    )
    invoice_image = models.ImageField(
        verbose_name=_('发票照片'),
        upload_to='hardware/invoice/',
        blank=True,
        null=True,
    )
    remarks = models.TextField(
        verbose_name=_('备注'),
        blank=True,
    )
    submitted_by = models.ForeignKey(
        to=User,
        on_delete=models.SET_NULL,
        related_name='submitted_hardware',
        verbose_name=_('提交人'),
        blank=True,
        null=True,
    )
    approval_status = models.CharField(
        verbose_name=_('审批状态'),
        max_length=20,
        choices=HardwareApprovalStatusChoices,
        default=HardwareApprovalStatusChoices.PENDING,
        help_text=_('添加硬件时的审批状态（管理员添加自动通过，成员添加需审核）'),
    )
    approved_by = models.ForeignKey(
        to=User,
        on_delete=models.SET_NULL,
        related_name='approved_hardware',
        verbose_name=_('审核人'),
        blank=True,
        null=True,
    )
    approval_note = models.TextField(
        verbose_name=_('审核备注'),
        blank=True,
        help_text=_('审核人填写的审核意见（通过或驳回理由）'),
    )

    class Meta(NetBoxModel.Meta):
        verbose_name = _('硬件')
        verbose_name_plural = _('硬件')
        ordering = ('name',)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('plugins:lab_manager:hardware', args=[self.pk])
