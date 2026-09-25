'use strict';
// 成员独立详情页：hash 路由 #member/m3，数据全部来自 workspace 快照聚合（无额外接口）。
// 可视化图表为纯 CSS/SVG，不引入第三方库。

function _memberTasks(mid) {
  return (db.tasks || []).filter((t) => t.assigneeId === mid || t.creatorId === mid);
}

// 最近 6 个月任务分布：绿色=已完成，蓝色=其余状态（柱状 + 分割段）
function taskTrendBars(mid) {
  const tasks = _memberTasks(mid);
  const now = new Date();
  const months = [];
  for (let i = 5; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    months.push({ key: `${d.getFullYear()}-${d.getMonth()}`, label: `${d.getMonth() + 1}月`, total: 0, done: 0 });
  }
  const indexOf = (dt) => months.findIndex((x) => x.key === `${dt.getFullYear()}-${dt.getMonth()}`);
  for (const t of tasks) {
    const i = indexOf(new Date(t.created));
    if (i >= 0) months[i].total++;
    const doneAt = t.completedAt || (t.status === 'done' ? t.updated : null);
    if (doneAt) {
      const j = indexOf(new Date(doneAt));
      if (j >= 0) months[j].done++;
    }
  }
  const max = Math.max(1, ...months.map((m) => m.total));
  return `<div class="mini-bars">${months
    .map(
      (m) => `<div class="mb-col"><div class="mb-bar-wrap"><div class="mb-bar" style="height:${(m.total / max) * 100}%;${m.total ? '' : 'min-height:0'}" title="${m.label} · ${m.done}/${m.total} 完成"><i class="mb-done" style="height:${m.total ? (m.done / m.total) * 100 : 0}%"></i></div></div><span>${m.label}</span></div>`,
    )
    .join('')}</div><div class="chart-legend"><span><i style="background:#26a078"></i>已完成</span><span><i style="background:#3b5c93"></i>其余</span></div>`;
}

// 近 30 天打卡热力格：1 次浅、2 次中、3+ 次深
let _trendCache = {};

function _mockTrend(mid) {
  const total = member(mid)?.points || 0;
  const days = [];
  const now = new Date();
  for (let i = 29; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i);
    days.push({ day: d.toISOString().slice(0, 10), points: i === 29 ? total : 0 });
  }
  return { total, days };
}

async function ensureTrend(mid) {
  if (_trendCache[mid]) return;
  try {
    _trendCache[mid] = CONFIG.mode === 'api' ? await API.request(`/points/trend/${mid}`) : _mockTrend(mid);
  } catch (e) {
    _trendCache[mid] = { total: member(mid)?.points || 0, days: [] };
  }
  render();
}

function trendBars(mid) {
  const t = _trendCache[mid];
  if (!t || !t.days || !t.days.length) return '';
  // 30 天全 0 时给可读的空态，而不是一排 2px 高的点划线
  const sum = t.days.reduce((s, d) => s + (d.points || 0), 0);
  if (!sum) return `<div class="empty small">${icon('clock')}近 30 天暂无积分变动</div>`;
  const max = Math.max(1, ...t.days.map((d) => d.points));
  return `<div class="mini-bars trend-bars">${t.days
    .map(
      (d) =>
        `<div class="mb-col" style="min-width:5px" title="${d.day} · ${d.points} 分"><div class="mb-bar-wrap"><div class="mb-bar" style="height:${(d.points / max) * 100}%;${d.points ? 'min-height:2px' : ''}"></div></div></div>`,
    )
    .join('')}</div>`;
}

// 近 30 天打卡热力：周一列对齐 + 月份刻度（周列布局，1 次浅、2 次中、3+ 次深）
function checkinHeat(mid) {
  const counts = new Map();
  for (const c of db.checkins || []) {
    if (c.memberId !== mid) continue;
    const k = new Date(c.created).toDateString();
    counts.set(k, (counts.get(k) || 0) + 1);
  }
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const winStart = new Date(today);
  winStart.setDate(winStart.getDate() - 29); // 30 天窗口起点，之前的日期隐藏（不是灰格）
  const start = new Date(today);
  start.setDate(start.getDate() - 29);
  start.setDate(start.getDate() - ((start.getDay() + 6) % 7)); // 起点对齐到所在周的周一
  const weeks = [];
  const marks = [];
  for (let ws = new Date(start); ws <= today; ws.setDate(ws.getDate() + 7)) {
    const cells = [];
    let mark = '';
    for (let i = 0; i < 7; i++) {
      const d = new Date(ws.getFullYear(), ws.getMonth(), ws.getDate() + i);
      if (d > today || d < winStart) {
        cells.push('<span class="heat-cell off"></span>');
        continue;
      }
      if (d.getDate() === 1) mark = `${d.getMonth() + 1}月`;
      const n = counts.get(d.toDateString()) || 0;
      cells.push(
        `<span class="heat-cell${n ? ' on' + (n > 2 ? 3 : n) : ''}" title="${d.getMonth() + 1}/${d.getDate()} · 打卡 ${n} 次">${n || ''}</span>`,
      );
    }
    weeks.push(`<div class="heat-week">${cells.join('')}</div>`);
    marks.push(mark);
  }
  const labels = marks.map((mk, i) => (mk ? `<b style="grid-column:${i + 2};grid-row:1">${mk}</b>` : '')).join('');
  const wd = ['一', '', '三', '', '五', '', ''].map((t) => `<span>${t}</span>`).join('');
  // 周列定宽 22px，月份刻度与热力格共用同一套列模板，保证上下严格对齐
  return `<div class="heatmap-wrap"><div class="heat-months" style="grid-template-columns:20px repeat(${weeks.length},22px)"><span></span>${labels}</div><div class="heat-grid" style="grid-template-columns:20px repeat(${weeks.length},22px)"><div class="heat-wd">${wd}</div><div class="heatmap" style="grid-template-columns:repeat(${weeks.length},22px)">${weeks.join('')}</div></div></div>`;
}

function memberDetailPage(mid) {
  const m = member(mid);
  if (!m) return `${empty('成员不存在', '该成员可能已被删除。')}<div class="controls-wrap">${btn('返回成员列表', 'nav', '', 'data-view="members"')}</div>`;
  if (!can('page:member.detail') && me().id !== mid)
    return `${empty('没有权限查看', '仅管理角色或本人可查看成员详情。')}<div class="controls-wrap">${btn('返回成员列表', 'nav', '', 'data-view="members"')}</div>`;
  const self = me().id === mid;
  const canEdit = editableMember(m);
  const canManage = can('action:manage.override');
  const groups = db.groups || [];
  const g = groups.find((x) => (x.members || []).includes(mid));
  const tasks = _memberTasks(mid).sort((a, b) => Date.parse(b.updated) - Date.parse(a.updated));
  const done = tasks.filter((t) => t.status === 'done').length;
  const loans = (db.loans || []).filter((l) => l.memberId === mid);
  const checkins = (db.checkins || []).filter((c) => c.memberId === mid);
  const logs = visibleLogs().filter((l) => l.memberId === mid);
  // 成长档案（头衔/标章/技能线/近期通过记录）：本人直接用快照，他人走接口缓存
  const mdata = _memberProfileCached(mid);
  const actions = [
    btn('返回成员列表', 'nav', '', 'data-view="members"'),
    ...(canEdit ? [btn('编辑成员', 'member-edit', '', `data-id="${m.id}"`)] : []),
    ...(canManage && !self ? [btn('权限覆盖', 'member-override', '', `data-id="${m.id}"`)] : []),
    ...(can('action:member.reset_password') && !self ? [btn('重置密码', 'member-reset-password', 'danger', `data-id="${m.id}"`)] : []),
  ];
  const head = `${heading(`${esc(m.name)}<span style="font-size:16px;color:#7a7a78;font-weight:400;margin-left:10px">${roleLabel(m)}</span>${mdata ? `<span class="rank-chip" style="margin-left:10px">${esc(mdata.rankTitle || rankTitle(m.exp || 0))} · ${mdata.exp || 0} EXP</span>` : ''}`, `学号 ${esc(m.number)} · ${esc(m.group || '未分组')} · 加入 ${new Date(m.joined).toLocaleDateString('zh-CN')}`, actions.join(''), 'MEMBER / 成员详情')}`;
  const stats = `<div class="stats">${statsCard('参与任务', tasks.length, '件', 'task', '', `<span>${done} 件已完成</span><span>·</span><span>${tasks.length - done} 件推进中</span>`)}${statsCard('完成任务', done, '件', 'check', 'green', `<span>${Math.round(percentage(done, tasks.length || 1))}% 完成率</span>`)}${statsCard('借用记录', loans.length, '笔', 'swap', 'blue', `<span>${loans.filter((l) => ['使用中', '待确认归还'].includes(l.status)).length} 笔进行中</span>`)}${statsCard('累计打卡', checkins.length, '次', 'pin', 'purple', `<span>${new Set(checkins.map((c) => new Date(c.created).toDateString())).size} 天到场</span>`)}</div>`;
  // 积分口径统一：右上角同时给「累计」与「近 30 天」两个数（接口 total 本来就有，之前只展示了累计还标成 30 天）
  const trend = _trendCache[mid];
  const trendSum = trend && Array.isArray(trend.days) ? trend.days.reduce((s, d) => s + (d.points || 0), 0) : null;
  const pointsTotal = trend && trend.total != null ? trend.total : m.points || 0;
  const pointsMeta = trendSum == null ? `累计 ${pointsTotal} 分` : `累计 ${pointsTotal} 分 · 近 30 天 ${trendSum > 0 ? '+' : ''}${trendSum}`;
  const charts = `<div class="chart-duo"><section class="panel"><div class="panel-head"><div><h2>任务趋势</h2><p>最近 6 个月任务分布</p></div><span class="small muted">${done}/${tasks.length} 完成</span></div><div class="chart-body">${tasks.length ? taskTrendBars(mid) : `<div class="empty small">${icon('task')}暂无任务记录</div>`}</div></section><section class="panel"><div class="panel-head"><div><h2>积分</h2></div><span class="small muted" style="white-space:nowrap">${pointsMeta}</span></div><div class="chart-body">${_trendCache[mid] ? trendBars(mid) : (ensureTrend(mid), `<span class="muted small">${icon('clock')} 加载中…</span>`)}</div></section></div><section class="panel"><div class="panel-head"><div><h2>到场热力</h2><p>近 30 天实验室打卡</p></div><span class="small muted">${checkins.filter((c) => { const d = new Date(c.created); const n = new Date(); return n - d < 30 * 86400000; }).length} 次</span></div><div class="chart-body">${checkinHeat(mid)}</div></section>`;
  const side = `<section class="panel profile-panel"><div class="row">${avatar(m)}<div><h1 style="font-size:20px">${esc(m.name)}</h1><p class="muted" style="margin-top:6px">${roleLabel(m)}${g ? ` · ${esc(g.name)}` : ''}</p></div><span style="margin-left:auto">${badge(m.active === false ? '已停用' : memberStatus(m))}</span></div>${details([
    ['学号 / 工号', m.number],
    ['登录账号', self || can('page:members') ? m.username : '—'],
    ['所属小组', g ? `${g.name}（${g.memberCount}/${g.capacity} 人）` : m.group || '未分组'],
    ['研究方向', m.direction || '—'],
    ['联系方式', self || can('page:members') ? m.contact || '—' : '—'],
    ['邮箱', m.email || '—'],
    ['状态备注', m.note || self || can('page:members') ? m.note || '—' : '—'],
    ['最近更新', new Date(m.updated).toLocaleString('zh-CN')],
  ])}</section>`;
  const tasksPanel = `<section class="panel"><div class="panel-head"><div><h2>任务</h2><p>负责与创建的任务</p></div><button class="text-btn" data-action="nav" data-view="tasks">任务看板 ${icon('arrow')}</button></div><div class="member-task-list">${tasks.length ? tasks.map(memberTaskMiniRow).join('') : `<div class="empty small">${icon('task')}暂无任务</div>`}</div></section>`;
  const loansPanel = `<section class="panel"><div class="panel-head"><div><h2>借用记录</h2><p>历史借还与进行中</p></div><button class="text-btn" data-action="nav" data-view="loans">全部记录 ${icon('arrow')}</button></div><div class="table-wrap"><table><thead><tr><th>模块</th><th>状态</th><th>借用时间</th><th>预计归还</th><th>操作</th></tr></thead><tbody>${loans.slice(0, 8).map((l) => `<tr><td>${l.assetIds?.map((id) => `<strong>${esc(asset(id)?.name || id)}</strong>`).join('<br>') || '—'}</td><td>${badge(l.status)}</td><td>${fmt(l.issued || l.created, true)}</td><td>${fmt(l.due, true)}</td><td>${recordButton('详情', 'loan-detail', l.id)}</td></tr>`).join('')}</tbody></table>${loans.length ? '' : `<div class="empty small">${icon('swap')}暂无借用记录</div>`}</div></section>`;
  const logsPanel = `<section class="panel"><div class="panel-head"><div><h2>操作记录</h2><p>该成员的最近足迹</p></div></div><div class="full-log">${logs.slice(0, 8).map((l) => `<div class="activity-item"><strong>${esc(l.actor)}</strong> · ${esc(l.text)}<small>${fmt(l.at, true)}</small></div>`).join('') || `<div class="empty small">${icon('history')}暂无操作记录</div>`}</div></section>`;
  const achievementsPanel = `<section class="panel"><div class="panel-head"><div><h2>成长档案</h2><p>水平 · 荣誉标章 · 技能线 · 通过记录</p></div></div><div class="chart-body">${mdata ? achievementsHTML(mdata) : `<div class="empty small">${icon('trophy')}读取成长档案中…</div>`}</div></section>`;
  _ensureMemberProfile(mid);
  _refreshAchievementsPanel(mid, achievementsPanel);
  return `<div class="page-fit">${head}${stats}<div class="grid-main grid-fill member-fill"><div>${uiTab('member-detail', [
    ['overview', '数据概览', () => charts],
    ['achievements', '成长', () => achievementsPanel],
    ['tasks', '任务', () => tasksPanel],
    ['loans', '借用', () => loansPanel],
    ['logs', '操作记录', () => logsPanel],
  ])}</div><div>${side}</div></div></div>`;
}

// 成员成长档案缓存与异步加载（本人走快照，他人走 /levels/member/<mid>/profile）
const _achCache = {};
function _memberProfileCached(mid) {
  if (mid === me().id) return db.myProfile || null;
  return _achCache[mid] || null;
}
function _ensureMemberProfile(mid) {
  if (!window.memberProfile) return;
  memberProfile(mid, !!_achCache[mid]).then((d) => {
    if (d && !_achCache[mid]) {
      _achCache[mid] = d;
      render();
    }
  });
}
// 成就 tab 依赖异步档案数据：停在成就页且数据未就绪时，到达后原地刷新一次
let _achPoll = null;
function _refreshAchievementsPanel(mid, panelHTML) {
  if (UI_TAB_STATE['member-detail'] !== 'achievements') return;
  if (_memberProfileCached(mid)) return;
  if (_achPoll || mid !== _achPollMid) { clearInterval(_achPoll); _achPoll = null; _achPollMid = mid; }
  if (!_achPoll) {
    _achPollMid = mid;
    _achPoll = setInterval(() => {
      if (_memberProfileCached(_achPollMid)) {
        clearInterval(_achPoll); _achPoll = null;
        if (UI_TAB_STATE['member-detail'] === 'achievements') {
          const body = document.querySelector('#tab-body-member-detail');
          if (body) body.innerHTML = uiTabRender('member-detail');
        }
      }
    }, 400);
  }
}
let _achPollMid = null;

function memberTaskMiniRow(t) {
  return `<div class="todo"><span class="todo-icon ${t.status === 'done' ? '' : 'orange'}">${icon(t.status === 'done' ? 'check' : 'clock')}</span><div>${stack(t.title, `${t.id}${t.groupName ? ' · ' + t.groupName : ''}${t.due ? ' · 截止 ' + fmt(t.due) : ''}`)}</div><div class="row" style="gap:6px">${t.score ? `<span class="score-chip">${'★'.repeat(t.score)}</span>` : ''}${badge(taskStatusLabel(t.status))}${recordButton('查看', 'task-detail', t.id)}</div></div>`;
}

window.MEMBER_ACTIONS = {
  'member-detail': (id) => go('member/' + id),
};
window.memberDetailPage = memberDetailPage;