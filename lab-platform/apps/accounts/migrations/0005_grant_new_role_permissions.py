"""给内置角色补充新增权限点：老师/负责人 += 成员扩展、公告、导出、排行榜。"""

from django.db import migrations

STAFF_ADDS = [
    'page:member.detail', 'page:groups', 'page:loginlogs', 'page:leaderboard',
    'action:member.reset_password', 'action:group.manage', 'action:group.members',
    'page:announcements', 'action:announcement.create', 'action:announcement.update',
    'action:export.csv', 'action:task.score', 'action:points.rules', 'action:points.manual',
]

ALL_MEMBER_ADDS = [
    'page:member.detail', 'page:leaderboard',
]


def apply(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    for role in Role.objects.filter(code__in=('teacher', 'manager')):
        perms = list(role.permissions or [])
        for k in STAFF_ADDS:
            if k not in perms:
                perms.append(k)
        role.permissions = sorted(perms)
        role.save(update_fields=['permissions'])
    for role in Role.objects.filter(code='member'):
        perms = list(role.permissions or [])
        for k in ALL_MEMBER_ADDS:
            if k not in perms:
                perms.append(k)
        role.permissions = sorted(perms)
        role.save(update_fields=['permissions'])


def rollback(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    for role in Role.objects.filter(code__in=('teacher', 'manager', 'member')):
        perms = list(role.permissions or [])
        role.permissions = sorted(k for k in perms if k not in (STAFF_ADDS + ALL_MEMBER_ADDS))
        role.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_memberprofile_email_and_more'),
        ('notify', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(apply, rollback),
    ]