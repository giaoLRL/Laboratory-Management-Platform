from __future__ import annotations

from uuid import uuid4

from django.db import models
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel
from users.models import User


def generate_batch_id() -> str:
    return f'imp_{uuid4().hex[:12]}'


class HardwareImportBatch(NetBoxModel):
    """硬件批量导入批次记录。"""

    batch_id = models.CharField(
        verbose_name=_('批次编号'),
        max_length=32,
        unique=True,
        default=generate_batch_id,
    )
    created_by = models.ForeignKey(
        to=User,
        on_delete=models.SET_NULL,
        related_name='hardware_import_batches',
        verbose_name=_('创建人'),
        blank=True,
        null=True,
    )
    source_type = models.CharField(
        verbose_name=_('来源类型'),
        max_length=20,
        default='json',
    )
    status = models.CharField(
        verbose_name=_('状态'),
        max_length=20,
        default='draft',
    )
    raw_payload = models.JSONField(
        verbose_name=_('原始数据'),
        default=list,
        blank=True,
    )
    validated_payload = models.JSONField(
        verbose_name=_('校验结果'),
        default=dict,
        blank=True,
    )
    result_summary = models.JSONField(
        verbose_name=_('导入结果'),
        default=dict,
        blank=True,
    )

    class Meta(NetBoxModel.Meta):
        verbose_name = _('硬件导入批次')
        verbose_name_plural = _('硬件导入批次')
        ordering = ('-created',)

    def __str__(self) -> str:
        return self.batch_id
