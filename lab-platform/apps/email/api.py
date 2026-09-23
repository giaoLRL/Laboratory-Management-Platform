"""邮件设置：SMTP 配置、规则管理、发送日志。发送引擎见 service.py / send_reminders 命令。"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.common.rbac import require
from apps.common.response import ok, fail
from apps.email.models import EmailConfig, EmailLog, EmailRule
from apps.email.service import get_config, send


def _rule_dict(r):
    return {'key': r.key, 'label': r.label, 'enabled': r.enabled,
            'hoursBefore': r.hours_before, 'subjectTpl': r.subject_tpl, 'bodyTpl': r.body_tpl}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def email_config_get(request):
    return ok(get_config().mask())


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def email_config_save(request):
    if (err := require(request.user, 'action:email.manage', '没有配置邮件的权限')):
        return err
    d = request.data or {}
    cfg = get_config()
    if 'smtpHost' in d:
        cfg.smtp_host = str(d.get('smtpHost', '')).strip()[:128]
    if 'smtpPort' in d:
        try:
            cfg.smtp_port = max(1, min(int(d.get('smtpPort')), 65535))
        except (TypeError, ValueError):
            pass
    if 'smtpUser' in d:
        cfg.smtp_user = str(d.get('smtpUser', '')).strip()[:128]
    if 'fromAddr' in d:
        cfg.from_addr = str(d.get('fromAddr', '')).strip()[:128]
    if 'useSsl' in d:
        cfg.use_ssl = bool(d.get('useSsl'))
    if 'enabled' in d:
        cfg.enabled = bool(d.get('enabled'))
    password = str(d.get('password', ''))
    if password:
        cfg.set_password(password)
    cfg.save()
    if d.get('sendTest'):
        err = send(cfg.smtp_user or cfg.from_addr, '【具身智能实验室】邮件服务测试',
                   '这是一封配置测试邮件。收到即表示 SMTP 设置可用。')
        if err:
            return fail('配置已保存，但测试发送失败：' + err)
        return ok({'ok': True, 'testSent': True})
    return ok(cfg.mask())


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def email_rules_get(request):
    return ok([_rule_dict(r) for r in EmailRule.objects.all()])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def email_rules_save(request):
    if (err := require(request.user, 'action:email.manage', '没有配置邮件规则的权限')):
        return err
    for item in (request.data or {}).get('rules') or []:
        rule = EmailRule.objects.filter(key=str(item.get('key', ''))).first()
        if not rule:
            continue
        if 'enabled' in item:
            rule.enabled = bool(item.get('enabled'))
        if 'hoursBefore' in item:
            try:
                rule.hours_before = max(1, min(int(item.get('hoursBefore')), 24 * 30))
            except (TypeError, ValueError):
                pass
        for field, key_ in (('subject_tpl', 'subjectTpl'), ('body_tpl', 'bodyTpl')):
            if key_ in item and isinstance(item.get(key_), str):
                if len(item[key_]) > 2000:
                    return fail('模板内容过长')
                setattr(rule, field, item[key_])
        rule.save()
    return ok([_rule_dict(r) for r in EmailRule.objects.all()])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def email_logs(request):
    rows = []
    for lg in EmailLog.objects.all()[:100]:
        rows.append({'ruleKey': lg.rule_key, 'recipient': lg.recipient, 'subject': lg.subject,
                     'objId': lg.obj_id, 'ok': lg.ok, 'error': lg.error, 'sentAt': lg.sent_at})
    return ok(rows)