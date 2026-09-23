'use strict';
// 通知中心：站内通知列表（分页/类型筛选）+ 已读管理（单条/全部）。

let _notifyCache = null; // {items, total, unread}

const NOTIFY_KIND_LABEL = {
  loan_apply: '借用申请', loan_reviewed: '借用审批', loan_issued: '借用发放',
  loan_return_requested: '归还申请', loan_returned: '归还验收', loan_overdue: '借用逾期',
  leave_apply: '请假申请', leave_reviewed: '请假审批',
  task_assigned: '任务指派', task_completed: '任务完成', task_scored: '任务评分', task_due: '任务到期',
  competition_published: '比赛发布', competition_deadline: '报名截止', competition_start: '开赛提醒',
  announcement_published: '公告', asset_repaired: '维修完成',
  points_changed: '积分', member_joined: '成员加入',
};
const NOTIFY_FILTERS = [
  ['', '全部'], ['loan', '借用'], ['leave', '请假'], ['task', '任务'],
  ['competition', '比赛'], ['announcement', '公告'], ['asset', '资产'],
  ['points', '积分'], ['member', '成员'],
];
const NOTIFY_PAGE_SIZE = 8;

function _notifyKindLabel(kind) {
  return NOTIFY_KIND_LABEL[kind] || kind;
}
function _notifyIcon(kind) {
  if (kind.startsWith('loan') || kind.startsWith('leave')) return 'swap';
  if (kind.startsWith('task')) return 'task';
  if (kind.startsWith('competition')) return 'trophy';
  if (kind.startsWith('announcement')) return 'bell';
  if (kind.startsWith('asset')) return 'tool';
  if (kind.startsWith('points')) return 'trophy';
  return 'chat';
}

async function ensureNotify() {
  const type = filter || '';
  const resp = await API.request(
    `/notifications?page=${page}&pageSize=${NOTIFY_PAGE_SIZE}${type ? `&type=${type}` : ''}`);
  resp.page = page;
  resp.type = type;
  _notifyCache = resp;
  return _notifyCache;
}

function notificationsPage() {
  const type = filter || '';
  if (!_notifyCache || _notifyCache.page !== page || _notifyCache.type !== type) {
    ensureNotify().then(() => render());
    return `${heading('通知中心', '审批结果、任务进展与系统提醒都会在这里出现。', '', 'NOTIFICATIONS / 消息中心')}<section class="panel"><div class="empty">${icon('bell')}加载中…</div></section>`;
  }
  const { items = [], total = 0, unread = 0 } = _notifyCache;
  const count = Math.max(1, Math.ceil(total / NOTIFY_PAGE_SIZE));
  const tabs = `<div class="toolbar" style="border-top:0"><select id="filter" aria-label="类型筛选" style="max-width:180px">${options(
    NOTIFY_FILTERS.map(([v, l]) => [v, l]), filter, '')}</select><span class="small muted" style="margin-left:auto">共 ${total} 条 · ${unread} 条未读</span></div>`;
  const list = items.length
    ? items
        .map(
          (n) => `<article class="panel ann-card ${n.read ? '' : 'unread'}"><div class="ann-head"><div class="row" style="gap:9px;min-width:0"><span class="hardware-icon" style="width:30px;height:30px">${icon(_notifyIcon(n.kind))}</span><div style="min-width:0"><h3 style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(n.title)}</h3><small class="muted">${esc(_notifyKindLabel(n.kind))} · ${fmt(n.created, true)}</small></div></div><span style="margin-left:auto;flex-shrink:0">${n.read ? '' : badge('未读')}</span></div>${n.body ? `<div class="ann-body" style="font-size:12px;line-height:1.7">${esc(n.body)}</div>` : ''}<div class="ann-foot">${recordButton('查看', 'notification-open', n.id)}${n.read ? '' : recordButton('标为已读', 'notification-read', n.id)}</div></article>`,
        )
        .join('')
    : empty('暂无通知', '业务动态会以通知的形式出现在这里。');
  const pager = `<div class="pagination"><span>第 ${page} / ${count} 页</span><div class="row" style="gap:6px">${btn('上一页', 'page', 'small', `data-value="${page - 1}" ${page === 1 ? 'disabled' : ''}`)}<button class="current" disabled>${page}</button>${btn('下一页', 'page', 'small', `data-value="${page + 1}" ${page === count ? 'disabled' : ''}`)}</div></div>`;
  return `<div class="page-fit">${heading('通知中心', '审批结果、任务进展与系统提醒都会在这里出现。', btn(`${icon('check')} 全部已读`, 'notification-read-all', 'primary') + btn(`${icon('refresh')} 刷新`, 'notifications-refresh'), 'NOTIFICATIONS / 消息中心')}<section class="panel">${tabs}<div class="ann-list">${list}</div>${pager}</section></div>`;
}

function _markRead(nid) {
  const hit = (_notifyCache?.items || []).find((n) => n.id === nid);
  if (hit && !hit.read) hit.read = true;
}

// 本地同步快照里的通知与未读数，不重拉 workspace
function _syncLocalRead(nid) {
  const hit = (db.notifications || []).find((n) => n.id === nid);
  if (hit && !hit.read) {
    hit.read = true;
    if ((db.unread_notifications || 0) > 0) db.unread_notifications -= 1;
  }
}
function _syncLocalReadAll() {
  db.unread_notifications = 0;
  for (const n of db.notifications || []) n.read = true;
}
function _refreshBell() {
  const bell = document.querySelector('button[data-action="notifications"]');
  if (!bell) return;
  const total = pendingCount() + (db.unread_notifications || 0);
  const dot = bell.querySelector('.notification-dot');
  if (total > 0 && !dot) bell.insertAdjacentHTML('beforeend', '<i class="notification-dot"></i>');
  else if (total === 0 && dot) dot.remove();
}
// 弹窗打开时只重建“待办与通知”弹窗；通知中心页只重建内容区；其余才整页 render
function _refreshNotifyUi() {
  const d = document.querySelector('#modal');
  if (d && d.open && typeof notifyDropdown === 'function') {
    notifyDropdown();
    return;
  }
  if (view === 'notifications') {
    const content = document.querySelector('#content');
    if (content) {
      content.innerHTML = notificationsPage();
      return;
    }
  }
  render();
}

async function notificationRead(id) {
  await API.request(`/notifications/${id}/read`, { method: 'POST', body: '{}' });
  _markRead(id);
  _syncLocalRead(id);
  if ((_notifyCache?.unread ?? 0) > 0) _notifyCache.unread -= 1;
  _refreshBell();
  _refreshNotifyUi();
  toast('已标记为已读');
}

async function notificationOpen(id) {
  const n = (_notifyCache?.items || []).find((x) => x.id === id) || (db.notifications || []).find((x) => x.id === id);
  await API.request(`/notifications/${id}/read`, { method: 'POST', body: '{}' });
  _markRead(id);
  _syncLocalRead(id);
  _refreshBell();
  if (n && n.link) {
    document.querySelector('#modal')?.close();
    go(n.link);
  } else {
    render();
  }
}

async function notificationReadAll() {
  await API.request('/notifications/read-all', { method: 'POST', body: '{}' });
  if (_notifyCache) _notifyCache.unread = 0;
  for (const n of _notifyCache?.items || []) n.read = true;
  _syncLocalReadAll();
  _refreshBell();
  _refreshNotifyUi();
  toast('全部通知已读');
}

function notifyRefresh() {
  _notifyCache = null;
  render();
}

window.notificationsPage = notificationsPage;
window.NOTIFY_ACTIONS = {
  'notification-read': notificationRead,
  'notification-open': notificationOpen,
  'notification-read-all': notificationReadAll,
  'notifications-refresh': notifyRefresh,
};
