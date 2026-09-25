'use strict';
// 系统管理模块：公告、小组管理、登录日志、密码与数据导出。
// 页面按左侧菜单分类接入权限矩阵（page:/action: 权限点见 rbac_defs）。

// 令牌明文只在创建弹窗内存在（复制后置空），不暴露为全局属性，防止被同源脚本窃取。
let _lastToken = '', _lastAi = '';

/* ───────────────── 修改密码 ───────────────── */

function changePasswordModal(force = false) {
  modal(
    force ? '请修改初始密码' : '修改密码',
    `<div class="form-grid">${field('旧密码 *', 'oldPassword', '', 'password', 'autocomplete="current-password"')}${field('新密码 *', 'newPassword', '', 'password', 'autocomplete="new-password" placeholder="8-64 位，含字母和数字"')}${field('确认新密码 *', 'confirmPassword', '', 'password', 'autocomplete="new-password"')}</div>${force ? '<p class="privacy-note">管理员已重置你的密码，首次登录后必须修改。</p>' : ''}`,
    '确认修改',
    async (f) => {
      const oldP = f.get('oldPassword'), newP = f.get('newPassword'), cf = f.get('confirmPassword');
      if (CONFIG.mode === 'mock') {
        // mock 演示：本地校验与更新密码（db.credentials），不请求后端
        const m = me();
        const cred = db.credentials?.[m.id];
        const oldOk = cred ? await verifyCredential(oldP, cred) : oldP === 'Lab@123456';
        requirePermission(oldOk, '旧密码不正确');
        requirePermission(newP === cf, '两次输入的新密码不一致');
        validatePassword(newP, cf);
        db.credentials = { ...(db.credentials || {}), [m.id]: await makeCredential(newP) };
        localStorage.setItem(DB_KEY, JSON.stringify(db));
        toast('密码已修改');
        document.querySelector('#modal')?.close();
        render();
        return;
      }
      await API.request('/members/me/password', {
        method: 'POST',
        body: JSON.stringify({
          oldPassword: oldP,
          newPassword: newP,
          confirmPassword: cf,
        }),
      });
      toast('密码已修改');
      document.querySelector('#modal')?.close();
      render();
    },
  );
}

/* ───────────────── 首次登录完善资料 ───────────────── */

function completeProfileModal() {
  const d = document.querySelector('#modal');
  if (d.open) d.close();
  const u = me() || {};
  const blockCancel = (e) => e.preventDefault();
  modalSubmit = async (f) => {
    const data = cleanMemberData({ name: f.get('name'), number: f.get('number'), contact: f.get('contact'), email: f.get('email') }, true);
    if (!data.number || !data.contact || !data.email) throw new Error('请完善个人资料：学号、联系方式、邮箱不能为空');
    validateMemberData(data, me()?.id, true);
    await API.request('/members/me/update', { method: 'POST', body: JSON.stringify(data) });
    await API.load();
    d.close();
    render();
    toast('资料已完善，欢迎使用平台');
    if (me()?.mustChangePassword && typeof changePasswordModal === 'function') changePasswordModal(true);
  };
  d.innerHTML = `<div class="modal-header"><h2>完善个人资料</h2></div><form id="modal-form"><div class="modal-body"><p class="privacy-note">新账号首次登录需先完善个人资料，保存后才能正常使用平台。所属小组由管理员分配。</p><div class="form-grid">${field('姓名 *', 'name', u.name || '', 30)}${field('学号 / 工号 *', 'number', u.number || '', 30, 'placeholder="如 2023xxxxxx"')}${fields(u, { contact: ['联系方式 *', 80], email: ['邮箱 *', 'email', 'placeholder="name@example.com" required'] })}</div><div class="form-error" id="modal-error" role="alert"></div></div><div class="modal-footer"><button type="submit" class="btn primary">保存并进入平台</button></div></form>`;
  d.showModal();
  d.addEventListener('cancel', blockCancel);
  d.addEventListener('close', () => d.removeEventListener('cancel', blockCancel), { once: true });
}

/* ───────────────── 公告 ───────────────── */

function announcementsPage() {
  const list = db.announcements || [];
  const canCreate = can('action:announcement.create');
  const canUpdate = can('action:announcement.update');
  const unread = db.unread_announcements || 0;
  const p = paginate(list, 4);
  return `<div class="page-fit">${heading('公告管理', '发布与维护面向整个实验室的公告。', canCreate ? btn(`${icon('plus')} 发布公告`, 'announcement-new', 'primary') + btn(`${icon('refresh')} 刷新`, 'announcement-refresh') : '', 'ANNOUNCEMENTS / 通知中心')}${unread ? `<div class="notice">${icon('bell')} 你有 ${unread} 条未读公告</div>` : ''}<section class="panel"><div class="ann-list">${
    p.rows.length
      ? p.rows
          .map(
            (a) => `<article class="panel ann-card ${a.read ? '' : 'unread'}"><div class="ann-head"><div class="row" style="gap:9px"><span class="ann-pin">${a.pinned ? `${icon('pin')} 置顶` : ''}</span><h3>${esc(a.title)}</h3></div><div class="muted small">${esc(a.author)} · ${fmt(a.created, true)}</div></div><div class="ann-body">${esc(a.content).replace(/\n/g, '<br>')}</div>${canUpdate ? `<div class="ann-foot">${a.active ? btn('下架', 'announcement-toggle', 'small', `data-id="${esc(a.id)}"`) : btn('恢复', 'announcement-toggle', 'small', `data-id="${esc(a.id)}"`)}</div>` : ''}</article>`,
          )
          .join('')
      : empty('暂无公告', '点击右上角发布第一条公告吧。')
  }</div>${p.footer}</section></div>`;
}

function announcementForm(id = null) {
  const a = id ? (db.announcements || []).find((x) => x.id === id) : null;
  const groups = db.groups || [];
  const members = db.members.filter((m) => m.active);
  modal(
    a ? '编辑公告' : '发布公告',
    `<div class="form-grid">${field('标题 *', 'title', a?.title || '', 80)}</div><div class="field" style="margin-top:14px"><label>公告内容 *</label><textarea name="content" maxlength="20000" style="min-height:160px">${esc(a?.content || '')}</textarea></div><div class="form-grid" style="margin-top:14px">${selectField('接收范围', 'scope', [['all', '全体成员'], ['group', '指定小组'], ['members', '指定成员']], a?.scope || 'all')}<div id="scope-extra" class="field"></div></div><label class="row" style="margin-top:12px;gap:8px"><input type="checkbox" name="pinned" ${a?.pinned ? 'checked' : ''}> 置顶显示</label>`,
    '保存',
    async (f) => {
      const d = { title: f.get('title').trim(), content: f.get('content').trim(), pinned: !!f.get('pinned'), scope: f.get('scope') };
      if (d.scope === 'group') d.groupId = f.get('groupId');
      if (d.scope === 'members') d.memberIds = members.filter((m) => f.get(`mem:${m.id}`)).map((m) => m.id);
      const path = a ? `/announcements/${a.id}/update` : '/announcements/create';
      await API.request(path, { method: 'POST', body: JSON.stringify(d) });
      await API.load();
      document.querySelector('#modal')?.close();
      render();
      toast(a ? '公告已更新' : '公告已发布');
    },
  );
  // 范围联动渲染
  const extra = document.querySelector('#scope-extra');
  const drawScope = () => {
    const scope = document.querySelector('[name="scope"]')?.value || 'all';
    extra.innerHTML =
      scope === 'group'
        ? `<label>选择小组</label><select name="groupId">${options(groups.map((g) => [g.id, `${g.name}（${g.memberCount}人）`]), a?.groupId || '')}</select>`
        : scope === 'members'
          ? `<label>选择成员</label><div class="asset-picker">${members.map((m) => `<label class="asset-option"><span>${esc(m.name)} · ${roleLabel(m)}</span><span style="margin-left:auto"><input type="checkbox" name="mem:${m.id}"> 选择</span></label>`).join('')}</div>`
          : '';
  };
  document.querySelector('[name="scope"]')?.addEventListener('change', drawScope);
  drawScope();
}

async function announcementToggle(id) {
  const a = (db.announcements || []).find((x) => x.id === id);
  if (!a) return;
  await API.request(`/announcements/${id}/update`, { method: 'POST', body: JSON.stringify({ active: !a.active }) });
  await API.load();
  render();
  toast(a.active ? '公告已下架' : '公告已恢复');
}

function markAnnouncementRead(id) {
  API.request(`/announcements/${id}/read`, { method: 'POST', body: '{}' }).then(() => {
    const a = (db.announcements || []).find((x) => x.id === id);
    if (a) a.read = true;
    render();
  });
}

/* ───────────────── 小组管理 ───────────────── */

function groupsPage() {
  const groups = db.groups || [];
  const canManage = can('action:group.manage');
  const canAssign = can('action:group.members');
  const p = paginate(groups, 6);
  return `<div class="page-fit">${heading('小组管理', '按小组组织成员，队长可指定、人数可设上限。', canManage ? btn(`${icon('plus')} 新建小组`, 'group-new', 'primary') : '', 'GROUPS / 分组')}<section class="panel"><div class="group-grid">${
    p.rows.length
      ? p.rows
          .map(
            (g) => `<section class="panel group-card"><div class="row"><span class="group-avatar">${icon('users')}</span><div><h3>${esc(g.name)}</h3><small class="muted">队长：${esc(g.leaderName || '未指定')} · ${g.memberCount}/${g.capacity} 人</small></div></div><div class="group-members">${g.members.map((mid) => { const m = member(mid); return m ? `<span class="member-chip">${esc(m.name)}</span>` : ''; }).join('') || '<span class="muted small">暂无成员</span>'}</div>${canManage || canAssign ? `<div class="group-actions">${canAssign ? btn('调配成员', 'group-members', 'small', `data-id="${esc(g.id)}"`) : ''}${canManage ? btn('编辑', 'group-edit', 'small', `data-id="${esc(g.id)}"`) : ''}${canManage ? btn('删除', 'group-delete', 'small danger', `data-id="${esc(g.id)}"`) : ''}</div>` : ''}</section>`,
          )
          .join('')
      : empty('暂无小组', '创建小组，把成员组织起来。')
  }</div>${p.footer}</section></div>`;
}

function groupForm(id = null) {
  const g = id ? (db.groups || []).find((x) => x.id === id) : null;
  const leadable = db.members.filter((m) => m.active);
  modal(
    g ? '编辑小组' : '新建小组',
    `<div class="form-grid">${field('小组名称 *', 'name', g?.name || '', 40)}${field('人数上限', 'capacity', g?.capacity || 20, 'number', 'min="1" max="200"')}${selectField('队长', 'leaderId', leadable.map((m) => [m.id, m.name]), g?.leaderId || '')}<div class="field full"><label>备注</label><input name="note" value="${esc(g?.note || '')}" maxlength="120"></div></div>`,
    '保存',
    async (f) => {
      const d = { name: f.get('name').trim(), capacity: parseInt(f.get('capacity') || '20', 10), leaderId: f.get('leaderId'), note: f.get('note') };
      const path = g ? `/groups/${g.id}/update` : '/groups/create';
      await API.request(path, { method: 'POST', body: JSON.stringify(d) });
      await API.load();
      document.querySelector('#modal')?.close();
      render();
      toast(g ? '小组已更新' : '小组已创建');
    },
  );
}

function groupMembersForm(id) {
  const g = (db.groups || []).find((x) => x.id === id);
  if (!g) return;
  const current = new Set(g.members || []);
  const others = db.members.filter((m) => m.active);
  modal(
    `调配「${g.name}」成员`,
    `<p class="privacy-note">勾选成员加入该小组（同一个人只能属于一个小组，最多 ${g.capacity} 人）。</p><div class="asset-picker">${others.map((m) => `<label class="asset-option"><span>${esc(m.name)} · ${roleLabel(m)}</span><span style="margin-left:auto"><input type="checkbox" name="mem:${m.id}" ${current.has(m.id) ? 'checked' : ''}></span></label>`).join('')}</div>`,
    '保存',
    async (f) => {
      const ids = others.filter((m) => f.get(`mem:${m.id}`)).map((m) => m.id);
      await API.request(`/groups/${id}/members`, { method: 'POST', body: JSON.stringify({ memberIds: ids }) });
      await API.load();
      document.querySelector('#modal')?.close();
      render();
      toast('成员已调配');
    },
  );
}

async function groupDelete(id) {
  const g = (db.groups || []).find((x) => x.id === id);
  if (!g) return;
  modal(
    '删除小组',
    `<p>确认删除小组「${esc(g.name)}」吗？成员将被移出该小组，但不会删除成员账号。</p>`,
    '删除',
    async () => {
      await API.request(`/groups/${id}/delete`, { method: 'POST', body: '{}' });
      await API.load();
      document.querySelector('#modal')?.close();
      render();
      toast('小组已删除');
    },
  );
}

/* ───────────────── 登录日志 ───────────────── */

let _loginLogsCache = null;
async function ensureLoginLogs() {
  if (_loginLogsCache) return;
  try {
    _loginLogsCache = await API.request('/login-logs');
  } catch (e) {
    // 加载失败给出空态而非永久"加载中…"
    _loginLogsCache = [];
    toast(e.message, true);
  }
}
function loginLogsPage() {
  if (!_loginLogsCache) {
    ensureLoginLogs().then(() => render());
    return `${heading('登录日志', '跟踪成员登录行为，辅助安全审计。', btn(`${icon('refresh')} 刷新`, 'loginlogs-refresh'), 'SECURITY / 登录审计')}<section class="panel"><div class="empty">${icon('shield')}加载中…</div></section>`;
  }
  const rows = _loginLogsCache || [];
  const filtered = rows
    .filter((l) => !filter || (filter === '成功') === l.success)
    .filter((l) => !search || (l.name + l.ip).includes(search));
  const p = paginate(filtered, 8);
  return `<div class="page-fit">${heading('登录日志', '跟踪成员登录行为，辅助安全审计。', btn(`${icon('refresh')} 刷新`, 'loginlogs-refresh'), 'SECURITY / 登录审计')}<section class="panel"><div class="toolbar"><div class="search-field">${icon('search')}<input id="search" placeholder="搜索成员、IP…" value="${esc(search)}"></div><select id="filter">${options(['成功', '失败'], filter, '全部结果')}</select><button class="text-btn" data-action="clear-filter">重置</button></div><div class="table-wrap"><table><thead><tr><th>成员</th><th>结果</th><th>IP</th><th>时间</th><th>设备</th></tr></thead><tbody>${p.rows
    .map((l) => `<tr><td><strong>${esc(l.name)}</strong></td><td>${badge(l.success ? '成功' : '失败')}</td><td class="mono">${esc(l.ip || '—')}</td><td>${new Date(l.at).toLocaleString('zh-CN')}</td><td class="muted small">${esc(l.ua.slice(0, 40))}</td></tr>`)
    .join('') || `<tr><td colspan="5">${empty('暂无记录')}</td></tr>`}</tbody></table></div>${p.footer}</section></div>`;
}
function loginLogsRefresh() {
  _loginLogsCache = null;
  render();
}

/* ───────────────── 数据导出 ───────────────── */

function exportCsv(kind, label) {
  requirePermission(can('action:export.csv'));
  window.open(`/api/export/${kind}`, '_blank');
}

function memberResetPassword(id) {
  const m = member(id);
  requirePermission(m, '成员不存在');
  modal(
    '重置密码',
    `<p>确认重置「${esc(m.name)}」的登录密码？重置后系统生成随机密码（仅本次展示），该成员下次登录将被要求修改密码。</p>`,
    '确认重置',
    async () => {
      const resp = await API.request(`/members/${id}/reset-password`, { method: 'POST', body: '{}' });
      const pw = resp.password;
      modal(
        '密码已重置',
        `<div class="notice">${icon('check')} 以下为<strong>一次性</strong>临时密码，请立即告知该成员：</div><div class="temp-password mono">${esc(pw)}</div><p class="privacy-note">该成员下次登录后将强制修改为新密码。</p>`,
        '我已保存',
        null,
      );
    },
  );
}

window.sysmo = { changePasswordModal, markAnnouncementRead, exportCsv, memberResetPassword };
window.SYS_ACTIONS = {
  'change-password': () => changePasswordModal(false),
  'member-reset-password': memberResetPassword,
  'announcement-new': () => announcementForm(),
  'announcement-edit': announcementForm,
  'announcement-toggle': announcementToggle,
  'announcement-read': markAnnouncementRead,
  'announcement-refresh': async () => { await API.load(); render(); },
  'group-new': () => groupForm(),
  'group-edit': groupForm,
  'group-delete': groupDelete,
  'group-members': groupMembersForm,
  'loginlogs-refresh': loginLogsRefresh,
  'token-new': tokenNew,
  'token-revoke': tokenRevoke,
  'token-copy': tokenCopy,
  'token-copy-ai': tokenCopyAi,
  ...Object.fromEntries(['members', 'loans', 'assets', 'maintenance', 'points', 'loginlogs', 'tasks', 'checkins', 'logs'].map((k) => [`export-${k}`, () => exportCsv(k, k)])),
};

/* ───────────────── API 令牌（个人中心） ───────────────── */

let _tokenCache = null;
async function ensureTokens() {
  if (_tokenCache) return;
  try {
    _tokenCache = CONFIG.mode === 'mock' ? [] : await API.request('/tokens');
  } catch (e) {
    _tokenCache = [];
  }
  render();
}

function tokensPanel() {
  if (!can('action:token.manage')) return '';
  if (_tokenCache === null) ensureTokens();
  const rows = (_tokenCache || [])
    .map(
      (t) => `<tr><td><strong>${esc(t.name)}</strong></td><td class="mono small muted">${(t.scopes || []).join('、')}</td><td class="muted small">${t.active ? (t.expiresAt ? '至 ' + fmt(t.expiresAt) : '长期') : '<b style="color:#d28370">已吊销</b>'}</td><td>${badge(t.active ? '启用' : '已吊销')}</td><td>${t.active ? recordButton('吊销', 'token-revoke', t.id) : ''}</td></tr>`,
    )
    .join('');
  return `<section class="panel"><div class="panel-head"><div><h2>API 令牌</h2><p>给外部工具/脚本提供只读数据接口（Bearer Token）</p></div>${btn(`${icon('plus')} 创建令牌`, 'token-new', 'primary')}</div><div class="table-wrap"><table><thead><tr><th>名称</th><th>授权范围</th><th>有效期</th><th>状态</th><th>操作</th></tr></thead><tbody>${rows || '<tr><td colspan="5"><div class="empty small">' + icon('box') + '暂无令牌</div></td></tr>'}</tbody></table></div><p class="privacy-note">调用方式：<code class="agent-inline">Authorization: Bearer &lt;令牌&gt;</code>，可用于 <span class="mono">/openapi/assets</span>、<span class="mono">/openapi/loans</span> 等只读接口。令牌明文仅在创建时展示一次。</p></section>`;
}

function tokenNew() {
  modal(
    '创建 API 令牌',
    `<div class="form-grid">${field('令牌名称 *', 'name', '', 40, 'placeholder="例如：Trae 外部调用"')}<div class="field full"><label>授权范围（只读，可多选）</label><div class="asset-picker">${['read:assets', 'read:loans', 'read:tasks'].map((s) => `<label class="asset-option"><input type="checkbox" name="scope" value="${s}" checked><span class="mono">${s}</span></label>`).join('')}</div></div></div><p class="privacy-note">默认 90 天过期，可在列表吊销。</p>`,
    '创建',
    async (f) => {
      const scopes = f.getAll('scope');
      requirePermission(scopes.length, '请至少选择一个授权范围');
      let resp;
      if (CONFIG.mode === 'mock') {
        // mock 演示：本地生成令牌与 AI 指令，不请求后端
        resp = {
          token: 'lab_' + 'demo' + Math.random().toString(36).slice(2, 14),
          expiresAt: new Date(Date.now() + 90 * 86400000).toISOString(),
          aiInstruction: ['你是「具身智能实验室」管理平台的只读数据助手。', '这是一条演示用的 API 令牌（mock 模式，不能访问真实数据）。', '认证方式：请求头携带  Authorization: Bearer <令牌>', '', '可用接口（按授权范围）：', ...scopes.map((s) => `- GET https://wuyuan.me/api/openapi/${s.replace('read:', '')}  →  对应只读数据`)].join('\n'),
        };
        const list = _tokenCache || [];
        list.unshift({ id: 'T' + Date.now(), name: f.get('name').trim(), scopes, active: true, expiresAt: resp.expiresAt });
        _tokenCache = list;
      } else {
        resp = await API.request('/tokens/create', { method: 'POST', body: JSON.stringify({ name: f.get('name').trim(), scopes }) });
      }
      _tokenCache = null;
      document.querySelector('#modal').innerHTML =
        `<div class="modal-header"><h2>令牌已创建</h2><button type="button" class="icon-btn" data-action="modal-close" aria-label="关闭">${icon('close')}</button></div><div class="modal-body"><div class="notice">令牌明文仅展示这一次，关闭后无法再次查看。AI 指令已内置令牌，直接粘贴给 AI 即可查询实验室数据。</div><p class="small muted" style="margin-top:14px">给 AI 的指令（已内置令牌）</p><div class="token-reveal mono" style="white-space:pre-wrap;line-height:1.7;max-height:230px;overflow:auto">${esc(resp.aiInstruction || '')}</div><p class="small muted" style="margin-top:14px">令牌明文</p><div class="token-reveal mono">${esc(resp.token)}</div><div class="controls-wrap">${btn('复制 AI 指令', 'token-copy-ai')}${btn('仅复制令牌', 'token-copy')}${btn('关闭', 'modal-close', 'primary')}</div></div>`;
      _lastToken = resp.token;
      _lastAi = resp.aiInstruction || '';
      await API.load();
      render();
    },
  );
}

function tokenRevoke(id) {
  const t = (_tokenCache || []).find((x) => x.id === id);
  confirmation(
    '吊销令牌',
    `确认吊销「${esc(t?.name || id)}」？吊销后使用该令牌的调用将立即失效。`,
    `/tokens/${id}/revoke`,
    {},
    () => {
      _tokenCache = null;
    },
    '确认吊销',
  );
}

function tokenCopy() {
  const text = _lastToken || '';
  const done = (ok) => {
    if (ok) _lastToken = ''; // 复制成功即销毁内存中的明文
    toast(ok ? '已复制到剪贴板' : '没有可复制的令牌');
  };
  if (navigator.clipboard?.writeText) navigator.clipboard.writeText(text).then(() => done(true)).catch(() => done(false));
  else {
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
    done(true);
  }
}

function tokenCopyAi() {
  const text = _lastAi || '';
  const done = (ok) => {
    if (ok) _lastAi = '';
    toast(ok ? '已复制 AI 指令' : '没有可复制的指令');
  };
  if (navigator.clipboard?.writeText) navigator.clipboard.writeText(text).then(() => done(true)).catch(() => done(false));
  else {
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
    done(true);
  }
}