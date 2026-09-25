def build_workspace(profile, staff):
    """聚合工作空间快照（API.md 契约）。

    - member：本人（full）；permissions：当前用户有效权限点集合
    - members：所有人公开信息；本人或管理角色附带私有字段（联系方式/备注）
    - logs：最近 200 条操作记录；private 日志仅管理角色或当事人可见
    - 其余数组由各业务模块的 workspace_slice 提供（P2/P3 逐步实现）
    - version：取各模块最新更新时间戳的最大值（整数秒），数据不变则不变
    """
    from apps.accounts.models import MemberProfile, OperationLog
    from apps.accounts.serializers import member_dict, log_dict
    from apps.common.rbac import effective_permissions
    from apps.points.service import totals_map
    from django.utils import timezone

    # 成员总分缓存进 _points_cache，member_dict 直接读取
    point_totals = totals_map()
    from apps.accounts.models import Role
    builtin_roles = {r.code: r for r in Role.objects.all()}
    members_profiles = list(MemberProfile.objects.select_related('user').prefetch_related('roles'))
    for mp in members_profiles:
        mp._points_cache = point_totals.get(mp.user_id, 0)
        # 预取生效角色，避免 member_dict → effective_roles() 逐成员查询（N+1）
        cached = list(mp.roles.all())
        mp._roles_cache = cached if cached else ([builtin_roles[mp.role]] if mp.role in builtin_roles else [])
    members = [member_dict(mp, full=(staff or mp.user_id == profile.user_id)) for mp in members_profiles]

    logs = []
    log_qs = OperationLog.objects.select_related('actor', 'member').order_by('-at')[:200]
    for lg in log_qs:
        if lg.private and not staff and lg.member_id != profile.pk and lg.actor_id != profile.user_id:
            continue
        logs.append(log_dict(lg))

    data = {
        'version': 1,
        'server_time': timezone.now().isoformat(),
        'member': member_dict(profile, full=True),
        'permissions': sorted(effective_permissions(profile)),
        'members': members,
        'assets': [], 'loans': [], 'leaves': [], 'maintenance': [],
        'logs': logs, 'competitions': [],
    }
    from apps.accounts.api import nav_items
    data['nav'] = nav_items(profile)

    ts = [mp.updated for mp in MemberProfile.objects.all()]
    ts += [lg.at for lg in log_qs]

    from apps.inventory.api import workspace_slice as inventory_slice
    from apps.leaves.api import workspace_slice as leaves_slice
    from apps.competitions.api import workspace_slice as competitions_slice
    from apps.tasksapp.api import workspace_slice as tasks_slice
    from apps.checkins.api import workspace_slice as checkins_slice
    from apps.notify.api import workspace_slice as notify_slice
    from apps.points.api import workspace_slice as points_slice
    from apps.levels.api import workspace_slice as levels_slice
    from apps.seats.api import workspace_slice as seats_slice
    from apps.accounts.api import workspace_groups
    data['groups'] = workspace_groups(profile, staff)['groups']
    for fn in (inventory_slice, leaves_slice, competitions_slice, tasks_slice, checkins_slice,
               notify_slice, points_slice, levels_slice, seats_slice):
        part = fn(profile, staff)
        ts.extend(part.pop('_ts', None) or [])
        for key, value in part.items():
            if isinstance(value, list):
                data[key] = data.get(key, []) + value
            else:
                data[key] = value

    real_ts = [t for t in ts if t]
    if real_ts:
        data['version'] = int(max(real_ts).timestamp())
    return data
