"""技能关卡的进阶体系：经验值/水平等级、荣誉标章（全量派生，无需单独落表）。

原则：
- 水平按累计 EXP 分段；EXP 由审核通过时累计到 MemberProfile.level_exp。
- 标章全部按通过记录派生（通过数/档位/技能线全通/首个通过），无独立表，
  改规则只动这里；前端在成员详情「成长」区与关卡页展示持有/未持有态。
"""

from apps.levels.models import PassRecord

# 头衔分段（EXP 下限）：一穿 ≈ 60 EXP（3★×20），几关即可升段，保持激励密度
RANK_TIERS = [
    (0, '学员'),
    (200, '工匠'),
    (600, '专家'),
    (1500, '大师'),
]

# 徽章定义（skill 类按技能线动态生成）
BADGE_DEFS = [
    {'key': 'first_pass', 'title': '新手上路', 'desc': '通过任意 1 关', 'tier': 1},
    {'key': 'pass_3', 'title': '三关掌握', 'desc': '累计通过 3 关', 'tier': 2},
    {'key': 'pass_6', 'title': '六关熟练', 'desc': '累计通过 6 关', 'tier': 2},
    {'key': 'pass_10', 'title': '十关精通', 'desc': '累计通过 10 关', 'tier': 3},
    {'key': 'stars_9', 'title': '满档水准', 'desc': '累计 9 挡（三档通过 3 关）', 'tier': 3},
    {'key': 'first_bonus', 'title': '率先通过', 'desc': '成为某关首个通过者', 'tier': 1},
]

# 技能线全体通关徽章（链名 → 图标代号）
SKILL_CHAINS = ['51单片机', '物联网', '电赛', '无人机', '嵌入式', '其他']
CHAIN_EMBLEMS = {'51单片机': 'chip', '物联网': 'antenna', '电赛': 'weld', '无人机': 'wing', '嵌入式': 'core', '其他': 'gear'}


def rank_title(exp):
    """EXP → 头衔（学员→工匠→专家→大师）。"""
    title = RANK_TIERS[0][1]
    for threshold, t in RANK_TIERS:
        if exp >= threshold:
            title = t
    return title


def rank_progress(exp):
    """返回头衔与到下一段位的进度，供前端渲染经验条。"""
    title = rank_title(exp)
    cur_thr = 0
    nxt_thr = None
    nxt_title = title
    for i, (threshold, t) in enumerate(RANK_TIERS):
        if exp >= threshold:
            cur_thr = threshold
        if exp < threshold and nxt_thr is None:
            nxt_thr = threshold
            nxt_title = t
    if nxt_thr is None:
        # 已是最高段位：进度满
        return {'title': title, 'exp': exp, 'nextTitle': title, 'nextExp': None,
                'left': 0, 'pct': 100, 'percent': 100}
    span = nxt_thr - cur_thr
    pct = 0 if span <= 0 else round((exp - cur_thr) * 100 / span)
    return {'title': title, 'exp': exp, 'nextTitle': nxt_title, 'nextExp': nxt_thr,
            'left': nxt_thr - exp, 'pct': max(0, min(100, pct))}


def _all_badge_defs():
    out = list(BADGE_DEFS)
    for c in SKILL_CHAINS:
        if c in CHAIN_EMBLEMS:
            out.append({'key': f'chain_{c}', 'title': f'{c}精通',
                        'desc': f'通过「{c}」全部关卡', 'tier': 2,
                        'chain': c, 'emblem': CHAIN_EMBLEMS[c]})
    return out


def member_badges(member, pass_qs=None):
    """计算某成员（User）的徽章持有状态与简要战绩。

    返回 {'badges': [{def+ earned}], 'passCount', 'stars', 'chains': {chain: 通关数}, 'firstPassCount'}
    """
    if pass_qs is None:
        pass_qs = PassRecord.objects.filter(member=member, status__in=['passed', 'done']).select_related('level')
    rows = list(pass_qs)
    by_level = {}
    first_count = 0
    for r in rows:
        if r.level_id not in by_level or by_level[r.level_id] < r.stars:
            by_level[r.level_id] = r.stars
        if r.first_pass:
            first_count += 1
    chain_counts = {}
    for r in rows:
        chain = (getattr(r.level, 'chain', '') or '其他')
        chain_counts[chain] = chain_counts.get(chain, 0) + 1
    # 技能线是否全通关：与库内该链关卡总数比对
    from apps.levels.models import Level
    chain_totals = {}
    for lv in Level.objects.all():
        chain_totals[lv.chain] = chain_totals.get(lv.chain, 0) + 1
    stars = sum(by_level.values())
    count = len(by_level)
    badges = []
    for b in _all_badge_defs():
        key = b['key']
        if key == 'first_pass':
            earned = count >= 1
        elif key == 'pass_3':
            earned = count >= 3
        elif key == 'pass_6':
            earned = count >= 6
        elif key == 'pass_10':
            earned = count >= 10
        elif key == 'stars_9':
            earned = stars >= 9
        elif key == 'first_bonus':
            earned = first_count >= 1
        elif key.startswith('chain_'):
            chain = key[len('chain_'):]
            earned = chain_counts.get(chain, 0) >= max(chain_totals.get(chain, 1), 1) and chain_counts.get(chain, 0) > 0
        else:
            earned = False
        badges.append({**b, 'earned': earned, 'progress': {
            'chain': chain_counts.get(b.get('chain', ''), 0),
            'total': chain_totals.get(b.get('chain', ''), 1)} if key.startswith('chain_') else None})
    return {'badges': badges, 'passCount': count, 'stars': stars,
            'chains': chain_counts, 'firstPassCount': first_count}


def my_payload(member):
    """供 /levels/mine 与 workspace 快照输出：头衔 + 徽章 + 战绩。"""
    stats = member_badges(member)
    prof = getattr(member, 'member_profile', None)
    exp = prof.level_exp if prof else 0
    return {
        'exp': exp, 'rankTitle': rank_title(exp),
        'passCount': stats['passCount'], 'stars': stats['stars'],
        'chains': stats['chains'], 'firstPassCount': stats['firstPassCount'],
        'badges': stats['badges'],
    }