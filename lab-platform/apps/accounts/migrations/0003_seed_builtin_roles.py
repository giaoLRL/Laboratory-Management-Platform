"""数据迁移：写入 4 个内置角色，并把现有 MemberProfile 绑定到对应内置角色。"""

from django.db import migrations

# 与 apps/accounts/rbac_defs.py 的权限点 key 保持一致
MEMBER_PERMS = [
    'page:workbench', 'action:notifications', 'page:profile', 'action:profile.edit', 'action:profile.status',
    'page:loans', 'action:loan.create', 'action:loan.cancel', 'action:loan.request_return',
    'page:leaves', 'action:leave.create', 'action:leave.cancel',
    'page:tasks', 'action:task.create', 'action:task.update', 'action:task.delete', 'action:task.attachment',
    'page:checkins', 'action:checkin.create', 'action:checkin.refresh',
    'page:competitions', 'action:competition.view',
    'page:agent', 'action:agent.chat', 'action:agent.history',
    'page:logs',
]

STAFF_ADDS = [
    'page:members', 'action:member.create', 'action:member.update', 'action:member.active',
    'page:assets', 'action:asset.create', 'action:asset.update', 'action:asset.repair',
    'action:asset.repair_complete', 'action:asset.retire',
    'action:loan.review', 'action:loan.issue', 'action:loan.receive',
    'action:leave.review',
    'action:competition.create', 'action:competition.update', 'action:competition.archive',
]

BUILTIN_ROLES = [
    ('member', '普通成员', False, False, MEMBER_PERMS),
    ('manager', '负责人', True, False, sorted(set(MEMBER_PERMS) | set(STAFF_ADDS))),
    ('teacher', '指导老师', True, False, sorted(set(MEMBER_PERMS) | set(STAFF_ADDS))),
    ('superadmin', '系统管理员', True, True, []),
]


def seed_roles(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    MemberProfile = apps.get_model('accounts', 'MemberProfile')
    for code, name, builtin, superadmin, perms in BUILTIN_ROLES:
        Role.objects.update_or_create(
            code=code,
            defaults={'name': name, 'builtin': builtin, 'superadmin': superadmin, 'permissions': perms},
        )
    # 为现有成员绑定与 role 字段一致的内置角色（superadmin 角色不自动授给任何人）
    role_map = {code: Role.objects.get(code=code) for code, *_ in BUILTIN_ROLES if code != 'superadmin'}
    for profile in MemberProfile.objects.all():
        r = role_map.get(profile.role)
        if r and not profile.roles.exists():
            profile.roles.add(r)


def unseed_roles(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Role.objects.filter(code__in=[b[0] for b in BUILTIN_ROLES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_role_memberprofile_permission_overrides_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_roles, unseed_roles),
    ]