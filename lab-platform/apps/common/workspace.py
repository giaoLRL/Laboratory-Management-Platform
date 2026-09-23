def build_workspace(profile, staff):
    """聚合工作空间快照（API.md 契约）。

    - members：所有人公开信息；本人或管理角色附带私有字段（联系方式/备注）
    - logs：最近 200 条操作记录；private 日志仅管理角色或当事人可见
    - 其余数组由各业务模块的 workspace_slice 提供（P2/P3 逐步实现）
    - version：取各模块最新更新时间戳的最大值（整数秒），数据不变则不变
    """
    from apps.accounts.models import MemberProfile, OperationLog
    from apps.accounts.serializers import member_dict, log_dict

    members = [
        member_dict(mp, full=(staff or mp.user_id == profile.user_id))
        for mp in MemberProfile.objects.select_related('user')
    ]

    logs = []
    log_qs = OperationLog.objects.select_related('actor', 'member').order_by('-at')[:200]
    for lg in log_qs:
        if lg.private and not staff and lg.member_id != profile.pk and lg.actor_id != profile.user_id:
            continue
        logs.append(log_dict(lg))

    data = {
        'version': 1,
        'member': member_dict(profile, full=True),
        'members': members,
        'assets': [], 'loans': [], 'leaves': [], 'maintenance': [],
        'logs': logs, 'competitions': [],
    }

    ts = [mp.updated for mp in MemberProfile.objects.all()]
    ts += [lg.at for lg in log_qs]

    from apps.inventory.api import workspace_slice as inventory_slice
    from apps.leaves.api import workspace_slice as leaves_slice
    from apps.competitions.api import workspace_slice as competitions_slice
    from apps.tasksapp.api import workspace_slice as tasks_slice
    from apps.checkins.api import workspace_slice as checkins_slice
    for fn in (inventory_slice, leaves_slice, competitions_slice, tasks_slice, checkins_slice):
        part = fn(profile, staff)
        ts.extend(part.pop('_ts', None) or [])
        for key, value in part.items():
            data[key] = data.get(key, []) + value

    real_ts = [t for t in ts if t]
    if real_ts:
        data['version'] = int(max(real_ts).timestamp())
    return data
