"""扫码签到：新增权限点 action:checkin.qrcode 并授予内置管理角色。

- teacher / manager：可在打卡页打开「签到二维码」投屏展示
- member：不授予（避免任何人在宿舍自行亮码给别人扫）
- 系统管理员(superadmin) 全量权限，无需授权

签到本身仍是 action:checkin.create（既有权限点，改造前已分配给全部角色）。
"""

from django.db import migrations

QRCODE_KEY = 'action:checkin.qrcode'


def _grant(Role, code, keys):
    role = Role.objects.filter(code=code).first()
    if not role:
        return
    perms = list(role.permissions or [])
    for key in keys:
        if key not in perms:
            perms.append(key)
    role.permissions = sorted(perms)
    role.save(update_fields=['permissions'])


def apply(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    for code in ('teacher', 'manager'):
        _grant(Role, code, [QRCODE_KEY])


def rollback(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    for code in ('teacher', 'manager'):
        role = Role.objects.filter(code=code).first()
        if not role:
            continue
        role.permissions = sorted(k for k in (role.permissions or []) if k != QRCODE_KEY)
        role.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0022_seats_nav_permissions'),
    ]

    operations = [
        migrations.RunPython(apply, rollback),
    ]