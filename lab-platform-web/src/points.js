'use strict';
// 积分中心：排行榜（周/月/累计）+ 管理侧规则配置。发放逻辑在后端流程节点完成。

let _lbCache = {};
let pointsPeriod = 'all';
let _rulesCache = null;

function _mockLeaderboard(period) {
  return {
    period,
    ranking: (db.members || [])
      .filter((m) => m.active)
      .map((m) => ({ memberId: m.id, name: m.name, group: m.group || '', points: m.points || 0 }))
      .sort((a, b) => b.points - a.points)
      .slice(0, 30),
  };
}

async function ensureLeaderboard(period) {
  if (_lbCache[period]) return;
  try {
    _lbCache[period] =
      CONFIG.mode === 'api' ? await API.request('/points/leaderboard?period=' + period) : _mockLeaderboard(period);
  } catch (e) {
    _lbCache[period] = { period, ranking: [] };
  }
  render();
}

function leaderboardPage() {
  const staffConfig = can('action:points.rules');
  const head = heading('积分排行榜', '打卡、任务评分与按时归还都会计入积分，监督成员成长。', btn(`${icon('refresh')} 刷新`, 'lb-refresh'), 'POINTS / 积分中心');
  const tabs = `<div class="view-tabs">${[
    ['week', '本周'],
    ['month', '本月'],
    ['all', '累计'],
  ].map(([k, l]) => `<button class="vt ${pointsPeriod === k ? 'active' : ''}" data-action="lb-period" data-id="${k}">${l}</button>`).join('')}</div>`;
  if (!_lbCache[pointsPeriod]) {
    ensureLeaderboard(pointsPeriod);
    return `${head}${tabs}<section class="panel"><div class="empty">${icon('clock')}加载中…</div></section>`;
  }
  const ranking = _lbCache[pointsPeriod].ranking || [];
  const medals = ['🥇', '🥈', '🥉'];
  const podium = `<div class="lb-podium">${
    ranking.length
      ? ranking
          .slice(0, 3)
          .map(
            (r, i) =>
              `<div class="lb-top${i === 0 ? ' first' : ''}"><span class="lb-medal">${medals[i]}</span>${avatar(member(r.memberId) || { name: r.name })}<strong>${esc(r.name)}</strong><small>${esc(r.group || '—')}</small><b>${r.points}<i>分</i></b></div>`,
          )
          .join('')
      : `<div class="empty small">${icon('trophy')}暂无积分数据</div>`
  }</div>`;
  const p = paginate(ranking, typeof window !== 'undefined' && window.innerHeight < 760 ? 5 : 7);
  const rows = p.rows
    .map(
      (r, i) =>
        `<div class="lb-row"><span class="lb-rank">${i + 1}</span><strong>${esc(r.name)}</strong><small class="muted">${esc(r.group || '—')}</small><button class="text-btn" data-action="member-detail" data-id="${esc(r.memberId)}">查看</button><span class="lb-pts">${r.points}<i>分</i></span></div>`,
    )
    .join('');
  const rankPanel = () => `${podium}<section class="panel"><div class="panel-head"><div><h2>全部排行</h2><p>${{ week: '本周', month: '本月', all: '累计' }[pointsPeriod]}积分</p></div><span class="small muted">共 ${ranking.length} 人</span></div><div class="lb-list">${rows || `<div class="empty small">${icon('users')}暂无记录</div>`}</div>${p.footer}</section>`;
  const rulesPanel = () => pointsRulesCard();
  return `<div class="page-fit">${head}${tabs}${uiTab('lb', staffConfig ? [['rank', '排行榜', rankPanel], ['rules', '积分规则', rulesPanel]] : [['rank', '排行榜', rankPanel]])}</div>`;
}

async function ensureRules() {
  if (_rulesCache) return;
  try {
    _rulesCache = CONFIG.mode === 'api' ? await API.request('/points/rules') : [];
  } catch (e) {
    _rulesCache = [];
  }
  render();
}

function pointsRulesCard() {
  if (!_rulesCache) {
    ensureRules();
    return '';
  }
  const rows = _rulesCache
    .map(
      (r) =>
        `<div class="rule-row"><div><strong>${esc(r.label)}</strong><small class="mono muted">${esc(r.key)}</small></div><div class="row" style="gap:10px"><label class="small muted">分值 <input type="number" class="rule-points" data-key="${esc(r.key)}" min="0" max="1000" value="${r.points}" style="width:64px"></label><label class="check-label"><input type="checkbox" class="rule-enable" data-key="${esc(r.key)}" ${r.enabled ? 'checked' : ''}> 启用</label></div></div>`,
    )
    .join('');
  return `<section class="panel"><div class="panel-head"><div><h2>积分规则</h2><p>设置各项单位分值，保存后立即生效（仅管理可见）</p></div>${btn('保存规则', 'rule-save', 'primary')}</div><div class="rule-list">${rows}</div></section>`;
}

function lbPeriod(mode) {
  pointsPeriod = ['week', 'month', 'all'].includes(mode) ? mode : 'all';
  render();
}

async function rulesSave() {
  const rules = (_rulesCache || []).map((r) => ({
    key: r.key,
    points: Number(document.querySelector(`.rule-points[data-key="${r.key}"]`)?.value ?? r.points) || 0,
    enabled: !!document.querySelector(`.rule-enable[data-key="${r.key}"]`)?.checked,
  }));
  if (CONFIG.mode === 'api') {
    _rulesCache = await API.request('/points/rules/save', { method: 'POST', body: JSON.stringify({ rules }) });
  } else {
    _rulesCache = rules;
  }
  render();
  toast('积分规则已保存');
}

const POINTS_ACTIONS = {
  'lb-period': lbPeriod,
  'lb-refresh': () => {
    _lbCache = {};
    render();
  },
  'rule-save': rulesSave,
};
window.POINTS_ACTIONS = POINTS_ACTIONS;
window.leaderboardPage = leaderboardPage;