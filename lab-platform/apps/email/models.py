from django.conf import settings
from django.db import models


def _encrypt(password):
    from django.core import signing
    return signing.dumps(password, salt='lab.email.smtp', compress=True) if password else ''


def _decrypt(token):
    if not token:
        return ''
    from django.core import signing
    try:
        return signing.loads(token, salt='lab.email.smtp')
    except signing.BadSignature:
        return ''


class EmailConfig(models.Model):
    """SMTP 配置（单例）：密码加密存储；开启后才允许发送。"""

    smtp_host = models.CharField('SMTP 服务器', max_length=128, blank=True, default='')
    smtp_port = models.PositiveIntegerField('端口', default=465)
    smtp_user = models.CharField('账号', max_length=128, blank=True, default='')
    smtp_password_enc = models.CharField('密码(加密)', max_length=512, blank=True, default='')
    from_addr = models.EmailField('发件人', max_length=128, blank=True, default='')
    use_ssl = models.BooleanField('SSL', default=True)
    enabled = models.BooleanField('启用', default=False)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '邮件配置'

    @property
    def smtp_password(self):
        return _decrypt(self.smtp_password_enc)

    def set_password(self, raw):
        self.smtp_password_enc = _encrypt(raw) if raw else ''

    def mask(self):
        return {
            'smtpHost': self.smtp_host,
            'smtpPort': self.smtp_port,
            'smtpUser': self.smtp_user,
            'passwordSet': bool(self.smtp_password_enc),
            'fromAddr': self.from_addr,
            'useSsl': self.use_ssl,
            'enabled': self.enabled,
        }


class EmailRule(models.Model):
    """提醒规则：key + 提前量 + 标题/正文模板（{name} {title} {due} 等占位符）。"""

    RULE_CHOICES = [
        ('task_due', '任务临近截止'),
        ('task_assigned', '任务指派'),
        ('loan_overdue', '借用已逾期'),
        ('competition_deadline', '比赛报名截止'),
        ('competition_start', '比赛开赛提醒'),
        ('leave_result', '请假审批结果'),
        ('loan_reviewed', '借用审批结果'),
        ('loan_issued', '借用发放'),
        ('asset_repaired', '维修完成'),
        ('custom', '自定义'),
    ]

    key = models.CharField('规则', max_length=32, unique=True, choices=RULE_CHOICES)
    label = models.CharField('名称', max_length=64)
    enabled = models.BooleanField('启用', default=True)
    hours_before = models.PositiveIntegerField('提前小时数', default=24)
    subject_tpl = models.CharField('标题模板', max_length=256, blank=True, default='')
    body_tpl = models.TextField('正文模板', blank=True, default='')

    class Meta:
        ordering = ['key']

    def __str__(self):
        return self.label

    def render(self, ctx):
        try:
            subject = self.subject_tpl.format(**ctx)
            body = self.body_tpl.format(**ctx)
        except (KeyError, IndexError, ValueError):
            subject, body = self.subject_tpl, self.body_tpl
        return subject, body


class EmailLog(models.Model):
    """邮件发送日志：同一对象同一规则每天只发一次（去重）。"""

    rule_key = models.CharField('规则', max_length=32)
    recipient = models.EmailField('收件人', max_length=128)
    obj_type = models.CharField('对象类型', max_length=32, blank=True, default='')
    obj_id = models.CharField('对象编号', max_length=64, blank=True, default='')
    subject = models.CharField('主题', max_length=256, blank=True, default='')
    day = models.DateField('发送日', auto_now_add=True)
    ok = models.BooleanField('成功', default=True)
    error = models.CharField('错误', max_length=256, blank=True, default='')
    sent_at = models.DateTimeField('发送时间', auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']
        constraints = [
            models.UniqueConstraint(fields=['rule_key', 'obj_type', 'obj_id', 'recipient', 'day'], name='uniq_email_day'),
        ]