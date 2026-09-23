"""动态导航种子：NavItem 表 + 默认菜单/路由配置（superadmin 可经接口调整）。"""

from django.db import migrations, models

DEFAULT_NAV = [
    # (id, label, icon, permission, param)
    ('dashboard', '工作台', 'grid', 'page:workbench', ''),
    ('members', '成员管理', 'users', 'page:members', ''),
    ('leaves', '请假管理', 'calendar', 'page:leaves', ''),
    ('assets', '模块管理', 'chip', 'page:assets', ''),
    ('loans', '借用与归还', 'swap', 'page:loans', ''),
    ('competitions', '比赛管理', 'trophy', 'page:competitions', ''),
    ('tasks', '任务看板', 'task', 'page:tasks', ''),
    ('checkins', '实验室打卡', 'pin', 'page:checkins', ''),
    ('leaderboard', '积分排行', 'trophy', 'page:leaderboard', ''),
    ('agent', '智能体助手', 'chat', 'page:agent', ''),
    ('logs', '操作记录', 'history', 'page:logs', ''),
    ('profile', '个人中心', 'user', 'page:profile', ''),
    ('permissions', '权限矩阵', 'shield', 'page:permissions', ''),
    ('announcements', '公告管理', 'bell', 'page:announcements', ''),
    ('email', '邮件通知', 'mail', 'page:email', ''),
    ('groups', '小组管理', 'users', 'page:groups', ''),
    ('login-logs', '登录日志', 'history', 'page:loginlogs', ''),
    # 参数子页（不在侧边栏主菜单，作为路由存在）
    ('member', '成员详情', '', 'page:member.detail', 'm'),
    ('task', '任务详情', '', 'page:tasks', 'TASK'),
]


def seed_nav(apps, schema_editor):
    NavItem = apps.get_model('accounts', 'NavItem')
    for order, (rid, label, icon, permission, param) in enumerate(DEFAULT_NAV, start=1):
        NavItem.objects.get_or_create(id=rid, defaults={
            'label': label, 'icon': icon, 'permission': permission,
            'param': param, 'enabled': True, 'order': order,
        })


def unseed(apps, schema_editor):
    NavItem = apps.get_model('accounts', 'NavItem')
    NavItem.objects.filter(id__in=[rid for rid, *_ in DEFAULT_NAV]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_grant_agent_operate'),
    ]

    operations = [
        migrations.CreateModel(
            name='NavItem',
            fields=[
                ('id', models.CharField(max_length=32, primary_key=True, serialize=False, verbose_name='路由 id')),
                ('label', models.CharField(max_length=32, verbose_name='菜单标题')),
                ('icon', models.CharField(blank=True, default='', max_length=32, verbose_name='图标')),
                ('permission', models.CharField(blank=True, default='', max_length=64, verbose_name='所需权限点')),
                ('param', models.CharField(blank=True, default='', max_length=32, verbose_name='参数子页前缀')),
                ('enabled', models.BooleanField(default=True, verbose_name='启用')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='排序')),
            ],
            options={'ordering': ['order', 'id']},
        ),
        migrations.RunPython(seed_nav, unseed),
    ]