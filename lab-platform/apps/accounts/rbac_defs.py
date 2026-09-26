"""权限点静态清单（RBAC 矩阵的"列/行"契约）。

每一项: (key, label, frontend_only)
- key: 权限点唯一标识。
  - page:*   控制菜单(NAV)可见 + hash 路由守卫 + 页面可进
  - action:* 控制按钮/操作 + 对应后端 API 动作（除 frontend_only 外，后端强制）
- label: 矩阵界面显示的中文名。
- frontend_only: True 表示仅前端渲染控制、后端无强制点（如铃铛/刷新）。

本文件是"前端按钮 / 后端视图 / 权限矩阵"三方的唯一契约来源，新增权限点必须
同步到对应前端按钮的 can('action:...') 与后端视图的 require(user,'action:...')。
"""

# (key, label, frontend_only)
PERMISSION_POINTS = [
    # ── 框架 ──
    ('page:workbench', '工作台', False),
    ('action:notifications', '顶栏待办铃铛', True),
    ('page:notifications', '通知中心页', False),
    ('page:profile', '个人中心', False),
    ('action:profile.edit', '编辑个人资料', False),
    ('action:profile.status', '更新工作状态', False),

    # ── 成员 ──
    ('page:members', '成员管理页', False),
    ('page:member.detail', '成员详情页', False),
    ('page:groups', '分组管理页', False),
    ('action:member.create', '创建成员账号', False),
    ('action:member.update', '修改成员资料', False),
    ('action:member.active', '停用/启用成员', False),
    ('action:member.reset_password', '重置成员密码', False),
    ('action:group.manage', '创建/管理小组', False),
    ('action:group.members', '调配小组成员', False),
    ('page:loginlogs', '登录日志页', False),
    ('action:token.manage', 'API 令牌管理', False),

    # ── 公告 ──
    ('page:announcements', '公告管理页', False),
    ('action:announcement.create', '发布公告', False),
    ('action:announcement.update', '编辑/下架公告', False),
    ('page:news', '实时动态页', False),
    ('action:news.manage', '动态录入/删除', False),

    # ── 积分 ──
    ('page:leaderboard', '积分排行榜页', False),
    ('action:task.score', '任务评分', False),
    ('action:points.rules', '积分规则配置', False),
    ('action:points.manual', '手动增减积分', False),

    # ── 邮件 ──
    ('page:email', '邮件设置页', False),
    ('action:email.manage', '邮件配置/规则管理', False),

    # ── 数据导出 ──
    ('action:export.csv', '导出 CSV', False),

    # ── 资产 / 借用 ──
    ('page:assets', '模块页', False),
    ('action:asset.create', '录入模块', False),
    ('action:asset.update', '编辑模块', False),
    ('action:asset.repair', '登记维修', False),
    ('action:asset.repair_complete', '完成维修', False),
    ('action:asset.retire', '报废模块', False),
    ('page:loans', '借用与归还页', False),
    ('action:loan.create', '申请借用', False),
    ('action:loan.cancel', '取消借用', False),
    ('action:loan.request_return', '申请归还', False),
    ('action:loan.review', '审批借用', False),
    ('action:loan.issue', '确认发放', False),
    ('action:loan.receive', '验收归还', False),

    # ── 请假 ──
    ('page:leaves', '请假页', False),
    ('action:leave.create', '提交请假', False),
    ('action:leave.cancel', '撤销请假', False),
    ('action:leave.review', '审批请假', False),

    # ── 任务 ──
    ('page:tasks', '任务看板页', False),
    ('action:task.create', '创建任务', False),
    ('action:task.update', '编辑/移动任务', False),
    ('action:task.delete', '删除任务', False),
    ('action:task.attachment', '上传附件', False),
    ('action:task.review', '审核任务', False),

    # ── 关卡系统 ──
    ('page:levels', '关卡页', False),
    ('action:level.manage', '管理关卡', False),
    ('action:level.review', '审核通关', False),
    ('action:level.comment', '关卡评论', True),

    # ── 打卡 ──
    ('page:checkins', '打卡页', False),
    ('action:checkin.create', '打卡', False),
    ('action:checkin.qrcode', '展示签到二维码', False),
    ('action:checkin.refresh', '刷新打卡', True),

    # ── 比赛 ──
    ('page:competitions', '比赛页', False),
    ('action:competition.view', '查看比赛', True),
    ('action:competition.create', '创建比赛', False),
    ('action:competition.update', '编辑比赛', False),
    ('action:competition.archive', '归档比赛', False),

    # ── 智能体 ──
    ('page:agent', '智能体页', False),
    ('action:agent.chat', '发起对话', False),
    ('action:agent.history', '查看会话历史', False),
    ('action:agent.operate', '智能体代操作', False),

    # ── 日志 ──
    ('page:logs', '操作记录页', True),

    # ── 可视化座位 ──
    ('page:seats', '座位图页', False),
    ('action:seats.move', '移动自己的小人', False),
    ('action:seats.status', '设置状态与形象', False),
    ('action:seats.bubble', '冒气泡', False),
    ('action:seats.chat', '在大厅发言', False),
    ('action:seats.manage', '编辑实验室布局与大厅管理', False),

    # ── 系统（仅 superadmin） ──
    ('page:permissions', '权限矩阵页', False),
    ('action:manage.roles', '角色管理', False),
    ('action:manage.permissions', '权限矩阵维护', False),
    ('action:manage.override', '成员权限覆盖', False),

    # ── 主页管理（仅 superadmin） ──
    ('page:homepage', '主页管理页', False),
    ('action:homepage.edit', '主页内容编辑', False),
]

ALL_KEYS = {key for (key, _, _) in PERMISSION_POINTS}

# 矩阵上"仅 superadmin 可见且可交互"的系统区权限点（用于权限不由矩阵篡夺自身）
MANAGE_KEYS = {'action:manage.roles', 'action:manage.permissions', 'action:manage.override',
               'page:homepage', 'action:homepage.edit'}

# 权限点在矩阵里展示的分组顺序：[(group_label, [keys...]), ...]
PERMISSION_GROUPS = [
    ('框架', ['page:workbench', 'action:notifications', 'page:notifications', 'page:profile', 'action:profile.edit', 'action:profile.status']),
    ('成员', ['page:members', 'page:member.detail', 'page:groups',
              'action:member.create', 'action:member.update', 'action:member.active',
              'action:member.reset_password', 'action:group.manage', 'action:group.members', 'page:loginlogs',
              'action:token.manage']),
    ('公告', ['page:announcements', 'action:announcement.create', 'action:announcement.update']),
    ('动态', ['page:news', 'action:news.manage']),
    ('资产/借用', ['page:assets', 'action:asset.create', 'action:asset.update', 'action:asset.repair',
                    'action:asset.repair_complete', 'action:asset.retire',
                    'page:loans', 'action:loan.create', 'action:loan.cancel', 'action:loan.request_return',
                    'action:loan.review', 'action:loan.issue', 'action:loan.receive']),
    ('请假', ['page:leaves', 'action:leave.create', 'action:leave.cancel', 'action:leave.review']),
    ('任务', ['page:tasks', 'action:task.create', 'action:task.update', 'action:task.delete',
              'action:task.attachment', 'action:task.review']),
    ('打卡', ['page:checkins', 'action:checkin.create', 'action:checkin.qrcode', 'action:checkin.refresh']),
    ('比赛', ['page:competitions', 'action:competition.view', 'action:competition.create',
              'action:competition.update', 'action:competition.archive']),
    ('积分', ['page:leaderboard', 'action:task.score', 'action:points.rules', 'action:points.manual']),
    ('关卡', ['page:levels', 'action:level.manage', 'action:level.review', 'action:level.comment']),
    ('座位', ['page:seats', 'action:seats.move', 'action:seats.status', 'action:seats.bubble',
              'action:seats.chat', 'action:seats.manage']),
    ('智能体', ['page:agent', 'action:agent.chat', 'action:agent.history', 'action:agent.operate']),
    ('日志', ['page:logs', 'action:export.csv']),
    ('邮件', ['page:email', 'action:email.manage']),
    ('系统', ['page:permissions', 'action:manage.roles', 'action:manage.permissions', 'action:manage.override']),
    ('主页', ['page:homepage', 'action:homepage.edit']),
]