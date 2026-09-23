from django.contrib.auth.models import User
from django.db import models


class Conversation(models.Model):
    id = models.CharField('会话编号', max_length=32, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='agent_conversations')
    title = models.CharField('标题', max_length=128, blank=True, default='')
    created = models.DateTimeField('创建时间', auto_now_add=True)
    updated = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['-updated']


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
