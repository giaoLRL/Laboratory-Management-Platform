from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel
from users.models import User


class AgentConversation(NetBoxModel):
    """智能体会话记录。"""

    user = models.ForeignKey(
        to=User,
        on_delete=models.CASCADE,
        related_name='agent_conversations',
        verbose_name=_('所属用户'),
    )
    title = models.CharField(
        verbose_name=_('会话标题'),
        max_length=200,
    )
    mode = models.CharField(
        verbose_name=_('会话模式'),
        max_length=20,
        default='chat',
    )
    workflow_alias = models.CharField(
        verbose_name=_('工作流别名'),
        max_length=100,
        blank=True,
    )
    coze_conversation_id = models.CharField(
        verbose_name=_('扣子会话 ID'),
        max_length=100,
        blank=True,
        db_index=True,
    )
    last_message_preview = models.CharField(
        verbose_name=_('最后消息预览'),
        max_length=255,
        blank=True,
    )

    class Meta(NetBoxModel.Meta):
        verbose_name = _('智能体会话')
        verbose_name_plural = _('智能体会话')
        ordering = ('-last_updated', '-created')

    def __str__(self) -> str:
        return self.title


class AgentMessage(NetBoxModel):
    """智能体消息记录。"""

    conversation = models.ForeignKey(
        to=AgentConversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_('所属会话'),
    )
    role = models.CharField(
        verbose_name=_('角色'),
        max_length=20,
    )
    content = models.TextField(
        verbose_name=_('消息内容'),
        blank=True,
    )
    raw_payload = models.JSONField(
        verbose_name=_('原始响应'),
        default=dict,
        blank=True,
    )
    coze_chat_id = models.CharField(
        verbose_name=_('扣子对话 ID'),
        max_length=100,
        blank=True,
    )

    class Meta(NetBoxModel.Meta):
        verbose_name = _('智能体消息')
        verbose_name_plural = _('智能体消息')
        ordering = ('created',)

    def __str__(self) -> str:
        return f'{self.role}: {self.content[:50]}'
