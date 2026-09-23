"""扫描临期任务 / 逾期借用 / 报名截止与开赛比赛，生成站内通知并按规则发送邮件。

宿主机 cron 每 30 分钟执行一次：
  docker exec lab-lab-1 python manage.py send_reminders
站内通知始终生成（不依赖邮件规则开关）；邮件仅在规则 enabled 时发送。
"""

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = '发送规则化邮件提醒与站内通知（任务临期/借用逾期/比赛报名与开赛）'

    def handle(self, *args, **options):
        from apps.email.service import _member_email, _rule, _trigger_by_rule
        from apps.accounts.models import MemberProfile
        from apps.notify.service import create_many, managers_with

        now = timezone.now()
        rounds = 0
        notified = 0

        # ── 1. 任务临期 ──
        rule = _rule('task_due')
        if rule:
            from apps.tasksapp.models import Task
            deadline = now + timezone.timedelta(hours=rule.hours_before)
            for task in Task.objects.filter(due__lte=deadline, due__gte=now).exclude(status=Task.STATUS_DONE).select_related('assignee', 'assignee__member_profile'):
                if task.assignee_id:
                    from apps.notify.service import create
                    create(task.assignee, 'task_due', f'任务即将截止 · {task.title[:30]}',
                           f'{task.id} · 截止 {timezone.localtime(task.due).strftime("%m-%d %H:%M")}',
                           ref_type='task', ref_id=task.id, link='tasks')
                    notified += 1
                if rule.enabled:
                    email = _member_email(task.assignee)
                    if email:
                        _trigger_by_rule(rule, {
                            'name': task.assignee.member_profile.name if hasattr(task.assignee, 'member_profile') else '同学',
                            'title': task.title, 'id': task.id,
                            'due': timezone.localtime(task.due).strftime('%m-%d %H:%M'),
                        }, 'task', task.id, [email])
                        rounds += 1

        # ── 2. 借用已逾期 ──
        rule = _rule('loan_overdue')
        if rule:
            from apps.inventory.models import Loan
            for loan in Loan.objects.filter(due__lt=now, status__in=(Loan.STATUS_IN_USE, Loan.STATUS_RETURNING)).select_related('member', 'member__member_profile'):
                targets = [u for u in [loan.member] + managers_with('action:loan.review') if u]
                create_many(targets, 'loan_overdue', f'借用已逾期 · {loan.id}',
                            f'应于 {timezone.localtime(loan.due).strftime("%m-%d %H:%M")} 归还',
                            ref_type='loan', ref_id=loan.id, link='loans')
                notified += len(set(u.id for u in targets if u))
                if rule.enabled:
                    email = _member_email(loan.member)
                    if email:
                        _trigger_by_rule(rule, {
                            'name': loan.member.member_profile.name if hasattr(loan.member, 'member_profile') else '同学',
                            'id': loan.id,
                            'due': timezone.localtime(loan.due).strftime('%m-%d %H:%M'),
                        }, 'loan', loan.id, [email])
                        rounds += 1

        # ── 3. 比赛报名截止 ──
        rule = _rule('competition_deadline')
        if rule:
            from apps.competitions.models import Competition
            deadline = now + timezone.timedelta(hours=rule.hours_before)
            for comp in Competition.objects.filter(archived=False, registration_end__lte=deadline, registration_end__gte=now):
                members = MemberProfile.objects.filter(active=True).select_related('user')
                create_many([mp.user for mp in members], 'competition_deadline',
                            f'比赛报名即将截止 · {comp.name[:30]}',
                            f'报名截止 {timezone.localtime(comp.registration_end).strftime("%m-%d %H:%M")}',
                            ref_type='competition', ref_id=comp.id, link='competitions')
                notified += 1
                if rule.enabled:
                    emails = [_member_email(mp.user) for mp in members]
                    emails = [e for e in emails if e]
                    if emails:
                        _trigger_by_rule(rule, {
                            'name': '实验室各位同学',
                            'title': comp.name,
                            'due': timezone.localtime(comp.registration_end).strftime('%m-%d %H:%M'),
                        }, 'competition', comp.id, emails)
                        rounds += 1

        # ── 4. 比赛开赛提醒 ──
        rule = _rule('competition_start')
        if rule:
            from apps.competitions.models import Competition
            start_upper = now + timezone.timedelta(hours=rule.hours_before)
            for comp in Competition.objects.filter(archived=False, start__lte=start_upper, start__gte=now):
                members = MemberProfile.objects.filter(active=True).select_related('user')
                create_many([mp.user for mp in members], 'competition_start',
                            f'比赛即将开赛 · {comp.name[:30]}',
                            f'{timezone.localtime(comp.start).strftime("%m-%d %H:%M")} · {comp.location or ""}',
                            ref_type='competition', ref_id=comp.id, link='competitions')
                notified += 1
                if rule.enabled:
                    emails = [_member_email(mp.user) for mp in members]
                    emails = [e for e in emails if e]
                    if emails:
                        _trigger_by_rule(rule, {
                            'name': '实验室各位同学',
                            'title': comp.name,
                            'start': timezone.localtime(comp.start).strftime('%m-%d %H:%M'),
                            'location': comp.location or '',
                        }, 'competition', comp.id, emails)
                        rounds += 1

        self.stdout.write(self.style.SUCCESS(
            f'send_reminders done, emails={rounds}, notifications={notified}'))
