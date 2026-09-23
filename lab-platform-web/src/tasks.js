'use strict';

const TASK_STATUSES = [
  ['todo', '待办'],
  ['doing', '进行中'],
  ['submitted', '待审核'],
  ['done', '已完成'],
];
const TASK_PRIORITIES = [
  ['low', '低'],
  ['normal', '普通'],
  ['high', '高'],
  ['urgent', '紧急'],
];
const TASK_VIEWS = [
  ['my', '我的任务'],
  ['board', '看板模式'],
  ['member', '按成员'],
  ['group', '按小组'],
  ['query', '查询'],
];
let taskViewMode = 'my';
let taskActiveMember = '';
let taskActiveGroup = '';
let taskQueryState = { q: '', status: '', priority: '', assignee: '', group: '', dueFrom: '', dueTo: '' };
let _boardExpanded = Object.create(null); // 看板列：展开到更多卡片
let _taskRowsExpanded = Object.create(null); // 成员/小组子列表：展开到更多
const BOARD_COL_LIMIT = typeof window !== 'undefined' && window.innerHeight < 740 ? 3 : 4;
const BOARD_COL_EXPAND = 8;

function taskPriorityColor(p) {
  return { low: '', normal: '', high: 'orange', urgent: 'red' }[p] || '';
}
function taskPriorityLabel(p) {
  return (TASK_PRIORITIES.find(([k]) => k === p) || ['', '普通'])[1];
}
function taskStatusLabel(s) {
  return (TASK_STATUSES.find(([k]) => k === s) || ['', s])[1];
}
function taskAssigneeName(id) {
  return member(id)?.name || '待分配';
}

function isSuperadmin() {
  const m = me();
  return !!(m && Array.isArray(m.roles) && m.roles.includes('superadmin'));
}

// 系统管理员不显示「我的任务」栏，默认全量看板
function taskViewsForUser() {
  return isSuperadmin() ? TASK_VIEWS.filter(([k]) => k !== 'my') : TASK_VIEWS;
}
function taskDefaultView() {
  return isSuperadmin() ? 'board' : 'my';
}

// 审核人：可选老师/负责人/系统管理员，默认系统管理员
function taskReviewerPool() {
  return (db.members || []).filter(
    (m) => m.active && (m.role === 'teacher' || m.role === 'manager' || (Array.isArray(m.roles) && m.roles.includes('superadmin'))),
  );
}
function taskDefaultReviewerId() {
  const pool = taskReviewerPool();
  const sup = pool.find((m) => Array.isArray(m.roles) && m.roles.includes('superadmin')) || pool.find((m) => m.role === 'superadmin');
  return sup ? sup.id : (pool[0]?.id || '');
}
function taskReviewerSelect(current = '') {
  const pool = taskReviewerPool();
  return selectField('审核人', 'reviewerId', [['', '不指定'], ...pool.map((m) => [m.id, m.name])], current || taskDefaultReviewerId());
}

function taskByStatus(status) {
  return (db.tasks || []).filter((t) => t.status === status);
}

function tasksPage() {
  // 按当前登录身份修正默认栏（superadmin 无「我的任务」）
  if (!taskViewsForUser().some(([k]) => k === taskViewMode)) taskViewMode = taskDefaultView();
  const todo = taskByStatus('doing').length + taskByStatus('todo').length;
  const done = taskByStatus('done').length;
  const submitted = taskByStatus('submitted').length;
  const total = (db.tasks || []).length;
  const tabs = `<div class="view-tabs" role="tablist">${taskViewsForUser().map(
    ([k, label]) => `<button class="vt ${taskViewMode === k ? 'active' : ''}" data-action="task-view" data-id="${k}" role="tab" aria-selected="${taskViewMode === k}">${label}</button>`,
  ).join('')}</div>`;
  const createBtns = can('action:task.create')
    ? btn(`${icon('users')} 批量布置`, 'task-batch-new') + btn(`${icon('plus')} 新建任务`, 'task-new', 'primary')
    : '';
  const body =
    taskViewMode === 'my' ? myView() :
    taskViewMode === 'board' ? boardView() :
    taskViewMode === 'member' ? memberView() :
    taskViewMode === 'group' ? groupView() : taskQueryView();
  return `<div class="page-fit">${heading('任务看板', '布置、推进、提交与审核，让每件任务都有始有终。', createBtns, 'TASKS / 实验室看板')}<div class="stats">${statsCard('全部任务', total, '件', 'task', '', `<span>${todo} 件待推进</span>`)}${statsCard('已完成', done, '件', 'check', 'green', `<span>${Math.round(percentage(done, total))}% 完成率</span>`)}${statsCard('待办 / 进行中', todo, '件', 'clock', todo > 5 ? 'orange' : '', `<span>${submitted} 件待审核 · ${taskByStatus('urgent').length} 件紧急</span>`)}${statsCard('活跃成员', new Set((db.tasks || []).map((t) => t.assigneeId).filter(Boolean)).size, '人', 'users', 'purple', '<span>参与任务分配</span>')}</div><section class="panel task-board">${tabs}${body}</section></div>`;
}

// ── 我的任务：仅看板列渲染自己负责的任务 ──

function myView() {
  return boardCols((db.tasks || []).filter((t) => t.assigneeId === me()?.id));
}

function boardCols(list) {
  return `<div class="task-board-cols">${
    TASK_STATUSES.map(([key, label]) => {
      const col = (list || []).filter((t) => t.status === key).sort((a, b) => Date.parse(b.updated) - Date.parse(a.updated));
      const limit = _boardExpanded[key] ? BOARD_COL_EXPAND : BOARD_COL_LIMIT;
      const shown = col.slice(0, limit);
      const hidden = col.length - shown.length;
      const more = hidden > 0 ? `<button class="task-col-more" data-action="task-col-more" data-id="${key}">还有 ${hidden} 件 · ${_boardExpanded[key] ? '收起' : '展开'}</button>` : '';
      return `<div class="task-col" data-status="${key}"><div class="task-col-head"><strong>${label}</strong><small>${col.length} 件</small></div><div class="task-col-body">${shown.map(taskCard).join('') || empty(`暂无${label}任务`, '点击新建或从其他列移动。')}</div>${more}</div>`;
    }).join('')
  }</div>`;
}

function boardView() {
  return boardCols(db.tasks || []);
}

function taskCard(t) {
  const g = t.groupName ? `<span class="small muted">${icon('users')} ${esc(t.groupName)}</span>` : '';
  const mine = t.assigneeId === me()?.id;
  const canSubmit = mine && (t.status === 'todo' || t.status === 'doing');
  const canReview = can('action:task.review') && t.status === 'submitted';
  const flow = `${canSubmit ? recordButton('提交', 'task-submit', t.id) : ''}${canReview ? recordButton('审核', 'task-review', t.id) : ''}`;
  return `<article class="task-card" data-id="${esc(t.id)}"><div class="row between"><span class="mono" style="font-size:11px;color:#7a7a78">${esc(t.id)}</span><span class="badge ${taskPriorityColor(t.priority)}">${taskPriorityLabel(t.priority)}</span></div><h4>${esc(t.title)}</h4>${t.description ? `<p class="muted small" style="line-height:1.6">${esc(t.description)}</p>` : ''}<div class="row between" style="margin-top:10px"><span class="small muted">${icon('users')} ${esc(taskAssigneeName(t.assigneeId))}</span>${t.due ? `<span class="small muted">${icon('clock')} ${fmt(t.due, true)}</span>` : ''}</div>${t.reviewerName ? `<div class="small muted" style="margin-top:8px">${icon('shield')} 审核人 · ${esc(t.reviewerName)}</div>` : ''}${g ? `<div class="task-card-group">${icon('users')} ${esc(t.groupName)}</div>` : ''}<div class="task-card-foot">${flow}${recordButton('详情', 'task-detail', t.id)}${recordButton('移动', 'task-move', t.id)}${recordButton('编辑', 'task-edit', t.id)}${recordButton('删除', 'task-delete', t.id)}</div></article>`;
}

// ── 按成员视图 ──

function _taskCountBy(fn) {
  const counts = new Map();
  for (const t of db.tasks || []) {
    const key = fn(t);
    if (!key) continue;
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return counts;
}

function memberView() {
  const counts = _taskCountBy((t) => t.assigneeId);
  const list = db.members
    .filter((m) => m.active)
    .map((m) => ({ m, n: counts.get(m.id) || 0 }))
    .sort((a, b) => b.n - a.n);
  const p = paginate(list, 12);
  const cards = p.rows
    .map(
      ({ m, n }) =>
        `<button class="member-task-card ${taskActiveMember === m.id ? 'active' : ''}" data-action="task-member" data-id="${m.id}"><span class="avatar a${Math.max(0, db.members.indexOf(m)) % 5}">${esc(m.name?.slice(-2) || '—')}</span><strong>${esc(m.name)}</strong><small>${n} 件任务</small>${n ? `<b class="count-chip">${n}</b>` : ''}</button>`,
    )
    .join('');
  const active = taskActiveMember ? member(taskActiveMember) : null;
  const rows = active ? memberTaskRows(active) : '';
  return `<div class="member-task-grid">${cards || empty('暂无成员', '先创建成员账号。')}</div>${p.footer}${rows}`;
}

function memberTaskRows(m, label = `「${m.name}」的任务`) {
  const list = (db.tasks || [])
    .filter((t) => t.assigneeId === m.id)
    .sort((a, b) => Date.parse(b.updated) - Date.parse(a.updated));
  const limit = _taskRowsExpanded[m.id] ? 10 : 4;
  const shown = list.slice(0, limit);
  const hidden = list.length - shown.length;
  const more = hidden > 0 ? `<button class="task-col-more" data-action="task-rows-more" data-id="${m.id}">还有 ${hidden} 件 · ${_taskRowsExpanded[m.id] ? '收起' : '展开'}</button>` : '';
  return `<div class="sub-view"><div class="sub-head"><strong>${esc(label)}</strong><small>${list.length} 件</small><button class="text-btn" data-action="task-clear" data-id="">收起</button></div><div class="member-task-list">${shown.map(taskMiniRow).join('') || empty('暂无任务', '给这位成员指派一个任务吧。')}</div>${more}</div>`;
}

// ── 按小组视图 ──

function groupView() {
  const counts = _taskCountBy((t) => t.groupId);
  const groups = db.groups || [];
  const p = paginate(groups, 8);
  const cards = p.rows
    .map((g) => {
      const n = counts.get(g.id) || 0;
      return `<button class="group-task-card ${taskActiveGroup === g.id ? 'active' : ''}" data-action="task-group" data-id="${g.id}"><span class="group-avatar">${icon('users')}</span><div><strong>${esc(g.name)}</strong><small>${g.memberCount} 人 · ${n} 件任务</small></div>${n ? `<b class="count-chip">${n}</b>` : ''}</button>`;
    })
    .join('');
  const active = taskActiveGroup ? (db.groups || []).find((g) => g.id === taskActiveGroup) : null;
  let rows = '';
  if (active) {
    const list = (db.tasks || []).filter((t) => t.groupId === active.id).sort((a, b) => Date.parse(b.updated) - Date.parse(a.updated));
    const limit = _taskRowsExpanded['g:' + active.id] ? 10 : 4;
    const shown = list.slice(0, limit);
    const hidden = list.length - shown.length;
    const more = hidden > 0 ? `<button class="task-col-more" data-action="task-rows-more" data-id="g:${active.id}">还有 ${hidden} 件 · ${_taskRowsExpanded['g:' + active.id] ? '收起' : '展开'}</button>` : '';
    rows = `<div class="sub-view"><div class="sub-head"><strong>「${esc(active.name)}」的任务</strong><small>${list.length} 件</small><button class="text-btn" data-action="task-clear" data-id="">收起</button></div><div class="member-task-list">${shown.map(taskMiniRow).join('') || empty('暂无小组任务', '新建任务时可指派给小组。')}</div>${more}<p class="privacy-note">小组任务的本组成员均可推进完成。</p></div>`;
  }
  return `<div class="member-task-grid">${cards || empty('暂无小组', '先在“小组管理”里创建小组。')}</div>${p.footer}${rows}`;
}

function taskMiniRow(t) {
  return `<div class="todo"><span class="todo-icon ${t.status === 'done' ? '' : 'orange'}">${icon(t.status === 'done' ? 'check' : 'clock')}</span><div>${stack(t.title, `${t.id}${t.assigneeId ? ' · ' + taskAssigneeName(t.assigneeId) : ''}${t.due ? ' · 截止 ' + fmt(t.due) : ''}`)}</div><div class="row" style="gap:6px">${t.score ? `<span class="score-chip">${'★'.repeat(t.score)}</span>` : ''}${badge(taskStatusLabel(t.status))}${recordButton('查看', 'task-detail', t.id)}</div></div>`;
}

// ── 任务详情页（#task/TASK-xxx） ──

let _taskDetailCache = null;
let _taskDetailPending = false;

async function ensureTaskDetail(tid) {
  if (_taskDetailCache?.task.id === tid) return;
  _taskDetailCache = null;
  _taskDetailPending = true;
  try {
    if (CONFIG.mode === 'api') {
      _taskDetailCache = await API.request(`/tasks/${tid}/detail`);
    } else {
      const t = (db.tasks || []).find((x) => x.id === tid);
      _taskDetailCache = t
        ? {
            task: {
              ...t,
              attachments: t.attachments || [],
              assigneeName: taskAssigneeName(t.assigneeId),
              groupName: (db.groups || []).find((g) => g.id === t.groupId)?.name || '',
            },
            editable:
              can('action:task.update') ||
              !!(t.groupId && (db.groups || []).find((g) => g.id === t.groupId)?.members?.includes(me().id)),
            logs: visibleLogs().filter((l) => l.text && l.text.includes(tid)),
          }
        : { task: null, error: '任务不存在或已被删除。' };
    }
  } catch (err) {
    _taskDetailCache = { task: null, error: err.message };
  } finally {
    _taskDetailPending = false;
  }
  render();
}

function _taskDueText(t) {
  if (!t.due) return { text: '无截止时间', ok: true };
  const diff = Date.parse(t.due) - Date.now();
  if (t.status === 'done') return { text: `${fmt(t.due, true)} 截止`, ok: true };
  if (diff <= 0) return { text: `已于 ${fmt(t.due, true)} 截止 · 逾期`, ok: false };
  const days = Math.floor(diff / 86400000);
  const hours = Math.floor((diff % 86400000) / 3600000);
  if (days > 0) return { text: `还剩 ${days} 天 ${hours} 小时`, ok: true };
  return { text: `还剩 ${hours} 小时 ${Math.floor((diff % 3600000) / 60000)} 分`, ok: true };
}

function _mediaUrl(a) {
  return (a.url || '').startsWith('/') ? a.url : '/' + a.url;
}
function _isImage(a) {
  return /\.(jpg|jpeg|png|gif|webp|avif)$/i.test(a.name || a.url || '');
}
function _isVideo(a) {
  return /\.(mp4|mov)$/i.test(a.name || a.url || '');
}

// 媒体墙：任务详情核心区 —— 图片网格（点击放大）+ 视频内嵌直接播放
function taskMediaWall(task, editable) {
  const atts = task.attachments || [];
  const videos = atts.filter(_isVideo);
  const images = atts.filter(_isImage);
  const other = atts.filter((a) => !_isVideo(a) && !_isImage(a));
  const uploadBtn = editable
    ? btn(`${icon('plus')} 上传图片/视频`, 'task-attachment', 'primary', `data-id="${esc(task.id)}"`)
    : '';
  if (!atts.length)
    return `<section class="panel media-wall"><div class="panel-head"><div><h2>媒体墙</h2><p>成果图片与视频，让工作看得见</p></div>${uploadBtn}</div><div class="media-empty">${icon('image')}<strong>还没有媒体</strong><span>上传图片或视频（≤50MB），视频可直接播放。</span></div></section>`;
  const videoHtml = videos
    .map((v) => `<div class="media-video"><video src="${esc(_mediaUrl(v))}" controls preload="metadata" playsinline></video><small>${esc(v.name)}</small></div>`)
    .join('');
  const imgHtml = images
    .map((a) => `<button class="media-img" data-action="task-lightbox" data-url="${esc(_mediaUrl(a))}" title="${esc(a.name)}" style="background-image:url('${esc(_mediaUrl(a))}')"></button>`)
    .join('');
  const otherHtml = other
    .map((a) => `<a class="att-card att-file" href="${esc(_mediaUrl(a))}" target="_blank" rel="noopener">${icon('file')}<small>${esc(a.name)}</small></a>`)
    .join('');
  return `<section class="panel media-wall"><div class="panel-head"><div><h2>媒体墙</h2><p>${videos.length} 个视频 · ${images.length} 张图片${other.length ? ` · ${other.length} 个文件` : ''}，视频直接播放、图片点击放大</p></div>${uploadBtn}</div><div class="media-scroll">${videoHtml ? `<div class="media-videos">${videoHtml}</div>` : ''}${imgHtml ? `<div class="media-imgs">${imgHtml}</div>` : ''}${otherHtml ? `<div class="media-others">${otherHtml}</div>` : ''}</div></section>`;
}

function taskLightbox(url) {
  const u = (url || '').startsWith('/') ? url : '/' + url;
  modal('媒体预览', `<div class="lightbox"><img src="${esc(u)}" alt="任务媒体"></div>`, '', null, '');
}

function taskDetailPage(tid) {
  const head = `${heading(`<span class="mono" style="font-size:15px;font-weight:500;color:#7a7a78">${esc(tid)}</span>`, '', btn('返回任务看板', 'nav', '', 'data-view="tasks"'), 'TASK / 任务详情')}`;
  if (!tid) return head + empty('任务不存在', '返回任务看板选择其他任务。');
  if (!_taskDetailCache || _taskDetailCache.task.id !== tid || _taskDetailPending) {
    if (!_taskDetailCache || _taskDetailCache.task.id !== tid) ensureTaskDetail(tid);
    return head + `<section class="panel"><div class="empty">${icon('clock')}加载中…</div></section>`;
  }
  const { task, editable, logs, error } = _taskDetailCache;
  if (!task) return head + empty('任务不存在', error || '可能已被删除，返回任务看板。');
  const due = _taskDueText(task);
  const score = task.score ? `${'★'.repeat(task.score)}<small>${task.score}/5</small>` : '';
  const scoreArea =
    task.status === 'done'
      ? task.score
        ? `<span class="score-chip" style="font-size:15px">${'★'.repeat(task.score)}</span><small class="muted" style="margin-left:6px">${task.score}/5 · 已计入负责人积分</small>`
        : can('action:task.score')
          ? `<span class="score-picker">${[1, 2, 3, 4, 5].map((n) => `<button class="star" data-action="task-score" data-id="${esc(task.id)}:${n}" title="评 ${n} 星" aria-label="评 ${n} 星">★</button>`).join('')}<small class="muted" style="margin-left:4px">评分计入负责人积分</small></span>`
          : ''
      : '';
  const mine = task.assigneeId === me()?.id;
  const submitBtn = mine && (task.status === 'todo' || task.status === 'doing')
    ? btn('提交作业', 'task-submit', 'primary', `data-id="${esc(task.id)}"`)
    : '';
  const reviewBtn = can('action:task.review') && task.status === 'submitted'
    ? btn('审核', 'task-review', 'primary', `data-id="${esc(task.id)}"`)
    : '';
  // 待审核任务由审核决定去向，隐藏移动/编辑
  const canMoveEdit = editable && task.status !== 'submitted';
  const actions = (canMoveEdit ? btn('移动', 'task-move', '', `data-id="${esc(task.id)}"`) + btn('编辑', 'task-edit', '', `data-id="${esc(task.id)}"`) : '') +
    (editable && can('action:task.delete') ? btn('删除', 'task-delete', 'danger', `data-id="${esc(task.id)}"`) : '') + submitBtn + reviewBtn;
  const info = details([
    ['状态', taskStatusLabel(task.status)],
    ['优先级', taskPriorityLabel(task.priority)],
    ['负责人', taskAssigneeName(task.assigneeId)],
    ['小组', task.groupName || '—'],
    ['创建人', member(task.creatorId)?.name || '—'],
    ['截止时间', fmt(task.due, true)],
    ['审核人', task.reviewerName || '—'],
    ['提交时间', task.submittedAt ? fmt(task.submittedAt, true) : '—'],
    ['审核人（实审）', task.reviewedByName || '—'],
    ['审核时间', task.reviewedAt ? fmt(task.reviewedAt, true) : '—'],
    ['完成时间', task.completedAt ? fmt(task.completedAt, true) : '—'],
    ['创建时间', fmt(task.created, true)],
  ]);
  const subPanel = `<section class="panel"><div class="panel-head"><div><h2>提交与审核</h2><p>负责人提交的作业与老师审核结果</p></div>${submitBtn || reviewBtn}</div><div class="panel-body">${task.submission ? `<div class="field"><label>提交内容</label><p class="note-text">${esc(task.submission).replace(/\n/g, '<br>')}</p></div>` : `<p class="muted small">${task.status === 'submitted' ? '已提交，等待老师审核。' : '尚未提交作业，负责人可在进行中提交。'}</p>`}${task.reviewOpinion ? `<div class="field" style="margin-top:14px"><label>审核意见</label><p class="note-text">${esc(task.reviewOpinion).replace(/\n/g, '<br>')}</p></div>` : ''}${task.reviewedByName ? `<p class="muted small" style="margin-top:14px">审核人：${esc(task.reviewedByName)}${task.reviewedAt ? ' · ' + fmt(task.reviewedAt, true) : ''}</p>` : ''}</div></section>`;
  const notePanel = `<section class="panel"><div class="panel-head"><div><h2>完成总结</h2><p>完成情况、成果与遗留问题</p></div>${editable ? btn(task.completionNote ? '编辑' : '填写总结', 'task-note', '', `data-id="${esc(task.id)}"`) : ''}</div><div class="panel-body">${task.completionNote ? `<p class="note-text">${esc(task.completionNote).replace(/\n/g, '<br>')}</p>` : `<p class="muted small">${task.status === 'done' ? '已完成，可填写总结归档。' : '尚未填写，任务完成后补充。'}</p>`}</div></section>`;
  const logPanel = `<section class="panel"><div class="panel-head"><div><h2>操作时间线</h2><p>与此任务相关的最新动态</p></div></div><div class="panel-body"><div class="full-log">${logs.map((l) => `<div class="activity-item"><strong>${esc(l.actor || '系统')}</strong> · ${esc(l.text)}<small>${fmt(l.at, true)}</small></div>`).join('') || `<p class="muted small">暂无操作记录</p>`}</div></div></section>`;
  const infoPanel = () => `<section class="panel"><div class="panel-head"><div><h2>基本信息</h2><p>任务关键字段一览</p></div></div><div class="panel-body">${info}</div></section>`;
  return `<div class="page-fit task-detail-page">${head}<section class="panel task-detail-head"><div class="row" style="gap:10px;flex-wrap:wrap">${badge(taskStatusLabel(task.status))}${badge(taskPriorityLabel(task.priority))}${score ? `<span class="score-chip">${score}</span>` : ''}${scoreArea}</div><h1 style="font-size:22px;margin:12px 0 6px">${esc(task.title)}</h1><p class="muted small">${due.ok ? '' : `<b style="color:#d28370">`}${due.text}${due.ok ? '' : '</b>'}</p>${task.description ? `<p class="task-desc">${esc(task.description).replace(/\n/g, '<br>')}</p>` : ''}<div class="task-detail-actions">${actions}</div></section>${taskMediaWall(task, editable)}${uiTab('task-detail', [
    ['info', '基本信息', infoPanel],
    ['sub', '提交与审核', () => subPanel],
    ['note', '完成总结', () => notePanel],
    ['log', '操作时间线', () => logPanel],
  ])}</div>`;
}

function taskNoteForm(tid) {
  const cache = _taskDetailCache;
  modal(
    '完成总结',
    `<div class="field"><label>总结内容（可填写完成情况、成果与遗留问题）</label><textarea name="completionNote" maxlength="2000" style="min-height:150px">${esc((cache?.task?.completionNote || ''))}</textarea></div>`,
    '保存',
    async (f) => {
      await API.request(`/tasks/${tid}/update`, { method: 'POST', body: JSON.stringify({ completionNote: f.get('completionNote') || '' }) });
      audit(`填写任务总结 · ${tid}`);
      await API.load();
      _taskDetailCache = null;
      document.querySelector('#modal')?.close();
      render();
      toast('完成总结已保存');
    },
  );
}

function taskAttachmentForm(tid) {
  modal(
    '上传任务材料',
    `<div class="notice">支持图片 / 视频 / 文档，单文件 ≤ 50MB。材料用于完成留档。</div><div class="field" style="margin-top:18px"><label>选择文件 *</label><input type="file" name="file" id="task-file" accept=".jpg,.jpeg,.png,.gif,.webp,.avif,.mp4,.mov,.pdf,.zip,.rar,.7z,.doc,.docx,.txt,.md,image/*,video/*"></div>`,
    '上传',
    async (f) => {
      const file = f.get('file') || document.querySelector('#task-file')?.files?.[0];
      requirePermission(file && file.name, '请选择文件');
      requirePermission(file.size <= 50 * 1024 * 1024, '附件不能超过 50MB');
      const fd = new FormData();
      fd.append('file', file);
      await API.request(`/tasks/${tid}/attachment`, { method: 'POST', body: fd });
      audit(`上传任务附件 · ${file.name}`);
      await API.load();
      _taskDetailCache = null;
      document.querySelector('#modal')?.close();
      render();
      toast('附件已上传');
    },
  );
}

// ── 查询视图：本地过滤 + 表格分页 ──

function matchTaskQuery(t) {
  const s = taskQueryState;
  if (s.q) {
    const hay = `${t.title} ${t.id} ${t.description || ''} ${taskAssigneeName(t.assigneeId)}`.toLowerCase();
    if (!hay.includes(s.q.toLowerCase())) return false;
  }
  if (s.status && t.status !== s.status) return false;
  if (s.priority && t.priority !== s.priority) return false;
  if (s.assignee && t.assigneeId !== s.assignee) return false;
  if (s.group && t.groupId !== s.group) return false;
  if (s.dueFrom && Date.parse(t.due) < Date.parse(s.dueFrom)) return false;
  if (s.dueTo && Date.parse(t.due) > Date.parse(s.dueTo) + 86399999) return false;
  return true;
}

function taskQueryView() {
  const list = (db.tasks || []).filter(matchTaskQuery).sort((a, b) => Date.parse(b.updated) - Date.parse(a.updated));
  const p = paginate(list, 8);
  const table = dataTable(
    p,
    ['编号', '标题', '负责人', '小组', '状态', '优先级', '截止', '操作'],
    (t) => [
      esc(t.id),
      esc(t.title),
      taskAssigneeName(t.assigneeId) || '—',
      t.groupName || '—',
      badge(taskStatusLabel(t.status)),
      `<span class="badge ${taskPriorityColor(t.priority)}">${taskPriorityLabel(t.priority)}</span>`,
      t.due ? fmt(t.due, true) : '—',
      recordButton('详情', 'task-detail', t.id),
    ],
    ['暂无匹配任务', '调整筛选条件后重试。'],
  );
  const form = `<div class="query-form"><div class="field" style="min-width:200px"><label>关键词</label><input name="tq" id="f-tq" value="${esc(taskQueryState.q)}" placeholder="标题 / 编号 / 负责人"></div>${selectField('状态', 'tq-status', TASK_STATUSES, taskQueryState.status)}${selectField('优先级', 'tq-priority', TASK_PRIORITIES, taskQueryState.priority)}${selectField('负责人', 'tq-assignee', [['', '全部'], ...db.members.filter((m) => m.active).map((m) => [m.id, m.name])], taskQueryState.assignee)}${selectField('小组', 'tq-group', [['', '全部'], ...(db.groups || []).map((g) => [g.id, g.name])], taskQueryState.group)}<div class="field"><label>截止区间</label><div class="row" style="gap:8px"><input type="date" name="tq-from" id="f-tq-from" value="${esc(taskQueryState.dueFrom)}"><input type="date" name="tq-to" id="f-tq-to" value="${esc(taskQueryState.dueTo)}"></div></div></div><div class="row" style="gap:8px;margin-top:12px">${btn('查询', 'task-query-apply', 'primary')}${btn('重置', 'task-query-reset')}</div>`;
  return `<div class="sub-view"><div class="sub-head"><strong>任务查询</strong><small>${list.length} 条结果</small></div>${form}<div class="query-result">${table}</div></div>`;
}

// ── 批量布置：同一任务为多位成员各建一条 ──

function taskBatchForm() {
  const groups = db.groups || [];
  const members = db.members.filter((m) => m.active);
  const pick = members
    .map((m) => `<label class="asset-option"><span>${esc(m.name)} · ${roleLabel(m)}</span><span style="margin-left:auto"><input type="checkbox" name="assigneeIds" value="${esc(m.id)}"></span></label>`)
    .join('');
  modal(
    '批量布置任务',
    `<div class="form-grid">${field('任务标题 *', 'title', '', 60)}${area('任务描述', 'description', '', 500)}${selectField('优先级', 'priority', TASK_PRIORITIES, 'normal')}<div class="field"><label>截止时间</label><input type="datetime-local" name="due"></div>${selectField('所属小组（可选）', 'groupId', [['', '不指派小组'], ...groups.map((g) => [g.id, `${g.name}（${g.memberCount}人）`])], '')}${taskReviewerSelect('')}</div><div class="field" style="margin-top:14px"><label>指派成员 *（为每位成员各建一条任务）</label><div class="asset-picker">${pick || empty('暂无成员', '先创建成员账号。')}</div></div>`,
    '批量布置',
    async (f) => {
      const data = Object.fromEntries(f);
      requirePermission(data.title && data.title.trim(), '请填写任务标题');
      const ids = (f.getAll('assigneeIds') || []).filter(Boolean);
      requirePermission(ids.length > 0, '请至少选择一位成员');
      const payload = {
        title: data.title.trim(),
        description: data.description,
        priority: data.priority,
        reviewerId: data.reviewerId || '',
        groupId: data.groupId || '',
        due: data.due ? new Date(data.due).toISOString() : null,
        assigneeIds: ids,
      };
      await API.request('/tasks/batch', { method: 'POST', body: JSON.stringify(payload) });
      audit(`批量布置任务 · ${payload.title.slice(0, 20)} · ${ids.length} 人`);
      await API.load();
      document.querySelector('#modal').close();
      render();
      toast(`已为 ${ids.length} 位成员布置任务`);
    },
  );
}

// ── 提交作业 ──

function taskSubmitForm(tid) {
  const t = (db.tasks || []).find((x) => x.id === tid);
  requirePermission(t, '任务不存在');
  modal(
    '提交作业',
    `${details([['任务', t.title], ['负责人', taskAssigneeName(t.assigneeId) || '—'], ['审核人', t.reviewerName || '—']])}<div class="field" style="margin-top:18px"><label>提交内容 *（成果、进展、链接等）</label><textarea name="submission" maxlength="4000" style="min-height:150px"></textarea></div><div class="field" style="margin-top:14px"><label>上传附件（可选，≤50MB）</label><input type="file" name="file" id="task-submit-file" accept=".jpg,.jpeg,.png,.gif,.webp,.avif,.mp4,.mov,.pdf,.zip,.rar,.7z,.doc,.docx,.txt,.md,image/*,video/*"></div><p class="privacy-note">提交后任务进入「待审核」列，由老师审核通过并打分，或退回修改后重新提交。</p>`,
    '提交审核',
    async (f) => {
      const submission = (f.get('submission') || '').trim();
      requirePermission(submission, '请填写提交内容');
      const file = f.get('file') || document.querySelector('#task-submit-file')?.files?.[0];
      if (file) requirePermission(file.size <= 50 * 1024 * 1024, '附件不能超过 50MB');
      const fd = new FormData();
      fd.append('submission', submission);
      if (file) fd.append('file', file);
      await API.request(`/tasks/${tid}/submit`, { method: 'POST', body: fd });
      audit(`提交作业 · ${tid}${file ? ` · 附件 ${file.name}` : ''}`);
      await API.load();
      _taskDetailCache = null;
      document.querySelector('#modal').close();
      render();
      toast('已提交，等待老师审核');
    },
  );
}

// ── 审核：通过并打分 / 退回 ──

function taskReviewForm(tid) {
  const t = (db.tasks || []).find((x) => x.id === tid);
  requirePermission(t, '任务不存在');
  const submission = t.submission
    ? `<div class="review-box"><label>提交内容</label><p class="note-text">${esc(t.submission).replace(/\n/g, '<br>')}</p></div>`
    : '';
  modal(
    '审核任务',
    `${details([['任务', t.title], ['负责人', taskAssigneeName(t.assigneeId) || '—'], ['提交时间', t.submittedAt ? fmt(t.submittedAt, true) : '—']])}${submission}<div class="field" style="margin-top:18px"><label>审核决策 *</label><select name="decision" id="f-decision"><option value="approve">通过并打分</option><option value="reject">退回修改</option></select></div><div class="field" id="score-field" style="margin-top:14px"><label>评分 *</label><div class="score-picker" style="font-size:20px">${[1, 2, 3, 4, 5].map((n) => `<button type="button" class="star" data-rv="${n}" title="评 ${n} 星">★</button>`).join('')}</div><input type="hidden" name="score" value="3"></div><div class="field" id="opinion-field" style="margin-top:14px;display:none"><label>退回意见 *</label><textarea name="opinion" maxlength="2000" style="min-height:90px"></textarea></div>`,
    '确认审核',
    async (f) => {
      const decision = f.get('decision');
      const opinion = (f.get('opinion') || '').trim();
      if (decision === 'reject') requirePermission(opinion, '退回时请填写审核意见');
      const score = Number(f.get('score') || 3);
      const payload = { decision, opinion, score: decision === 'approve' ? score : null };
      await API.request(`/tasks/${tid}/review`, { method: 'POST', body: JSON.stringify(payload) });
      audit(`审核任务 · ${tid} · ${decision === 'approve' ? `通过 ${score}★` : '退回'}`);
      await API.load();
      _taskDetailCache = null;
      document.querySelector('#modal').close();
      render();
      toast(decision === 'approve' ? '已通过并打分，积分已发放' : '已退回，成员可修改后重新提交');
    },
  );
  // 决策联动：退回时切换为意见必填
  const d = document.querySelector('#modal');
  if (d) {
    const sel = d.querySelector('#f-decision');
    if (sel) {
      sel.addEventListener('change', () => {
        const reject = sel.value === 'reject';
        const sf = d.querySelector('#score-field');
        if (sf) sf.style.display = reject ? 'none' : '';
        const of = d.querySelector('#opinion-field');
        if (of) of.style.display = reject ? '' : 'none';
      });
    }
    d.querySelectorAll('.star[data-rv]').forEach((b) =>
      b.addEventListener('click', () => {
        d.querySelectorAll('.star').forEach((x) => x.classList.remove('on'));
        b.classList.add('on');
        const h = d.querySelector('[name="score"]');
        if (h) h.value = b.dataset.rv;
      }),
    );
  }
}

// ── 表单与操作 ──

function taskForm(id) {
  const t = id ? (db.tasks || []).find((x) => x.id === id) : null;
  requirePermission(!id || t, '任务不存在');
  const groups = db.groups || [];
  const isSubmitted = t?.status === 'submitted';
  // 待审核状态只能由「提交作业」进入，编辑表单不允许直接选
  const statusSelect = isSubmitted
    ? `<div class="field"><label>看板列</label><select name="status" disabled><option value="submitted" selected>待审核</option></select></div>`
    : selectField('看板列', 'status', TASK_STATUSES.filter(([k]) => k !== 'submitted'), t?.status || 'todo');
  modal(
    id ? '编辑任务' : '新建任务',
    `<div class="form-grid">${field('任务标题 *', 'title', t?.title || '', 60)}${area('任务描述', 'description', t?.description || '', 500)}${statusSelect}${selectField('优先级', 'priority', TASK_PRIORITIES, t?.priority || 'normal')}<div class="field"><label>截止时间</label><input type="datetime-local" name="due" value="${t?.due ? inputDate(t.due) : ''}"></div>${selectField(
      '负责人',
      'assigneeId',
      [['', '待分配'], ...db.members.filter((m) => m.active).map((m) => [m.id, m.name])],
      t?.assigneeId || '',
    )}${selectField('所属小组（可选）', 'groupId', [['', '不指派小组'], ...groups.map((g) => [g.id, `${g.name}（${g.memberCount}人）`])], t?.groupId || '')}${taskReviewerSelect(t?.reviewerId || '')}</div><p class="privacy-note">小组任务的组内成员都能编辑与推进，适合多人协作。</p>`,
    id ? '保存修改' : '创建任务',
    async (f) => {
      const data = Object.fromEntries(f);
      requirePermission(data.title && data.title.trim(), '请填写任务标题');
      const payload = {
        title: data.title.trim(),
        description: data.description,
        priority: data.priority,
        assigneeId: data.assigneeId || '',
        reviewerId: data.reviewerId || '',
        groupId: data.groupId || '',
        due: data.due ? new Date(data.due).toISOString() : null,
      };
      if (!isSubmitted) payload.status = data.status;
      if (id) {
        await API.request(`/tasks/${id}/update`, { method: 'POST', body: JSON.stringify(payload) });
        audit(`更新任务 ${t.id} ${payload.title.slice(0, 20)}`);
      } else {
        await API.request('/tasks', { method: 'POST', body: JSON.stringify(payload) });
        audit(`创建任务 ${payload.title.slice(0, 20)}`);
      }
      await API.load();
      _taskDetailCache = null;
      document.querySelector('#modal').close();
      render();
      toast(id ? '任务已更新' : '任务已创建');
    },
  );
}

function taskMove(id) {
  const t = (db.tasks || []).find((x) => x.id === id);
  requirePermission(t, '任务不存在');
  // 待审核状态只能由「提交作业」进入，移动目标排除 submitted
  const next = TASK_STATUSES.filter(([k]) => k !== 'submitted' && k !== t.status)
    .map(([k, l]) => `<option value="${k}">${l}</option>`)
    .join('');
  modal(
    '移动任务到',
    `${details([['当前状态', taskStatusLabel(t.status)], ['任务', t.title]])}<div class="field" style="margin-top:18px"><label>目标列 *</label><select name="status">${next}</select><span class="hint" id="move-hint"></span></div><div class="field" style="margin-top:14px"><label>完成总结（移动到“已完成”时填写，可跳过）</label><textarea name="completionNote" maxlength="2000" style="min-height:90px;opacity:.4">${esc(t.completionNote || '')}</textarea></div>`,
    '确认移动',
    async (f) => {
      const status = f.get('status');
      requirePermission(status && status !== t.status, '请选择不同的目标列');
      const payload = { status };
      if (status === 'done') payload.completionNote = (f.get('completionNote') || '').trim();
      await API.request(`/tasks/${id}/update`, { method: 'POST', body: JSON.stringify(payload) });
      audit(`任务 ${t.id} 状态 → ${taskStatusLabel(status)}`);
      await API.load();
      _taskDetailCache = null;
      document.querySelector('#modal').close();
      render();
      toast(`已移到「${taskStatusLabel(status)}」${status === 'done' ? '，可到详情页上传材料' : ''}`);
    },
  );
  // 目标列联动：仅勾选"已完成"时高亮总结输入
  const statusEl = document.querySelector('[name="status"]');
  if (statusEl) {
    statusEl.addEventListener('change', () => {
      const done = statusEl.value === 'done';
      const area = statusEl.closest('form')?.querySelector('[name="completionNote"]');
      document.querySelector('#move-hint').textContent = done ? '任务将标记完成，可在详情页补充材料。' : '';
      if (area) area.style.opacity = done ? 1 : 0.4;
    });
  }
}

function taskDeleteConfirm(id) {
  const t = (db.tasks || []).find((x) => x.id === id);
  requirePermission(t, '任务不存在');
  confirmation(
    '删除任务',
    `确认删除「${t.title}」？此操作不可恢复。`,
    '',
    {},
    async () => {
      await API.request(`/tasks/${id}/delete`, { method: 'POST', body: JSON.stringify({}) });
      audit(`删除任务 ${t.id} ${t.title.slice(0, 20)}`);
      await API.load();
      _taskDetailCache = null;
      render();
    },
  );
}

// 把三个函数挂到全局给 app.js 和 FORM_ACTIONS 用
async function scoreTask(tid, score) {
  if (!(score >= 1 && score <= 5)) return;
  if (CONFIG.mode === 'api') {
    await API.request(`/tasks/${tid}/score`, { method: 'POST', body: JSON.stringify({ score }) });
    await API.load();
  } else {
    const t = (db.tasks || []).find((x) => x.id === tid);
    if (t) t.score = score;
    audit(`任务评分 · ${tid} ${score}★`);
    localStorage.setItem(DB_KEY, JSON.stringify(db));
  }
  _taskDetailCache = null;
  render();
  toast('评分已提交，积分已发放');
}

const TASK_ACTIONS = {
  'task-new': () => taskForm(null),
  'task-batch-new': () => taskBatchForm(),
  'task-submit': taskSubmitForm,
  'task-review': taskReviewForm,
  'task-edit': taskForm,
  'task-move': taskMove,
  'task-delete': taskDeleteConfirm,
  'task-detail': (id) => go('task/' + id),
  'task-lightbox': taskLightbox,
  'task-note': taskNoteForm,
  'task-attachment': taskAttachmentForm,
  'task-score': (payload) => {
    const [tid, score] = String(payload).split(':');
    scoreTask(tid, Number(score));
  },
  'task-view': (mode) => {
    taskViewMode = taskViewsForUser().some(([k]) => k === mode) ? mode : taskDefaultView();
    render();
  },
  'task-query-apply': () => {
    const read = (name) => document.querySelector(`[name="${name}"]`)?.value || '';
    taskQueryState = {
      q: read('tq'),
      status: read('tq-status'),
      priority: read('tq-priority'),
      assignee: read('tq-assignee'),
      group: read('tq-group'),
      dueFrom: read('tq-from'),
      dueTo: read('tq-to'),
    };
    page = 1;
    render();
  },
  'task-query-reset': () => {
    taskQueryState = { q: '', status: '', priority: '', assignee: '', group: '', dueFrom: '', dueTo: '' };
    page = 1;
    render();
  },
  'task-member': (mid) => {
    taskActiveMember = taskActiveMember === mid ? '' : mid;
    taskActiveGroup = '';
    render();
  },
  'task-group': (gid) => {
    taskActiveGroup = taskActiveGroup === gid ? '' : gid;
    taskActiveMember = '';
    render();
  },
  'task-col-more': (key) => {
    _boardExpanded[key] = !_boardExpanded[key];
    render();
  },
  'task-rows-more': (key) => {
    _taskRowsExpanded[key] = !_taskRowsExpanded[key];
    render();
  },
  'task-clear': () => {
    taskActiveMember = '';
    taskActiveGroup = '';
    _taskRowsExpanded = Object.create(null);
    render();
  },
};
window.TASK_ACTIONS = TASK_ACTIONS;
window.tasksPage = tasksPage;
window.taskDetailPage = taskDetailPage;