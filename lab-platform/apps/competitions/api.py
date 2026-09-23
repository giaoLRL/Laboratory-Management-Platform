from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.common.ids import next_code
from apps.common.rbac import require
from apps.common.response import ok, fail
from apps.competitions.models import Competition

FORM_FIELDS = (('name', 'name'), ('organizer', 'organizer'), ('level', 'level'), ('category', 'category'),
               ('location', 'location'), ('teamSize', 'team_size'), ('link', 'link'),
               ('summary', 'summary'), ('requirements', 'requirements'))


def _comp_dict(c):
    return {
        'id': c.id, 'name': c.name, 'organizer': c.organizer, 'level': c.level,
        'category': c.category, 'registrationStart': c.registration_start,
        'registrationEnd': c.registration_end, 'start': c.start, 'end': c.end,
        'location': c.location, 'ownerId': f'm{c.owner_id}' if c.owner_id else '',
        'teamSize': c.team_size, 'link': c.link, 'summary': c.summary,
        'requirements': c.requirements, 'stages': c.stages,
        'archived': c.archived, 'created': c.created,
        'status': _status_of(c),
    }


def _status_of(c):
    if c.archived:
        return '已归档'
    now = timezone.now()
    if now < c.registration_start:
        return '未开放'
    if now <= c.registration_end:
        return '报名中'
    if now < c.start:
        return '准备中'
    if now <= c.end:
        return '进行中'
    return '已结束'


def workspace_slice(profile, staff):
    comps = [_comp_dict(c) for c in Competition.objects.all()]
    ts = [c.created for c in Competition.objects.all()]
    return {'competitions': comps, '_ts': ts}


def _validate(d, instance=None):
    """创建/更新共用校验；返回 (clean_data, error_response)。"""
    name = str(d.get('name', '')).strip()
    if not name:
        return None, fail('请填写比赛名称')

    from django.utils.dateparse import parse_datetime
    times = {}
    for key, field in (('registrationStart', 'registration_start'), ('registrationEnd', 'registration_end'),
                       ('start', 'start'), ('end', 'end')):
        raw = d.get(key, getattr(instance, field) if instance is not None else None)
        dt = raw if hasattr(raw, 'isoformat') else parse_datetime(str(raw or ''))
        if not dt:
            return None, fail('请正确填写报名与比赛时间')
        times[field] = dt

    rs, re_, st, en = (times['registration_start'], times['registration_end'],
                       times['start'], times['end'])
    if not (rs < re_ <= st < en):
        return None, fail('时间须满足：报名开始 < 报名截止 <= 比赛开始 < 比赛结束')

    stages = d.get('stages', [] if instance is None else instance.stages)
    if not isinstance(stages, list) or len(stages) > 20:
        return None, fail('流程节点须为 1-20 个的列表')
    clean_stages = []
    for s in stages:
        if not isinstance(s, dict) or not str(s.get('title', '')).strip() or not s.get('at'):
            return None, fail('流程节点须包含 title 与 at')
        clean_stages.append({'title': str(s.get('title'))[:64], 'at': str(s.get('at')),
                             'description': str(s.get('description', ''))[:256]})
    clean_stages.sort(key=lambda s: s['at'])

    link = str(d.get('link', '')).strip()
    if link and not (link.startswith('http://') or link.startswith('https://')):
        return None, fail('官方链接仅支持 http/https')

    data = {'name': name}
    for json_key, field in FORM_FIELDS[1:]:
        data[field] = str(d.get(json_key, getattr(instance, field) if instance else '')).strip()
    data.update({'registration_start': rs, 'registration_end': re_, 'start': st, 'end': en,
                 'stages': clean_stages})
    return data, None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def competitions_create(request):
    if (err := require(request.user, 'action:competition.create', '没有创建比赛的权限')):
        return err
    data, err = _validate(request.data or {})
    if err:
        return err
    comp = Competition.objects.create(id=next_code(Competition, 'COMP'),
                                      owner=request.user, **data)
    from apps.notify.service import create_many, active_members
    create_many(active_members(exclude=request.user), 'competition_published',
                f'新比赛发布 · {data["name"][:40]}',
                f'报名截止 {str(data["registrationEnd"])[:16]} · 开赛 {str(data["start"])[:16]}',
                ref_type='competition', ref_id=comp.id, link='competitions')
    return ok({'id': comp.id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def competitions_update(request, cid):
    if (err := require(request.user, 'action:competition.update', '没有编辑比赛的权限')):
        return err
    try:
        comp = Competition.objects.get(pk=cid)
    except Competition.DoesNotExist:
        return fail('比赛不存在', 404)
    data, err = _validate(request.data or {}, instance=comp)
    if err:
        return err
    for k, v in data.items():
        setattr(comp, k, v)
    comp.save()
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def competitions_archive(request, cid):
    if (err := require(request.user, 'action:competition.archive', '没有归档比赛的权限')):
        return err
    try:
        comp = Competition.objects.get(pk=cid)
    except Competition.DoesNotExist:
        return fail('比赛不存在', 404)
    comp.archived = bool((request.data or {}).get('archived'))
    comp.save()
    return ok()
