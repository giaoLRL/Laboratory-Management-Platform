'use strict';
// 路由与导航完全由动态数据驱动：菜单可见性/顺序/参数子页由后端 workspace.nav 下发，
// 页面渲染函数通过 registerRenderer() 注册。前端不再硬编码页面清单。
const pageTitle = (v) => NAV.find((n) => n.id === v)?.label || v;
function go(next) {
  const [base, param] = String(next).split('/');
  const item = NAV.find((n) => n.id === base);
  if (!item) return;
  if (item.param) {
    // 参数子页：如 #member/m3（param 为前缀，渲染器必须已注册）
    if (!param || !param.startsWith(item.param) || !Object.hasOwn(PAGE_RENDERERS, base)) return;
    view = base;
    routeParam = param;
    history.replaceState(null, '', `#${base}/${param}`);
  } else {
    if (item.permission && !can(item.permission)) return;
    view = base;
    routeParam = '';
    history.replaceState(null, '', '#' + base);
  }
  search = '';
  filter = '';
  groupFilter = '';
  page = 1;
  render();
  window.scrollTo(0, 0);
}
// 登录页左栏的机甲骑士：纯 SVG + CSS 动画，持续持剑奔跑；点击触发一次挥刀，把词斩成两半。
// 头沿用品牌标里的机甲头多边形（此处不带徽章底）。词库在 features.js 的 mecha-slash 分支里轮换。
function mechaKnight() {
  // 登山版场景：折角山体 + 远山 + 雪冠 + 之字形山道 + 脚下岩台 + 滚落碎石 + 飘雪。
  // 机甲贴坡站立、上半身独立前倾、高抬膝步态；挥刀斩字与词库保持不变，无刀光残影。
  return `<button type="button" class="mecha" data-action="mecha-slash" aria-label="点击让机甲挥刀斩断阻碍"><svg viewBox="0 0 320 200" aria-hidden="true"><defs><clipPath id="mkCutA"><polygon points="64.2 -11 399.8 207 508.8 39.2 173.2 -178.8"/></clipPath><clipPath id="mkCutB"><polygon points="64.2 -11 399.8 207 290.8 374.8 -45.2 156.8"/></clipPath></defs><path class="mk-far2" d="M-5 140 L52 116 L110 138 L160 120 L210 136 L266 114"/><path class="mk-far" d="M-5 120 L38 92 L80 124 L128 98 L176 126 L224 102 L268 118"/><path class="mk-hill" d="M0 205 L96 186 L128 170 L152 162 L208 136 L262 106 L300 72 L320 86 L320 205 Z"/><path class="mk-facet" d="M262 106 L300 72 L320 86 L320 112 L285 118 Z"/><path class="mk-ridge" d="M0 205 L96 186 L128 170 L152 162 L208 136 L262 106 L300 72 L320 86"/><path class="mk-snow" d="M274 99 L284 92 L296 84 L305 89 L293 94 L280 102 Z"/><path class="mk-trail-path" d="M60 197 L110 183 L100 176 L140 162 L130 155 L168 143 L160 136 L220 115 L250 101"/><g transform="rotate(-15 140 164) translate(-21 -12)"><path class="mk-track s1" d="M88 158 l5 2 l-2 4 z"/><path class="mk-track s2" d="M70 170 l4 2 l-1 3 z"/><path class="mk-track s3" d="M104 146 l4 2 l-2 3 z"/></g><g transform="rotate(-9 140 164) translate(-21 -12)"><g class="mk-body"><g class="mk-leg-b"><rect class="mk-plate" x="143" y="130" width="14" height="26" rx="6"/><g class="mk-shin-b"><rect class="mk-plate2" x="144" y="152" width="12" height="20" rx="5"/><rect class="mk-deep" x="141" y="169" width="20" height="7" rx="3.5"/></g></g><g class="mk-lean" transform="rotate(16 160 124)"><path class="mk-plate" d="M136 90H184L180 120H140Z"/><path class="mk-deep" d="M140 120H180L177 132H143Z"/><rect class="mk-plate" x="126" y="88" width="20" height="17" rx="7"/><rect class="mk-plate" x="174" y="88" width="20" height="17" rx="7"/><rect class="mk-plate2" x="146" y="86" width="28" height="6" rx="3"/><path class="mk-acc mk-core" d="M160 97L167 104L160 111L153 104Z"/><rect class="mk-deep" x="152" y="80" width="16" height="12" rx="4"/><g class="mk-head" transform="translate(114.4 20.25) scale(1.9) rotate(-10 24 23)"><path class="h-face" d="M18 12.5H30L35 17.5V26.5L30.5 33.5H17.5L13 26.5V17.5Z"/><path class="h-face2" d="M13 24.6 35 22.6V26.5L30.5 33.5H17.5L13 26.5Z"/><path class="h-visor" d="M13 20.6 35 18.6V22.6L13 24.6Z"/><path class="h-acc" d="M15.2 21.2 32.8 19.7V22.5L15.2 24Z"/><path class="h-s-acc" d="M24 12.6V19.4" stroke-width="1.2" stroke-linecap="round" opacity=".5"/><path class="h-s-visor" d="M20.5 29.8H27.5" stroke-width="1.2" stroke-linecap="round" opacity=".25"/><path class="h-s-antenna" d="M30 12.6 33.6 8.7" stroke-width="1.5" stroke-linecap="round"/><circle class="h-acc" cx="34.2" cy="8" r="1.7"/></g><g class="mk-arm-l"><rect class="mk-plate" x="132" y="98" width="12" height="22" rx="6"/><g class="mk-fore-l"><rect class="mk-plate2" x="133" y="118" width="11" height="18" rx="5"/><circle class="mk-deep" cx="138.5" cy="137" r="6"/></g></g><g class="mk-arm-r"><rect class="mk-plate" x="176" y="98" width="12" height="22" rx="6"/><g class="mk-fore-r"><rect class="mk-plate2" x="177" y="118" width="11" height="18" rx="5"/><g class="mk-sword"><rect class="mk-deep" x="179" y="129" width="7" height="13" rx="3.5"/><path class="mk-s-acc" d="M174.3 133.2L190.7 140.8" stroke-width="4.5" stroke-linecap="round"/><path class="mk-blade" d="M179.6 135.65L185.4 138.35L208.7 80.8Z"/><path class="mk-s-face" d="M182.5 137L208.7 80.8" stroke-width="1.2" opacity=".75"/><path class="mk-s-face mk-glint" d="M182.5 137L188.4 124.3" stroke-width="2.6" stroke-linecap="round" opacity="0"/></g><circle class="mk-deep" cx="182.5" cy="137" r="6"/></g></g></g><rect class="mk-plate" x="141" y="128" width="38" height="5" rx="2.5"/><g class="mk-leg-f"><rect class="mk-plate" x="163" y="130" width="14" height="26" rx="6"/><g class="mk-shin-f"><rect class="mk-plate2" x="164" y="152" width="12" height="20" rx="5"/><rect class="mk-deep" x="161" y="169" width="20" height="7" rx="3.5"/></g></g></g></g><path class="mk-rock" d="M119 169 L135 169 L133 162 L121 162 Z"/><path class="mk-hi" d="M121 163 L133 163"/><path class="mk-rock" d="M144 167 L161 167 L158 159 L147 160 Z"/><path class="mk-hi" d="M147 161 L158 161"/><path class="mk-rock" d="M113 172 L124 172 L122 167 L114 168 Z"/><path class="mk-hi" d="M114 168.5 L122 168.5"/><g class="mk-flakes" aria-hidden="true"><circle class="mk-flake" cx="30" cy="34" r="2" style="animation-delay:-.4s"/><circle class="mk-flake b" cx="58" cy="12" r="1.6" style="animation-delay:-2.1s"/><circle class="mk-flake" cx="86" cy="46" r="2.2" style="animation-delay:-3.3s;animation-duration:7.2s"/><circle class="mk-flake b" cx="118" cy="20" r="1.5" style="animation-delay:-.9s;animation-duration:5.8s"/><circle class="mk-flake" cx="146" cy="54" r="2.4" style="animation-delay:-4.6s"/><circle class="mk-flake b" cx="176" cy="26" r="1.7" style="animation-delay:-1.6s"/><circle class="mk-flake" cx="204" cy="60" r="2" style="animation-delay:-5.2s;animation-duration:7.6s"/><circle class="mk-flake b" cx="232" cy="16" r="1.5" style="animation-delay:-2.8s"/><circle class="mk-flake" cx="260" cy="44" r="2.2" style="animation-delay:-3.9s"/><circle class="mk-flake b" cx="288" cy="24" r="1.8" style="animation-delay:-5.8s;animation-duration:6.2s"/><circle class="mk-flake" cx="200" cy="82" r="1.6" style="animation-delay:-.2s"/><circle class="mk-flake b" cx="150" cy="72" r="1.5" style="animation-delay:-6.1s"/></g><g class="mk-words" aria-hidden="true"><g class="mk-cut-a" clip-path="url(#mkCutA)"><text class="mk-word" x="232" y="112" text-anchor="middle">困难</text></g><g class="mk-cut-b" clip-path="url(#mkCutB)"><text class="mk-word" x="232" y="112" text-anchor="middle">困难</text></g><path class="mk-cutline" d="M185.9 54L278.1 114"/></g></svg></button>`;
}
function loginPage() {
  return `<div class="login"><section class="login-art"><div class="login-top"><img class="login-school-logo" src="/assets/img/school-logo.png" alt="湖南科技学院"><div class="brand"><div class="brandmark">${labMark()}</div><div><strong>具身智能 <span style="font-weight:400">实验室</span></strong><small>EMBODIED AI LAB</small></div></div></div><div class="login-copy"><div class="eyebrow">让科技有温度</div><h1>去够那些，<br>够不着的想法。</h1><p>每一行代码都在靠近明天，<br>每一次焊接都在点亮灵感。<br>探索没有边界，未来可以亲手发生。</p></div>${mechaKnight()}<blockquote class="login-quote"><p>山的魅力是从两个方位感受到的：一是从平原上远远地看山，再就是站在山顶上。</p><cite>—— 刘慈欣《山》</cite></blockquote><div class="login-art-footer">具身智能实验室 &nbsp; / &nbsp; 管理平台</div></section><section class="login-form-wrap"><form class="login-form" id="login-form"><div class="eyebrow">WELCOME BACK</div><h1>欢迎回到实验室</h1><p>登录你的账号，开始今天的探索。</p><div class="field"><label for="username">账号</label><input id="username" name="username" autocomplete="username" placeholder="请输入账号" required value=""></div><div class="field"><label for="password">密码</label><input id="password" name="password" type="password" autocomplete="current-password" placeholder="请输入密码" required value=""></div><div class="row between small muted" style="margin-bottom:20px"><span>${icon('shield')} &nbsp;实验室统一工作台</span><span>${CONFIG.mode === 'mock' ? '本地演示版' : '云端登录'}</span></div><button class="btn primary" type="submit">登录工作台 ${icon('arrow')}</button><div class="form-error" id="login-error" role="alert"></div>${CONFIG.mode === 'mock' ? `<div class="test-accounts"><p>选择测试身份，自动填入账号</p><div class="account-buttons"><button type="button" data-action="fill-account" data-value="teacher">指导老师</button><button type="button" data-action="fill-account" data-value="manager">负责人</button><button type="button" data-action="fill-account" data-value="member">普通成员</button></div><small>初始测试账号密码：<span class="mono">Lab@123456</span></small></div><p class="login-caption">当前为前端演示，数据仅保存在此浏览器。<br>新成员请使用管理员创建的账号和密码。<br>阿里云后端尚未连接。</p>` : ''}</form></section></div>`;
}
function shell() {
  const u = me(),
    pending = pendingCount() + (db.unread_notifications || 0),
    loanPending = db.loans.filter((l) => needsLoanReview(l)).length;
  // 详情子页（params）→ 父菜单高亮；同时作为顶栏返回目标
  const subNav = { member: 'members', task: 'tasks' };
  const activeNav = subNav[view] || view;
  const backTo = subNav[view] || '';
  const crumb = backTo
    ? `<button class="back-link" data-action="nav" data-view="${backTo}" aria-label="返回${esc(pageTitle(backTo) || '上级')}">${icon('arrow', 'back-arrow')} ${esc(pageTitle(backTo) || '返回')}</button><span class="home-label">/</span><span>${esc(pageTitle(view))}</span>`
    : `<span class="home-label">实验室管理</span><span class="home-label">/</span><span>${esc(pageTitle(view))}</span>`;
  return `<div class="overlay" data-action="close-menu"></div><aside class="sidebar" id="main-sidebar"><div class="brand"><div class="brandmark">${labMark()}</div><div><strong>具身智能 <span style="font-weight:400">实验室</span></strong><small>管理平台</small></div></div><div class="nav-label">WORKSPACE · 工作空间</div><nav class="nav" aria-label="主导航">${NAV.filter((item) => !item.param && !(item.permission && !can(item.permission))).map((item) => `<button class="${activeNav === item.id ? 'active' : ''}" data-action="nav" data-view="${item.id}" ${activeNav === item.id ? 'aria-current="page"' : ''}>${icon(item.icon)}<span>${esc(item.label)}</span>${item.id === 'loans' && loanPending ? `<span class="count">${loanPending}</span>` : ''}</button>`).join('')}</nav><div class="sidebar-bottom"><div class="lab-card"><div class="row" style="gap:8px;color:#4a4e55">${icon('chip')}<strong>具身智能实验室</strong></div><p>让设备物尽其用，让协作有迹可循。</p><div class="row" style="margin-top:12px;font-size:10px;color:#7c9b90"><span class="dot"></span>${CONFIG.mode === 'mock' ? '本地演示空间' : '云端工作空间'}</div></div><div class="sidebar-footer"><span>具身智能实验室 © 2026</span><span>v1.0</span></div></div></div></aside><main class="main"><header class="topbar"><div class="row"><button class="icon-btn mobile-menu" data-action="menu" aria-label="打开导航" aria-controls="main-sidebar" aria-expanded="false">${icon('menu')}</button><div class="breadcrumb">${crumb}</div></div><div class="top-actions"><span class="mode"><span class="dot"></span>${CONFIG.mode === 'mock' ? '本地演示 · 数据已保存于浏览器' : 'API 模式'}</span><button class="icon-btn" data-action="notifications" aria-label="查看待办通知">${icon('bell')}${pending ? '<i class="notification-dot"></i>' : ''}</button><span class="divider"></span><button class="row" data-action="nav" data-view="profile" style="gap:10px" aria-label="打开个人中心">${avatar(u)}<span class="profile-name">${esc(u.name)}<small>${roleLabel(u)}</small></span>${icon('down')}</button><button class="icon-btn" data-action="logout" aria-label="退出登录" title="退出登录">${icon('logout')}</button></div></header><div class="content" id="content">${renderView()}</div></main>`;
}
function dashboard() {
  const people = db.members.filter((m) => m.active),
    assets = countStatuses(db.assets, assetStatus),
    members = countStatuses(people, memberStatus);
  const available = assets['空闲'] || 0,
    using = assets['使用中'] || 0,
    repair = assets['维修中'] || 0,
    retired = assets['已报废'] || 0,
    total = db.assets.length;
  const free = members['空闲'] || 0,
    busy = members['忙碌'] || 0,
    leave = members['请假'] || 0,
    offline = members['离线'] || 0,
    late = db.loans.filter(overdue).length;
  const usage = Math.round(percentage(using, total - retired)),
    todos = todoItems();
  const vh = typeof window !== 'undefined' ? window.innerHeight : 900;
  const dashCount = vh < 760 ? 3 : vh < 1000 ? 4 : 5; // 工作台单列/表格显示条数
  const today = serverNow().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' });
  const active = db.loans.filter(isActiveLoan);
  const statsRow = `<div class="stats">${statsCard('实验室成员', people.length, '人', 'users', '', `<span class="mini-tag">${free} 人空闲</span><span>${busy} 忙碌 · ${leave} 请假 · ${offline} 离线</span>`, 'members')}${statsCard('硬件模块', total, '件', 'chip', 'purple', `<span>${new Set(db.assets.map((a) => a.category)).size} 个分类</span><span>·</span><span>${new Set(db.assets.map((a) => a.model)).size} 种型号</span>`, 'assets')}${statsCard('可用模块', available, '件', 'box', 'green', `<span class="mini-tag">随时可借用</span><span>${using} 件使用中</span>`, 'assets')}${statsCard('待处理事项', canApprove() ? pendingCount() : db.loans.filter((l) => l.memberId === me().id && l.status === '待审批').length, '项', 'clock', 'orange', `<span style="color:${late ? '#cf8a43' : '#8992a4'}">${late} 笔借用已逾期</span><span>·</span><span>${repair} 件维修中</span>`, 'loans')}</div>`;
  const memberPanel = `<section class="panel"><div class="panel-head"><h2>成员状态 <span>${people.length} 位成员</span></h2><div class="legend"><span><i style="background:#26a078"></i>空闲</span><span><i style="background:#3b5c93"></i>忙碌</span><span><i style="background:#d29740"></i>请假</span></div></div><div class="member-grid">${people.slice(0, dashCount).map(memberCard).join('')}</div><div class="panel-foot"><span><span class="dot" style="width:4px;height:4px"></span> &nbsp;状态根据当前记录计算</span><button class="text-btn" data-action="nav" data-view="members">查看全部成员 ${icon('arrow')}</button></div></section>`;
  const loanPanel = `<section class="panel"><div class="panel-head"><div><h2>正在使用的模块</h2><p>追踪设备去向，让每一件硬件都有记录</p></div><button class="text-btn" data-action="nav" data-view="loans">全部记录 ${icon('chevron')}</button></div><div class="table-wrap"><table><thead><tr><th>模块 / 型号</th><th>使用者</th><th>预计归还</th><th>状态</th></tr></thead><tbody>${active
    .flatMap((l) =>
      l.assetIds.map((id) => {
        const a = asset(id);
        return `<tr><td><button class="row" style="text-align:left;padding:0" data-action="asset-detail" data-id="${a.id}">${assetIcon(a)}<span><strong>${esc(a.name)}</strong><small class="mono">${esc(a.id)}</small></span></button></td><td>${esc(member(l.memberId)?.name)}</td><td style="color:${overdue(l) ? '#d28370' : 'inherit'}">${fmt(l.due)}</td><td>${badge(overdue(l) ? '逾期' : l.status)}</td></tr>`;
      }),
    )
    .slice(0, dashCount)
    .join('')}</tbody></table>${!active.length ? empty('暂无借出模块', '当前所有可用设备均已归还。') : ''}</div></section>`;
  const usagePanel = () => `<section class="panel"><div class="panel-head"><h2>模块使用概况</h2><span class="small muted">共 ${total} 件</span></div><div class="utilization"><div class="donut" style="background:conic-gradient(#3b5c93 0 ${percentage(using, total)}%,#4f9c82 ${percentage(using, total)}% ${percentage(using + available, total)}%,#d8a45c ${percentage(using + available, total)}% ${percentage(using + available + repair, total)}%,#e2e2e0 0)"><div class="donut-label"><strong>${usage}<span style="display:inline;font-size:17px;color:#33363c">%</span></strong><span>在册资产使用率</span></div></div><div class="chart-legend">${[
    ['使用中', using, '#3b5c93'],
    ['空闲', available, '#4f9c82'],
    ['维修中', repair, '#d8a45c'],
    ['已报废', retired, '#e2e2e0'],
  ]
    .map(([s, n, c]) => `<div><i style="background:${c}"></i>${s}<b>${n}</b></div>`)
    .join('')}</div></div><div class="usage-bottom"><span>设备可借用率（含全部资产）</span><strong>${Math.round(percentage(available, total))}% 可借用 ${icon('check')}</strong></div></section>`;
  const todoPanel = () => `<section class="panel"><div class="panel-head"><h2>${canApprove() ? '待办提醒' : '我的提醒'} <span>${todos.length}</span></h2><button class="text-btn" data-action="nav" data-view="notifications">查看全部</button></div><div class="todo-list">${
    todos
      .slice(0, 4)
      .map(
        (t) =>
          `<div class="todo"><span class="todo-icon ${t.orange ? 'orange' : ''}">${icon(t.icon)}</span><div>${stack(t.title, t.description)}</div><button class="arrow" data-action="nav" data-view="${t.view}" aria-label="查看${esc(t.title)}">${icon('chevron')}</button></div>`,
      )
      .join('') || empty('暂无待办', '可以专注于你的实验了。')
  }</div></section>`;
  const activityPanel = () => `<section class="panel"><div class="panel-head"><h2>最近动态</h2><span class="small muted">实验室足迹</span></div><div class="activity">${
    visibleLogs()
      .slice(0, 4)
      .map((l) => `<div class="activity-item">${esc(l.actor)} · ${esc(l.text)}<small>${fmt(l.at, true)}</small></div>`)
      .join('') || '<span class="small muted">暂无动态</span>'
  }</div></section>`;
  const [hi, emoji] = greetingText();
  return `<div class="page-fit">${heading(`${hi}，${esc(me().name)} <span style="font-size:22px">${emoji}</span>`, `今天是 ${today}，一起让实验室高效运转。`, btn(`${icon('calendar')} 申请请假`, 'leave-new') + btn(`${icon('plus')} 借用模块`, 'loan-new', 'primary'), 'LAB OVERVIEW / 实验室概览')}${statsRow}<div class="grid-main grid-fill"><div>${memberPanel}${loanPanel}</div><div>${uiTab('dash', [
    ['usage', '使用概况', usagePanel],
    ['todo', '待办提醒', todoPanel],
    ['activity', '最近动态', activityPanel],
  ])}</div></div></div>`;
}
// 按服务器时间返回问候语与图标（未校准到服务器时回退本地时间）
function greetingText() {
  const h = serverNow().getHours();
  if (h < 5) return ['凌晨好', '🌙'];
  if (h < 9) return ['早上好', '🌅'];
  if (h < 12) return ['上午好', '☀️'];
  if (h < 14) return ['中午好', '🌞'];
  if (h < 18) return ['下午好', '☀️'];
  return ['晚上好', '🌙'];
}
function renderView() {
  const fn = Object.hasOwn(PAGE_RENDERERS, view) ? PAGE_RENDERERS[view] : null;
  return fn ? fn(routeParam) : empty('页面不存在', '请从导航选择页面。');
}
function render() {
  const root = document.querySelector('#app');
  root.innerHTML = me() ? shell() : loginPage();
  syncNavigationAccessibility();
}
document.addEventListener('click', async (e) => {
  const b = e.target.closest('[data-action]');
  if (!b) return;
  try {
    await action(b.dataset.action, b);
  } catch (err) {
    toast(err.message, true);
  }
});
document.addEventListener('submit', async (e) => {
  const login = e.target.id === 'login-form';
  if (!login && (e.target.id !== 'modal-form' || !modalSubmit)) return;
  e.preventDefault();
  const button = e.target.querySelector('button[type=submit]'),
    label = button.innerHTML;
  button.disabled = true;
  button.textContent = login ? '正在登录…' : '正在保存…';
  try {
    const form = new FormData(e.target);
    if (login) {
      await API.login(form.get('username').trim(), form.get('password'));
      go('dashboard');
      checkFirstLoginGates();
      maybeOpenScannedCheckin(); // 扫码进来但未登录：登录后直接接着打卡
    } else await modalSubmit(form);
  } catch (err) {
    document.querySelector(login ? '#login-error' : '#modal-error').textContent = err.message;
  } finally {
    button.disabled = false;
    button.innerHTML = label;
  }
});
async function action(type, b) {
  if (type === 'fill-account') {
    // mock 演示：仅填入账号，密码由用户手动输入（不在页面里预置明文密码）
    document.querySelector('#username').value = b.dataset.value;
    document.querySelector('#password').focus();
    return;
  }
  if (type === 'nav') {
    go(b.dataset.view);
    return;
  }
  if (type === 'logout') {
    await API.logout();
    render();
    return;
  }
  if (type === 'menu') {
    setMobileMenu(true);
    return;
  }
  if (type === 'close-menu') {
    setMobileMenu(false);
    return;
  }
  return handleAction(type, b);
}
async function init() {
  captureScanCode(); // 扫码进入：先收起 ?c=（此时可能还没登录）
  try {
    await API.load();
    const [base, param] = location.hash.slice(1).split('/');
    const item = NAV.find((n) => n.id === base);
    if (item && !item.param) {
      view = base;
      routeParam = param || '';
    } else if (item && item.param && param && Object.hasOwn(PAGE_RENDERERS, base)) {
      view = base;
      routeParam = param;
    }
    render();
    checkFirstLoginGates();
    maybeOpenScannedCheckin();
  } catch (e) {
    document.querySelector('#app').innerHTML =
      `<div class="loading"><h2>暂时无法读取数据</h2><p style="margin:15px">${esc(e.message)}</p>${btn('重试', 'reload')}${CONFIG.mode === 'mock' ? btn('恢复演示数据', 'reset') : ''}</div>`;
  }
}
// 首次登录强制完善资料；管理员重置密码后提醒改密（叠加时资料完成后连弹改密框）
function checkFirstLoginGates() {
  const u = me();
  if (u?.mustCompleteProfile && typeof completeProfileModal === 'function') {
    completeProfileModal();
  } else if (u?.mustChangePassword && typeof changePasswordModal === 'function') {
    changePasswordModal(true);
  }
}
window.addEventListener('hashchange', () => go(location.hash.slice(1)));

// 页面渲染器注册（静态 map：路由/菜单的可见性、顺序由后端 nav 维护，渲染函数在此登记）
registerRenderer('dashboard', dashboard);
registerRenderer('competitions', competitionsPage);
registerRenderer('members', membersPage);
registerRenderer('assets', assetsPage);
registerRenderer('loans', loansPage);
registerRenderer('leaves', leavesPage);
registerRenderer('tasks', tasksPage);
registerRenderer('levels', levelsPage);
registerRenderer('checkins', checkinsPage);
registerRenderer('seats', seatsPage);
registerRenderer('leaderboard', leaderboardPage);
registerRenderer('agent', agentPage);
registerRenderer('logs', logsPage);
registerRenderer('profile', profilePage);
registerRenderer('permissions', permissionsPage);
registerRenderer('announcements', announcementsPage);
registerRenderer('email', emailPage);
registerRenderer('notifications', notificationsPage);
registerRenderer('news', newsPage);
registerRenderer('groups', groupsPage);
registerRenderer('login-logs', loginLogsPage);
registerRenderer('member', memberDetailPage);
registerRenderer('task', taskDetailPage);
registerRenderer('homepage', homepagePage);

document.addEventListener('DOMContentLoaded', init, { once: true });
