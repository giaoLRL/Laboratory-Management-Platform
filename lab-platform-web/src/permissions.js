'use strict';
// 权限矩阵页：按左侧菜单栏分类的折叠卡片，每卡片内 列=角色、行=权限点、单元格=复选框。
// 仅系统管理员可维护（canEditRoles / canEditMatrix / canOverride 由后端 meta 返回）。

let _permMeta = null;
let _permLoading = false;
let _navAdmin = null; // 动态导航全量配置（仅 superadmin）

// 展开状态：按菜单分类 id 记录被"已展开"的分组；默认全折叠，持久化到 localStorage
const PERM_EXP_KEY = 'lab_perm_group_state';
let _permExpanded = null;
function permExpanded() {
  if (!_permExpanded) {
    _permExpanded = new Set();
    try {
      const stored = JSON.parse(localStorage.getItem(PERM_EXP_KEY) || '[]');
      if (Array.isArray(stored)) stored.forEach((id) => _permExpanded.add(id));
    } catch (e) {
      _permExpanded = new Set();
    }
  }
  return _permExpanded;
}
function persistExpanded() {
  localStorage.setItem(PERM_EXP_KEY, JSON.stringify([...permExpanded()]));
}

async function ensurePermMeta() {
  if (_permMeta || _permLoading) return;
  _permLoading = true;
  try {
    _permMeta = await API.request('/permissions/meta');
    if (_permMeta.isSuperadmin && !_navAdmin) {
      _navAdmin = await API.request('/nav').catch(() => []);
    }
  } finally {
    _permLoading = false;
  }
}

// 动态导航配置区：调整菜单启用/顺序/标题（仅 superadmin），保存后刷新生效
function navAdminSection() {
  if (!_navAdmin) return '';
  const rows = _navAdmin
    .map(
      (n, i) => `<div class="nav-row" data-idx="${i}"><span class="mono nav-id">${esc(n.id)}</span><input class="nav-label" value="${esc(n.label)}" maxlength="32" aria-label="标题"><input class="nav-perm" value="${esc(n.permission)}" maxlength="64" aria-label="权限点"><span class="nav-param mono">${esc(n.param || '—')}</span><label class="check-label"><input type="checkbox" class="nav-enable" ${n.enabled ? 'checked' : ''}> 启用</label><div class="row" style="gap:4px"><button class="text-btn" data-action="nav-up" data-id="${esc(n.id)}" ${i === 0 ? 'disabled' : ''}>上移</button><button class="text-btn" data-action="nav-down" data-id="${esc(n.id)}" ${i === _navAdmin.length - 1 ? 'disabled' : ''}>下移</button></div></div>`,
    )
    .join('');
  return `<section class="panel nav-admin-panel"><div class="panel-head"><div><h2>导航配置</h2><p>调整侧边栏菜单的启用、顺序与路由配置，保存后立即生效</p></div>${btn('保存导航配置', 'nav-save', 'primary')}</div><div class="nav-admin-head"><span>路由 id</span><span>菜单标题</span><span>权限点</span><span>子页前缀</span></div><div class="nav-admin">${rows}<p class="privacy-note">参数子页（member/task）不在侧边栏展示；权限点留空表示登录即可见。</p></div></section>`;
}

// 分组渲染完全由后端 /permissions/meta 的 groups（rbac_defs.PERMISSION_GROUPS）驱动，
// 前端只提供图标映射；新增权限点只改后端即可出现在矩阵。
const ICON_BY_GROUP = {
  框架: 'grid', 成员: 'users', 公告: 'bell', 动态: 'wifi', '资产/借用': 'chip', 请假: 'calendar',
  任务: 'task', 打卡: 'pin', 比赛: 'trophy', 积分: 'trophy', 智能体: 'chat', 日志: 'history',
  邮件: 'mail', 系统: 'shield',
};

function _labelOf(key) {
  for (const g of _permMeta.groups || []) {
    for (const p of g.points) if (p.key === key) return p.label;
  }
  return key;
}

function _roleCell(r, key, checked, canEditMatrix) {
  if (r.superadmin) return `<td class="perm-cell perm-super">${checked ? '✓' : ''}</td>`;
  return `<td class="perm-cell"><input type="checkbox" data-role="${esc(r.code)}" data-key="${esc(key)}" ${checked ? 'checked' : ''} ${canEditMatrix ? '' : 'disabled'}></td>`;
}

function permissionsPage() {
  if (!_permMeta) {
    ensurePermMeta().then(() => render());
    return `${heading('权限矩阵', '按左侧菜单栏分类配置菜单、页面与按键权限。', '', 'PERMISSIONS / 权限配置')}<section class="panel"><div class="empty">${icon('shield')}加载中…</div></section>`;
  }
  const canEditMatrix = !!_permMeta.canEditMatrix;
  const canEditRoles = !!_permMeta.canEditRoles;
  const roles = _permMeta.roles || [];
  const expanded = permExpanded();

  const headActions = (canEditMatrix ? btn('保存全部', 'perm-save-all', 'primary') : '') +
    btn(expanded.size ? `${icon('chevron')} 全部折叠` : `${icon('down')} 全部展开`, 'perm-expand-all', '') +
    (canEditRoles ? btn(`${icon('plus')} 新增角色`, 'perm-role-new', '') : '');

  // 单一表头：角色列；超管列显示"全量"，自定义角色列带 改名/删除
  const roleHead = `<th class="perm-col-name">权限点</th>${roles
    .map(
      (r) => `<th class="perm-col-role"><span class="perm-col-role-name">${esc(r.name)}</span>${
        r.superadmin ? '<span class="perm-super-tag">全量</span>'
          : canEditRoles && !r.builtin
            ? `<span class="perm-col-actions"><button class="icon-btn perm-col-icon" data-action="perm-role-rename" data-id="${esc(r.code)}" aria-label="重命名 ${esc(r.name)}">${icon('tool')}</button><button class="icon-btn perm-col-icon" data-action="perm-role-delete" data-id="${esc(r.code)}" aria-label="删除 ${esc(r.name)}">${icon('close')}</button></span>`
            : ''
      }</th>`,
    )
    .join('')}`;

  const groups = (_permMeta.groups || [])
    .map((g) => {
      const name = g.name;
      const keys = g.points.map((p) => p.key);
      const open = expanded.has(name);
      return `<tbody class="perm-g-body ${open ? '' : 'collapsed'}" data-group="${name}">
  <tr data-group-head="${name}"><td class="perm-g-head-cell" colspan="${roles.length + 1}">
    <div class="perm-g-head" data-action="perm-group-toggle" data-id="${name}" role="button" tabindex="0" aria-expanded="${open}">
      <span class="perm-g-icon">${icon(ICON_BY_GROUP[name] || 'shield')}</span>
      <span class="perm-g-name">${esc(name)}</span>
      <span class="perm-g-meta">${keys.length} 项权限</span>
      <span class="perm-g-chev">${icon('chevron')}</span>
    </div>
    ${canEditMatrix ? `<button class="perm-g-check" data-action="perm-group-check" data-id="${esc(name)}" type="button">全选本组</button>` : ''}
  </td></tr>
  ${keys
    .map((key) => `<tr class="perm-g-detail"><td class="perm-point"><span>${esc(_labelOf(key))}</span><small class="mono">${esc(key)}</small></td>${roles
      .map((r) => _roleCell(r, key, r.permissions.includes(key), canEditMatrix))
      .join('')}</tr>`)
    .join('')}
</tbody>`;
    })
    .join('');

  const matrixPanel = `<section class="panel"><div class="panel-head"><h2>角色权限矩阵</h2><span class="small muted">点分组标题展开/收起；勾选复选框后，点角色列头上的"保存"写入</span></div><div class="perm-note muted small">系统管理员为全量、不可在矩阵勾选。对象级约束（如负责人只能审批普通成员）不在此矩阵控制。</div><div class="table-wrap perm-wrap"><table class="perm-matrix"><thead><tr>${roleHead}</tr></thead>${groups}</table></div></section>`;
  const content = _permMeta.isSuperadmin
    ? uiTab('perm', [['matrix', '权限矩阵', () => matrixPanel], ['nav', '导航配置', () => navAdminSection()]])
    : matrixPanel;
  return `<div class="page-fit">${heading('权限矩阵', '按左侧菜单栏分类配置菜单、页面与按键权限。', headActions, 'PERMISSIONS / 权限配置')}${content}</div>`;
}

// 权限矩阵折叠 / 全选工具
function toggleGroup(id) {
  const s = permExpanded();
  s.has(id) ? s.delete(id) : s.add(id);
  persistExpanded();
  render();
}
function expandAll(open) {
  const s = permExpanded();
  if (open) (_permMeta.groups || []).forEach((g) => s.add(g.name));
  else s.clear();
  persistExpanded();
  render();
}
function checkGroup(id) {
  // 全选本组：给该组每个已显示点、每个可编辑角色打勾；若全已勾则清空（成对切换）
  const boxes = [...document.querySelectorAll(`tbody[data-group="${CSS.escape(id)}"] input[data-role]:not([disabled])`)];
  const allChecked = boxes.length > 0 && boxes.every((b) => b.checked);
  boxes.forEach((b) => { b.checked = !allChecked; });
}

async function saveAll() {
  const toSave = (_permMeta.roles || []).filter((r) => !r.superadmin);
  let total = 0;
  for (const r of toSave) {
    const keys = [...document.querySelectorAll(`input[data-role="${CSS.escape(r.code)}"]:checked`)].map(
      (el) => el.dataset.key,
    );
    await API.request(`/permissions/roles/${r.code}/grant`, {
      method: 'POST',
      body: JSON.stringify({ permissions: keys }),
    });
    total += keys.length;
  }
  _permMeta = null;
  toast(`已保存全部角色（共 ${total} 项权限）`);
  await API.load();
  render();
}

function roleNew() {
  modal(
    '新增角色',
    `<div class="form-grid">${field('角色编码 *', 'code', '', 30, 'placeholder="如：operator，小写字母/数字/下划线"')}${field('角色名称 *', 'name', '', 30)}</div><p class="privacy-note">新增角色初始无任何权限，请在矩阵中为其勾选。</p>`,
    '创建',
    async (f) => {
      await API.request('/permissions/roles', {
        method: 'POST',
        body: JSON.stringify({ code: f.get('code').trim(), name: f.get('name').trim() }),
      });
      _permMeta = null;
      await API.load();
      render();
      toast('角色已创建');
    },
  );
}

function roleRename(code) {
  const r = (_permMeta.roles || []).find((x) => x.code === code);
  modal(
    '重命名角色',
    `<div class="form-grid">${field('角色名称 *', 'name', r?.name || '', 30)}</div>`,
    '保存',
    async (f) => {
      await API.request(`/permissions/roles/${code}/rename`, {
        method: 'POST',
        body: JSON.stringify({ name: f.get('name').trim() }),
      });
      _permMeta = null;
      await API.load();
      render();
      toast('已重命名');
    },
  );
}

function roleDelete(code) {
  const r = (_permMeta.roles || []).find((x) => x.code === code);
  modal(
    '删除角色',
    `<p>确认删除自定义角色「${esc(r?.name || code)}」吗？该角色下若有成员将无法删除。</p>`,
    '删除',
    async () => {
      await API.request(`/permissions/roles/${code}`, { method: 'DELETE' });
      _permMeta = null;
      await API.load();
      render();
      toast('角色已删除');
    },
  );
}

function memberOverride(mid) {
  API.request(`/permissions/members/${mid}`)
    .then((cur) => {
      const allowed = new Set(cur.allowed || []);
      const denied = new Set(cur.denied || []);
      const points = (_permMeta.groups || [])
        .flatMap((g) => (g.points || []))
        .map((p) => p.key);
      const rows = points
        .map(
          (k) =>
            `<tr><td class="perm-point"><span class="mono">${esc(k)}</span></td><td class="perm-cell"><input type="checkbox" name="allow:${esc(k)}" ${allowed.has(k) ? 'checked' : ''}></td><td class="perm-cell"><input type="checkbox" name="deny:${esc(k)}" ${denied.has(k) ? 'checked' : ''}></td></tr>`,
        )
        .join('');
      modal(
        '成员权限覆盖',
        `<p class="privacy-note">在成员所承担角色的权限基础上做加减。允许(Allow)追加权限、拒绝(Deny)回收权限。</p><div class="table-wrap" style="max-height:52vh;overflow:auto"><table class="perm-matrix"><thead><tr><th class="perm-col-name">权限点</th><th>允许</th><th>拒绝</th></tr></thead><tbody>${rows}</tbody></table></div>`,
        '保存',
        async (f) => {
          const a = [], d = [];
          for (const key of points) {
            if (f.get(`allow:${key}`)) a.push(key);
            if (f.get(`deny:${key}`)) d.push(key);
          }
          await API.request(`/permissions/members/${mid}/grant`, {
            method: 'POST',
            body: JSON.stringify({ allowed: a, denied: d }),
          });
          _permMeta = null;
          await API.load();
          document.querySelector('#modal')?.close();
          render();
          toast('成员权限覆盖已保存');
        },
      );
    })
    .catch((e) => toast(e.message, true));
}

// ── 导航配置（动态路由管理）──
function navMove(id, dir) {
  const i = _navAdmin.findIndex((n) => n.id === id);
  const j = i + dir;
  if (i < 0 || j < 0 || j >= _navAdmin.length) return;
  [_navAdmin[i], _navAdmin[j]] = [_navAdmin[j], _navAdmin[i]];
  render();
}
async function navSave() {
  const items = _navAdmin.map((n) => ({
    id: n.id,
    label: document.querySelector(`.nav-row[data-idx="${_navAdmin.indexOf(n)}"] .nav-label`)?.value ?? n.label,
    permission: document.querySelector(`.nav-row[data-idx="${_navAdmin.indexOf(n)}"] .nav-perm`)?.value ?? '',
    icon: n.icon,
    param: n.param,
    enabled: !!document.querySelector(`.nav-row[data-idx="${_navAdmin.indexOf(n)}"] .nav-enable`)?.checked,
    order: 0,
  }));
  await API.request('/nav/save', { method: 'POST', body: JSON.stringify({ items }) });
  await API.load(); // 重新拉 workspace（含最新 nav）
  render();
  toast('导航配置已保存并生效');
}

window.permissionsPage = permissionsPage;
window.PERMISSION_ACTIONS = {
  'perm-save-all': saveAll,
  'perm-role-new': roleNew,
  'perm-role-rename': (code) => roleRename(code),
  'perm-role-delete': (code) => roleDelete(code),
  'member-override': (mid) => memberOverride(mid),
  'perm-group-toggle': (id) => toggleGroup(id),
  'perm-expand-all': () => expandAll(permExpanded().size === 0),
  'perm-group-check': (id) => checkGroup(id),
  'nav-up': (id) => navMove(id, -1),
  'nav-down': (id) => navMove(id, 1),
  'nav-save': navSave,
};