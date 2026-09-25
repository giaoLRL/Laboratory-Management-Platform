from django.contrib.auth.models import User
from django.db import models


class Role(models.Model):
    """权限角色：定基础权限集；superadmin 免检（不受权限矩阵限制）。"""

    code = models.CharField('编码', max_length=32, unique=True)
    name = models.CharField('名称', max_length=64)
    builtin = models.BooleanField('内置', default=False)
    superadmin = models.BooleanField('系统管理员(免检)', default=False)
    permissions = models.JSONField('权限点集合', default=list, blank=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f'{self.name}({self.code})'


class LabGroup(models.Model):
    """实验室小组：队长 + 成员归属（成员通过 MemberProfile.group_fk 关联）。"""

    id = models.CharField('编号', max_length=32, primary_key=True)
    name = models.CharField('小组名称', max_length=64, unique=True)
    leader = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='led_groups')
    capacity = models.PositiveIntegerField('人数上限', default=20)
    note = models.CharField('备注', max_length=256, blank=True, default='')
    created = models.DateTimeField('创建时间', auto_now_add=True)
    updated = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class MemberProfile(models.Model):
    """成员档案：1:1 扩展 Django 用户，承载实验室业务字段。"""

    ROLE_TEACHER = 'teacher'
    ROLE_MANAGER = 'manager'
    ROLE_MEMBER = 'member'
    ROLE_CHOICES = [(ROLE_TEACHER, '指导老师'), (ROLE_MANAGER, '负责人'), (ROLE_MEMBER, '普通成员')]

    STATUS_FREE = '空闲'
    STATUS_BUSY = '忙碌'
    STATUS_OFFLINE = '模拟离线'
    BASE_STATUS_CHOICES = [(STATUS_FREE, STATUS_FREE), (STATUS_BUSY, STATUS_BUSY), (STATUS_OFFLINE, STATUS_OFFLINE)]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='member_profile')
    name = models.CharField('姓名', max_length=64)
    number = models.CharField('学号/工号', max_length=32, unique=True)
    role = models.CharField('角色', max_length=16, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    roles = models.ManyToManyField(Role, blank=True, related_name='members', verbose_name='授权角色')
    permission_overrides = models.JSONField('权限覆盖', default=dict, blank=True)
    group = models.CharField('所属小组', max_length=64, blank=True, default='')
    group_fk = models.ForeignKey(LabGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='members', verbose_name='小组')
    direction = models.CharField('技术方向', max_length=128, blank=True, default='')
    contact = models.CharField('联系方式', max_length=128, blank=True, default='')
    email = models.EmailField('邮箱', max_length=128, blank=True, default='')
    active = models.BooleanField('在籍', default=True)
    must_change_password = models.BooleanField('强制改密', default=False)
    must_complete_profile = models.BooleanField('首次登录需完善资料', default=False)
    base_status = models.CharField('工作状态', max_length=16, choices=BASE_STATUS_CHOICES, default=STATUS_FREE)
    level_exp = models.PositiveIntegerField('通关经验值 EXP', default=0)
    note = models.CharField('备注', max_length=256, blank=True, default='')
    joined = models.DateTimeField('加入时间', auto_now_add=True)
    updated = models.DateTimeField('更新时间', auto_now=True)

    def effective_roles(self):
        """返回生效角色列表：roles 非空用 roles，否则按 role 字段映射到内置角色。"""
        roles = list(self.roles.all())
        if roles:
            return roles
        builtins = list(Role.objects.filter(code__in=(self.role,)) if self.role else ())
        return builtins

    class Meta:
        ordering = ['number']

    def __str__(self):
        return f'{self.name}({self.number})'


class OperationLog(models.Model):
    """操作日志：由后端在写操作时生成，不信任客户端自报。"""

    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='logs_as_actor')
    member = models.ForeignKey(MemberProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs_about')
    text = models.CharField('内容', max_length=256)
    at = models.DateTimeField('时间', auto_now_add=True)
    private = models.BooleanField('仅管理可见', default=False)
    # 结构化关联：可回答"某对象（任务/借用/请假/资产…）的全部变更历史"，替代 text 模糊匹配
    ref_type = models.CharField('对象类型', max_length=32, blank=True, default='')
    ref_id = models.CharField('对象编号', max_length=64, blank=True, default='')

    class Meta:
        ordering = ['-at']
        indexes = [models.Index(fields=['ref_type', 'ref_id'], name='idx_oplog_ref')]

    def __str__(self):
        return self.text


class LoginLog(models.Model):
    """登录日志：记录每次登录尝试的 IP / UA / 结果，用于安全审计与异常告警。

    user 为空（null）时表示未知用户名尝试，账号名记录在 username 字段，
    确保针对不存在账号的爆破也有审计痕迹。
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='login_logs')
    username = models.CharField('尝试账号', max_length=128, blank=True, default='')
    ip = models.GenericIPAddressField('IP', null=True, blank=True)
    user_agent = models.CharField('UA', max_length=256, blank=True, default='')
    success = models.BooleanField('成功', default=True)
    at = models.DateTimeField('时间', auto_now_add=True)

    class Meta:
        ordering = ['-at']


class NavItem(models.Model):
    """动态导航/路由项：后端配置下发，前端据其渲染菜单与路由守卫。

    permission 为空表示登录即可见；param 非空表示支持参数子页（如 member → #member/m3）。
    顺序/启用由 superadmin 经接口调整，前端不硬编码菜单。
    """

    id = models.CharField('路由 id', max_length=32, primary_key=True)
    label = models.CharField('菜单标题', max_length=32)
    icon = models.CharField('图标', max_length=32, blank=True, default='')
    permission = models.CharField('所需权限点', max_length=64, blank=True, default='')
    param = models.CharField('参数子页前缀', max_length=32, blank=True, default='')
    enabled = models.BooleanField('启用', default=True)
    order = models.PositiveIntegerField('排序', default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.label}({self.id})'


class ApiToken(models.Model):
    """跨平台只读接口令牌：只存 SHA-256 哈希；明文仅创建时展示一次。"""

    name = models.CharField('令牌名', max_length=64)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_tokens')
    token_hash = models.CharField('令牌哈希', max_length=64, unique=True)
    scopes = models.JSONField('授权范围', default=list, blank=True)
    active = models.BooleanField('启用', default=True)
    expires_at = models.DateTimeField('过期时间', null=True, blank=True)
    last_used_at = models.DateTimeField('最后使用', null=True, blank=True)
    created = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.name
