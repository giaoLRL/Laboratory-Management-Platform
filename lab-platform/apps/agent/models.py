from django.contrib.auth.models import User
from django.db import models


class Conversation(models.Model):
    id = models.CharField('会话编号', max_length=32, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='agent_conversations')
    title = models.CharField('标题', max_length=128, blank=True, default='')
    pending_op = models.JSONField('待确认操作', null=True, blank=True)
    created = models.DateTimeField('创建时间', auto_now_add=True)
    updated = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['-updated']


class UserMemory(models.Model):
    """个人记忆：AI 可读写用户偏好（如方向、常用设备等）。"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='agent_memories')
    key = models.CharField('标签', max_length=64)
    value = models.TextField('内容', blank=True, default='')
    updated = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['-updated']
        constraints = [
            models.UniqueConstraint(fields=['user', 'key'], name='uniq_user_memory_key'),
        ]


class AgentMessage(models.Model):
    ROLE_USER = 'user'
    ROLE_ASSISTANT = 'assistant'
    ROLE_TOOL = 'tool'

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField('角色', max_length=16)
    content = models.TextField('内容', blank=True, default='')
    tool_name = models.CharField('工具名', max_length=64, blank=True, default='')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created']
