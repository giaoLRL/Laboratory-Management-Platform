from django.db import models
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel
from users.models import User

from ..choices import HardwareApprovalStatusChoices, HardwareCategoryChoices, HardwareStatusChoices
from ..validators import validate_file_size


class Hardware(NetBoxModel):
    """硬件资源"""
    name = models.CharField(
        verbose_name=_('名称'),
        max_length=200,
        help_text=_('硬件设备名称，例如：STM32F407 开发板'),
    )
    category = models.CharField(
        verbose_name=_('类别'),
        max_length=30,
        choices=HardwareCategoryChoices,
        default=HardwareCategoryChoices.MCU,
        db_index=True,
        help_text=_('硬件类别：MCU、传感器、电源、仪器、工具等'),
    )
    model_number = models.CharField(
        verbose_name=_('型号'),
        max_length=100,
        blank=True,
        help_text=_('厂家提供的型号编号'),
    )
    manufacturer = models.CharField(
        verbose_name=_('厂家/品牌'),
        max_length=100,
        blank=True,
        help_text=_('生产厂家或品牌名称'),
    )
    quantity = models.PositiveIntegerField(
        verbose_name=_('数量'),
        default=1,
        help_text=_('当前库存数量'),
    )
    minimum_stock = models.PositiveIntegerField(
        verbose_name=_('最低库存阈值'),
        default=0,
        help_text=_('当库存数量低于此值时触发低库存警报（0 表示不触发）'),
    )
    unit_price = models.DecimalField(
        verbose_name=_('单价（元）'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('单位价格，人民币'),
    )
    purchase_date = models.DateField(
        verbose_name=_('购买日期'),
        null=True,
        blank=True,
        help_text=_('购买或入库日期'),
    )
    purchase_link = models.URLField(
        verbose_name=_('购买链接'),
        max_length=500,
        blank=True,
        help_text=_('淘宝/京东等购买链接'),
    )
    status = models.CharField(
        verbose_name=_('状态'),
        max_length=20,
        choices=HardwareStatusChoices,
        default=HardwareStatusChoices.IN_USE,
        db_index=True,
        help_text=_('硬件使用状态：使用中、闲置、维修、报废'),
    )
    storage_location = models.CharField(
        verbose_name=_('存放位置'),
        max_length=100,
        blank=True,
        help_text=_('如：A302 实验室 3 号柜'),
    )
    custodian = models.ForeignKey(
        to=User,
        on_delete=models.SET_NULL,
        related_name='hardware_items',
        verbose_name=_('保管人'),
        blank=True,
        null=True,
        help_text=_('当前负责保管该硬件的人员'),
    )
    image = models.ImageField(
        verbose_name=_('实物照片'),
        upload_to='hardware/physical/',
        blank=True,
        null=True,
        validators=[validate_file_size],
        help_text=_('硬件实物照片，最大 10MB'),
    )
    invoice_image = models.ImageField(
        verbose_name=_('发票照片'),
        upload_to='hardware/invoice/',
        blank=True,
        null=True,
        validators=[validate_file_size],
        help_text=_('购买发票照片，最大 10MB'),
    )
    remarks = models.TextField(
        verbose_name=_('备注'),
        blank=True,
        help_text=_('其他补充说明'),
    )
    submitted_by = models.ForeignKey(
        to=User,
        on_delete=models.SET_NULL,
        related_name='submitted_hardware',
        verbose_name=_('提交人'),
        blank=True,
        null=True,
        help_text=_('提交此硬件记录的人员'),
    )
    approval_status = models.CharField(
        verbose_name=_('审批状态'),
        max_length=20,
        choices=HardwareApprovalStatusChoices,
        default=HardwareApprovalStatusChoices.PENDING,
        db_index=True,
        help_text=_('添加硬件时的审批状态（管理员添加自动通过，成员添加需审核）'),
    )
    approved_by = models.ForeignKey(
        to=User,
        on_delete=models.SET_NULL,
        related_name='approved_hardware',
        verbose_name=_('审核人'),
        blank=True,
        null=True,
        help_text=_('审核该硬件的管理员'),
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
