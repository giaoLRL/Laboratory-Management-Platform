'use strict';
// 配置、公共工具与数据操作
const CONFIG = { mode: 'api', API_BASE_URL: '/api', timeout: 10000 };
const DB_KEY = 'xinzhan.lab.demo.v1',
  SESSION_KEY = 'xinzhan.lab.session.v1';
const ROLE = { teacher: '指导老师', manager: '负责人', member: '普通成员' };
const PAGE_SIZE = typeof window !== 'undefined' && window.innerHeight
  ? window.innerHeight < 720 ? 4 : window.innerHeight < 860 ? 5 : window.innerHeight < 1000 ? 6 : 7
  : 6;
// 动态导航：API 模式下由后端 workspace.nav 下发（已按当前用户权限过滤）；mock 用默认兜底
// 每个页面模块的渲染函数通过 registerRenderer(id, fn) 注册，前端不硬编码菜单。
let NAV = [];
const DEFAULT_NAV = [
  { id: 'dashboard', label: '工作台', icon: 'grid', permission: 'page:workbench', param: '' },
  { id: 'members', label: '成员管理', icon: 'users', permission: 'page:members', param: '' },
  { id: 'leaves', label: '请假管理', icon: 'calendar', permission: 'page:leaves', param: '' },
  { id: 'assets', label: '模块管理', icon: 'chip', permission: 'page:assets', param: '' },
  { id: 'loans', label: '借用与归还', icon: 'swap', permission: 'page:loans', param: '' },
  { id: 'competitions', label: '比赛管理', icon: 'trophy', permission: 'page:competitions', param: '' },
  { id: 'tasks', label: '任务看板', icon: 'task', permission: 'page:tasks', param: '' },
  { id: 'levels', label: '技能关卡', icon: 'trophy', permission: 'page:levels', param: '' },
  { id: 'checkins', label: '实验室打卡', icon: 'pin', permission: 'page:checkins', param: '' },
  { id: 'seats', label: '实验室座位', icon: 'pin', permission: 'page:seats', param: '' },
  { id: 'leaderboard', label: '积分排行', icon: 'trophy', permission: 'page:leaderboard', param: '' },
  { id: 'agent', label: '智能体助手', icon: 'chat', permission: 'page:agent', param: '' },
  { id: 'logs', label: '操作记录', icon: 'history', permission: 'page:logs', param: '' },
  { id: 'profile', label: '个人中心', icon: 'user', permission: 'page:profile', param: '' },
  { id: 'notifications', label: '通知中心', icon: 'bell', permission: 'page:notifications', param: '' },
  { id: 'permissions', label: '权限矩阵', icon: 'shield', permission: 'page:permissions', param: '' },
  { id: 'announcements', label: '公告管理', icon: 'bell', permission: 'page:announcements', param: '' },
  { id: 'news', label: '实时动态', icon: 'wifi', permission: 'page:news', param: '' },
  { id: 'email', label: '邮件通知', icon: 'mail', permission: 'page:email', param: '' },
  { id: 'groups', label: '小组管理', icon: 'users', permission: 'page:groups', param: '' },
  { id: 'login-logs', label: '登录日志', icon: 'history', permission: 'page:loginlogs', param: '' },
  { id: 'homepage', label: '主页管理', icon: 'image', permission: 'page:homepage', param: '' },
  { id: 'member', label: '成员详情', icon: '', permission: 'page:member.detail', param: 'm' },
  { id: 'task', label: '任务详情', icon: '', permission: 'page:tasks', param: 'TASK' },
];
const PAGE_RENDERERS = {};
function registerRenderer(id, renderer) {
  PAGE_RENDERERS[id] = renderer;
}
const CATEGORIES = ['开发板', '单板计算机', '传感器', '通信模块', '执行器', '调试工具', '其他'];

const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const date = (days = 0, hour = 10) => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  d.setHours(hour, 0, 0, 0);
  return d.toISOString();
};
const fmt = (v, time = false) =>
  v
    ? new Date(v).toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        ...(time ? { hour: '2-digit', minute: '2-digit', hour12: false } : {}),
      })
    : '—';
const inputDate = (v) => {
  const d = new Date(v);
  return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};
function uid(prefix) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}
// 服务器时间校准：workspace 的 server_time 与本地时钟差（毫秒）；mock/未下发时为 0（回退本地时间）
let serverOffset = 0;
function serverNow() {
  return new Date(Date.now() + serverOffset);
}
function requirePermission(test, message = '当前身份没有此操作权限') {
  if (!test) throw new Error(message);
}
function ensureState(record, states) {
  requirePermission(states.includes(record.status), '记录状态已改变，请刷新后重试');
}

function percentage(value, total) {
  return total > 0 ? (value / total) * 100 : 0;
}
function countStatuses(items, status) {
  const counts = Object.create(null);
  for (const item of items) {
    const key = status(item);
    counts[key] = (counts[key] || 0) + 1;
  }
  return counts;
}
function cleanFields(input, keys = Object.keys(input)) {
  return Object.fromEntries(keys.map((key) => [key, String(input[key] ?? '').trim()]));
}
function isHttpURL(value) {
  return /^https?:\/\//i.test(value);
}

let db,
  sessionId = null,
  view = 'dashboard',
  routeParam = '',
  search = '',
  filter = '',
  groupFilter = '',
  page = 1;
const API = {
  async request(path, options = {}) {
    const controller = new AbortController(),
      timer = setTimeout(() => controller.abort(), CONFIG.timeout);
    try {
      const isForm = options.body instanceof FormData;
      const r = await fetch(CONFIG.API_BASE_URL + path, {
        ...options,
        credentials: 'include',
        headers: isForm ? (options.headers || {}) : { 'Content-Type': 'application/json', ...options.headers },
        signal: controller.signal,
      });
      const data = await r.json().catch(() => null);
      if (!r.ok) {
        const err = new Error(data?.message || `请求失败（${r.status}）`);
        err.status = r.status;
        throw err;
      }
      if (data === null) throw new Error('接口未返回有效 JSON 数据');
      return data.data ?? data;
    } catch (e) {
      if (e.name === 'AbortError') throw new Error('请求超时，请检查服务器连接');
      if (e.status === 401 && !path.startsWith('/auth/login')) {
        // 会话过期/失效：清除本地会话回登录页（登录失败 401 是密码错误，不跳转）
        sessionId = null;
        db = null;
        if (typeof render === 'function') render();
      }
      throw e;
    } finally {
      clearTimeout(timer);
    }
  },
  async load() {
    if (CONFIG.mode === 'api') {
      let current;
      try {
        current = await this.request('/auth/me');
      } catch (e) {
        if (e.status === 401) {
          sessionId = null;
          db = null;
          return;
        }
        throw e;
      }
      applySnapshot(await this.request('/workspace'));
      sessionId = current.id;
      return;
    }
    const raw = localStorage.getItem(DB_KEY),
      snapshot = raw ? JSON.parse(raw) : seed();
    validateSnapshot(snapshot);
    const migrated = !Array.isArray(snapshot.competitions);
    if (migrated) snapshot.competitions = seedCompetitions();
    if (!raw || migrated) localStorage.setItem(DB_KEY, JSON.stringify(snapshot));
    applySnapshot(snapshot);
    sessionId = sessionStorage.getItem(SESSION_KEY);
  },
  async login(username, password) {
    if (CONFIG.mode === 'api') {
      const result = await this.request('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) });
      sessionId = result.id;
      await this.load();
      return;
    }
    const m = db.members.find((x) => x.username === username && x.active);
    const credential = m && db.credentials?.[m.id];
    const valid = !!m && (credential ? await verifyCredential(password, credential) : password === 'Lab@123456');
    if (!valid) throw new Error('账号或密码不正确，或账号已停用');
    sessionStorage.setItem(SESSION_KEY, m.id);
    sessionId = m.id;
  },
  async mutate(path, payload, localAction) {
    if (CONFIG.mode === 'api') {
      await this.request(path, { method: 'POST', body: JSON.stringify(payload) });
      await this.load();
      return;
    }
    const backup = JSON.stringify(db);
    try {
      localAction();
      localStorage.setItem(DB_KEY, JSON.stringify(db));
    } catch (e) {
      applySnapshot(JSON.parse(backup), true);
      throw e;
    }
  },
  async logout() {
    if (CONFIG.mode === 'api') await this.request('/auth/logout', { method: 'POST' });
    sessionStorage.removeItem(SESSION_KEY);
    sessionId = null;
  },
};
function me() {
  return db?.members.find((m) => m.id === sessionId && m.active);
}
// mock 演示数据用的角色→权限映射（API 模式以后端 workspace.permissions 为准，不进此分支）
const MOCK_MEMBER_PERMS = [
  'page:workbench', 'page:profile', 'page:loans', 'page:leaves', 'page:tasks', 'page:checkins',
  'page:competitions', 'page:agent', 'page:logs', 'page:member.detail', 'page:leaderboard',
  'action:profile.edit', 'action:profile.status', 'action:notifications',
  'action:loan.create', 'action:loan.cancel', 'action:loan.request_return',
  'action:leave.create', 'action:leave.cancel',
  'action:task.create', 'action:task.update', 'action:task.delete', 'action:task.attachment',
  'action:checkin.create', 'action:checkin.refresh',
  'action:competition.view', 'action:agent.chat', 'action:agent.history',
  'action:token.manage', 'page:news',
  'page:notifications',
];
const MOCK_STAFF_ADDS = [
  'page:members', 'page:assets',
  'action:member.create', 'action:member.update', 'action:member.active',
  'action:asset.create', 'action:asset.update', 'action:asset.repair',
  'action:asset.repair_complete', 'action:asset.retire',
  'action:loan.review', 'action:loan.issue', 'action:loan.receive',
  'action:leave.review',
  'action:competition.create', 'action:competition.update', 'action:competition.archive',
  'action:task.score', 'action:points.rules', 'action:points.manual',
  'page:email', 'action:email.manage',
  'action:agent.operate',
  'action:token.manage', 'page:news', 'action:news.manage',
  // 兼容旧测试直接断言的管理权限字面量
  'manageCompetitions', 'manageAssets', 'manageMembers', 'approve',
];
function mockPermissions(role) {
  const base = [...MOCK_MEMBER_PERMS];
  if (role === 'teacher' || role === 'manager') base.push(...MOCK_STAFF_ADDS);
  if (role === 'teacher') base.push('assignRoles');
  return base;
}
// 路由 id 与权限点命名不一致的别名：导航守卫/菜单渲染共用 can()，统一在此归一
const PAGE_KEY_ALIAS = { 'page:dashboard': 'page:workbench', 'page:login-logs': 'page:loginlogs' };
function can(permission) {
  const key = PAGE_KEY_ALIAS[permission] || permission;
  if (Array.isArray(db?.permissions)) return db.permissions.includes(key);
  // mock：按当前登录成员的 role 推导（演示与既有测试）
  const role = me()?.role;
  return !!role && mockPermissions(role).includes(key);
}
function canApprove() {
  return can('action:loan.review') || can('action:leave.review') || can('approve');
}
function roleLabel(m) {
  if (!m) return '—';
  if (Array.isArray(m.roles) && m.roles.includes('superadmin')) return '系统管理员';
  return ROLE[m.role] || '普通成员';
}
function member(id) {
  return db.members.find((x) => x.id === id);
}
function asset(id) {
  return db.assets.find((x) => x.id === id);
}
function activeLoan(id) {
  return db.loans.find((l) => isActiveLoan(l) && l.assetIds.includes(id));
}
function assetStatus(a) {
  return activeLoan(a.id) ? '使用中' : a.status;
}
function memberStatus(m) {
  return db.leaves.some(
    (l) => l.memberId === m.id && l.status === '已通过' && Date.parse(l.start) <= Date.now() && Date.parse(l.end) >= Date.now(),
  )
    ? '请假'
    : m.baseStatus;
}
function overdue(l) {
  return isActiveLoan(l) && Date.parse(l.due) < Date.now();
}
function audit(text, memberId = me().id) {
  // API 模式下操作日志由后端生成（OperationLog），本地不再双写，避免与后端审计歧义
  if (CONFIG.mode !== 'mock') return;
  db.logs.push({ id: uid('LOG'), actor: me().name, text, memberId, at: new Date().toISOString() });
}
function pendingCount() {
  return db.loans.filter((l) => needsLoanReview(l)).length + db.leaves.filter((l) => l.status === '待审批' && canReview(l)).length;
}
function canReview(r) {
  const user = me(), owner = member(r?.memberId);
  if (!user || !(can('action:loan.review') || can('action:leave.review'))) return false;
  // 对象级约束：不能审自己；负责人只能审普通成员（后端 _can_review 同样强制）
  return user.id !== r.memberId && (user.role === 'teacher' || owner?.role === 'member');
}
const STAFF_PAGE_KEYS = ['page:members', 'page:assets', 'page:permissions', 'page:loginlogs', 'page:announcements', 'page:news', 'page:email', 'page:homepage', 'page:groups'];
function isStaffView() {
  return STAFF_PAGE_KEYS.some((k) => can(k));
}
function visibleLogs() {
  return db.logs
    .filter((l) => isStaffView() || l.memberId === me().id || !l.private)
    .sort((a, b) => Date.parse(b.at) - Date.parse(a.at));
}
function todoItems() {
  const tasks = [];
  for (const l of db.loans) {
    if (needsLoanReview(l))
      tasks.push({
        title: `${member(l.memberId)?.name} · ${l.status === '待审批' ? '模块借用申请' : l.status}`,
        description: l.assetIds.map((id) => asset(id)?.name).join('、'),
        icon: 'swap',
        view: 'loans',
      });
    if (overdue(l) && (canApprove() || l.memberId === me().id))
      tasks.push({
        title: '模块借用已逾期',
        description: `${member(l.memberId)?.name} · ${fmt(l.due)} 应归还`,
        icon: 'clock',
        view: 'loans',
        orange: true,
      });
  }
  for (const l of db.leaves)
    if (l.status === '待审批' && canReview(l))
      tasks.push({
        title: `${member(l.memberId)?.name} · 请假申请`,
        description: `${fmt(l.start)} — ${fmt(l.end)}`,
        icon: 'calendar',
        view: 'leaves',
        orange: true,
      });
  return tasks;
}
function editableMember(m) {
  // 权限点 + 对象级约束（负责人只能管理普通成员，与后端 members_update 一致）
  return !!m && can('action:member.update') && (me().role === 'teacher' || m.role === 'member');
}
function getLoan(id) {
  const l = db.loans.find((x) => x.id === id);
  requirePermission(l, '借用记录不存在');
  requirePermission(l.memberId === me().id || can('action:loan.review') || can('action:loan.issue') || can('action:loan.receive'));
  return l;
}
function getLeave(id) {
  const l = db.leaves.find((x) => x.id === id);
  requirePermission(l, '请假记录不存在');
  requirePermission(l.memberId === me().id || canReview(l));
  return l;
}

// 所有加载、同步和失败回滚使用同一入口，保持编辑回调引用的记录对象有效。
const RECORD_COLLECTIONS = ['members', 'assets', 'loans', 'leaves', 'maintenance', 'logs', 'competitions', 'tasks', 'checkins'];
function validateSnapshot(snapshot) {
  requirePermission(
    typeof snapshot?.version === 'number' && RECORD_COLLECTIONS.filter((key) => key !== 'competitions').every((key) => Array.isArray(snapshot[key])),
    '演示数据格式无效，请刷新或恢复演示数据',
  );
}
function applySnapshot(snapshot, exact = false) {
  validateSnapshot(snapshot);
  requirePermission(Array.isArray(snapshot.competitions), '比赛数据格式无效');
  const next = { ...snapshot };
  for (const key of RECORD_COLLECTIONS) {
    const existing = new Map((db?.[key] || []).map((record) => [record.id, record]));
    next[key] = snapshot[key].map((record) => {
      const current = existing.get(record.id);
      if (!current) return record;
      // 默认只合并/覆盖，不删除后端漏发的字段（保留旧值，避免 UI 依赖处显示异常）；
      // exact（失败回滚）必须精确还原，否则失败操作留下的脏字段会一直留在内存里
      if (exact) for (const field of Object.keys(current)) if (!Object.hasOwn(record, field)) delete current[field];
      return Object.assign(current, record);
    });
  }
  db = next;
  serverOffset = snapshot.server_time ? new Date(snapshot.server_time).getTime() - Date.now() : 0;
  // 动态导航：后端下发（已按权限过滤）优先，否则用默认兜底（mock 演示）
  NAV = Array.isArray(snapshot.nav) && snapshot.nav.length ? snapshot.nav : DEFAULT_NAV;
}
function isActiveLoan(loan) {
  return ['使用中', '待确认归还'].includes(loan.status);
}
function needsLoanReview(loan) {
  return canReview(loan) && ['待审批', '待发放', '待确认归还'].includes(loan.status);
}
function reviewRequest(record, data, approvedStatus, expires, message) {
  requirePermission(canReview(record));
  ensureState(record, ['待审批']);
  requirePermission(['approve', 'reject'].includes(data.decision));
  requirePermission(data.decision !== 'approve' || Date.parse(expires) > Date.now(), message);
  Object.assign(record, {
    status: data.decision === 'approve' ? approvedStatus : '已拒绝',
    reviewer: me().id,
    opinion: data.opinion,
    reviewed: new Date().toISOString(),
  });
}
