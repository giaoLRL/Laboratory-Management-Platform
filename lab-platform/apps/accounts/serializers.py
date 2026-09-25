from apps.common.ids import member_id


def member_dict(p, viewer=None, full=False):
    """按 API.md 契约序列化成员。

    full=True（本人或管理角色）时附带私有字段 contact / note；
    其他成员仅返回公开信息（不含私人联系方式与备注）。
    """
    roles = getattr(p, '_roles_cache', None)
    if roles is None:
        roles = p.effective_roles()
    d = {
        'id': member_id(p.user_id),
        'name': p.name,
        'username': p.user.username,
        'number': p.number,
        'role': p.role,
        'roles': [r.code for r in roles],
        'group': p.group,
        'groupId': p.group_fk_id or '',
        'email': p.email,
        'points': getattr(p, '_points_cache', 0),
        'exp': p.level_exp,
        'direction': p.direction,
        'active': p.active,
        'baseStatus': p.base_status,
        'joined': p.joined,
        'updated': p.updated,
    }
    if full:
        d['contact'] = p.contact
        d['note'] = p.note
        d['mustChangePassword'] = p.must_change_password
        d['mustCompleteProfile'] = p.must_complete_profile
    return d


def log_dict(lg):
    actor_name = ''
    if lg.actor_id:
        prof = getattr(lg.actor, 'member_profile', None)
        actor_name = prof.name if prof else lg.actor.username
    return {
        'id': f'LOG-{lg.pk}',
        'actor': actor_name,
        'memberId': member_id(lg.member_id) if lg.member_id else '',
        'text': lg.text,
        'at': lg.at,
        'private': lg.private,
    }
