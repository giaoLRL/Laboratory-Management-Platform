"""幂等地创建系统管理员账号。

用法：python manage.py createsuperadmin --username admin --password xxx
系统管理员拥有全部权限、不受权限矩阵限制，且能维护权限矩阵/角色/成员覆盖。
"""

import re

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import MemberProfile, Role

USERNAME_RE = re.compile(r'^\w{3,30}$')
PASSWORD_RE = re.compile(r'^(?=.*[A-Za-z])(?=.*\d).{8,64}$')


class Command(BaseCommand):
    help = '幂等地创建系统管理员（superadmin）账号'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--password', required=True)

    @transaction.atomic
    def handle(self, *args, **opts):
        username = opts['username']
        password = opts['password']
        if not USERNAME_RE.match(username):
            raise CommandError('账号须为 3-30 位字母、数字或下划线')
        if not PASSWORD_RE.match(password):
            raise CommandError('密码须为 8-64 位且至少含一个字母与一个数字')
        User = get_user_model()
        user = User.objects.filter(username__iexact=username).first()
        if user and getattr(user, 'member_profile', None) and user.member_profile.roles.filter(superadmin=True).exists():
            self.stdout.write(f'系统管理员账号已存在: {username}，未改动。')
            return
        if user is None:
            user = User.objects.create_user(username=username, password=password)
            user.is_superuser = True
            user.is_staff = True
            user.save()
        role = Role.objects.get_or_create(
            code='superadmin',
            defaults={'name': '系统管理员', 'builtin': True, 'superadmin': True, 'permissions': []},
        )[0]
        prof, _ = MemberProfile.objects.get_or_create(
            user=user,
            defaults={
                'name': '系统管理员',
                'number': f'admin-{user.pk:03d}',
                'role': MemberProfile.ROLE_TEACHER,  # 兼容 manager 层级判断
                'active': True,
            },
        )
        prof.roles.add(role)
        prof.user.is_active = True
        prof.user.save()
        self.stdout.write(self.style.SUCCESS(f'系统管理员已就绪: {username}'))