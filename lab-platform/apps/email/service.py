"""邮件发送引擎：被 manage.py send_reminders 与审批回执调用。"""

from django.utils import timezone


def get_config():
    from apps.email.models import EmailConfig

    cfg, _ = EmailConfig.objects.get_or_create(pk=1)
    return cfg


def _record(rule_key, recipient, obj_type, obj_id, subject, ok, error=''):
    from apps.email.models import EmailLog

    try:
        EmailLog.objects.create(
            rule_key=rule_key, recipient=recipient, obj_type=obj_type[:32],
            obj_id=str(obj_id or '')[:64], subject=str(subject)[:256], ok=ok, error=str(error)[:256])
    except Exception:
        pass


def send(to, subject, body, rule_key='custom', obj_type='', obj_id=''):
    """按配置发一封邮件，并记录日志。返回 error 文本或 None。"""
    cfg = get_config()
    if not cfg.enabled or not cfg.smtp_host or not cfg.smtp_user or not cfg.smtp_password:
        _record(rule_key, to, obj_type, obj_id, subject, False, 'SMTP 未配置或未启用')
        return 'SMTP 未配置或未启用'
    from django.core import mail
    from django.core.mail import EmailMessage

    msg = EmailMessage(
        subject=subject, body=body,
        from_email=cfg.from_addr or cfg.smtp_user, to=[to])
    try:
        if cfg.use_ssl:
            connection = mail.get_connection(
                backend='django.core.mail.backends.smtp.EmailBackend',
                host=cfg.smtp_host, port=cfg.smtp_port,
                username=cfg.smtp_user, password=cfg.smtp_password,
                use_ssl=True, fail_silently=False,
                timeout=15)
            msg.connection = connection
            msg.send()
        else:
            mail.send_mail(subject, body, cfg.from_addr or cfg.smtp_user, [to],
                           auth_user=cfg.smtp_user, auth_password=cfg.smtp_password,
                           connection=mail.get_connection(
                               backend='django.core.mail.backends.smtp.EmailBackend',
                               host=cfg.smtp_host, port=cfg.smtp_port, use_tls=not cfg.use_ssl,
                               fail_silently=False, timeout=15))
    except Exception as exc:  # noqa: BLE001
        err = str(exc)[:256]
        _record(rule_key, to, obj_type, obj_id, subject, False, err)
        return err
    _record(rule_key, to, obj_type, obj_id, subject, True)
    return None


def _trigger_by_rule(rule, ctx, obj_type, obj_id, emails):
    """规则命中后逐个收件人发送 + 去重。"""
    if not rule.enabled:
        return
    from apps.email.models import EmailLog

    subject, body = rule.render(ctx)
    for email in {e for e in emails if e}:
        if rule.key != 'leave_result' and EmailLog.objects.filter(
                rule_key=rule.key, obj_type=obj_type, obj_id=obj_id, recipient=email, day=timezone.localdate()).exists():
            continue
        send(email, subject, body, rule.key, obj_type, obj_id)


def _member_email(user):
    if not user:
        return ''
    prof = getattr(user, 'member_profile', None)
    return (prof.email or '').strip() if prof else ''


def _rule(key):
    from apps.email.models import EmailRule
    return EmailRule.objects.filter(key=key).first()