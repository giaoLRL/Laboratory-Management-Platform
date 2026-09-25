import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { webcrypto } from 'node:crypto';
import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const scripts = [...html.matchAll(/<script defer src="([^"]+)"><\/script>/g)].map((m) => m[1]);
const source = scripts.map((p) => readFileSync(new URL('../' + p, import.meta.url), 'utf8'));

/* 与 core.test.mjs 同样的最小浏览器环境：无 DOM 也要能定义模块 */
function setup() {
  const storage = () => {
    const map = new Map();
    return { getItem: (k) => (map.has(k) ? map.get(k) : null), setItem: (k, v) => map.set(k, String(v)),
      removeItem: (k) => map.delete(k), clear: () => map.clear() };
  };
  const context = vm.createContext({
    console, Date, Math, JSON, Promise, AbortController, FormData, TextEncoder,
    crypto: webcrypto, Uint8Array, setTimeout, clearTimeout,
    setInterval: () => {}, clearInterval: () => {},
    requestAnimationFrame: (fn) => { if (typeof fn === 'function') fn(); },
    localStorage: storage(), sessionStorage: storage(),
    document: {
      addEventListener() {},
      querySelector() {
        const set = new Set();
        const el = {
          open: false, innerHTML: '', textContent: '', style: {}, dataset: {},
          classList: { add: (...c) => c.forEach((x) => set.add(x)), remove: (...c) => c.forEach((x) => set.delete(x)),
            toggle: (c, f) => (f ? set.add(c) : set.delete(c)), contains: (c) => set.has(c) },
          close() {}, showModal() {}, append() {}, remove() {}, addEventListener() {},
          setAttribute() {}, scrollIntoView() {}, focus() {}, querySelector: () => null,
          querySelectorAll: () => [],
          scrollTop: 0, scrollHeight: 0, clientHeight: 0,
        };
        /* innerHTML 写入后 firstElementChild 要有东西 —— 走动动画靠它拿 walker */
        el.firstElementChild = { style: {} };
        return el;
      },
      querySelectorAll() { return []; },
      createElement() { return { remove() {}, style: {}, appendChild() {}, classList: { add() {}, remove() {}, toggle() {} } }; },
    },
    window: { addEventListener() {}, scrollTo() {}, matchMedia() { return { matches: false }; } },
    location: { hash: '' }, history: { replaceState() {} },
  });
  source.forEach((s) => vm.runInContext(s, context));
  const run = (code) => vm.runInContext(code, context);
  return { run, context };
}

/* B 区平面：与后端种子迁移 apps/seats/migrations/0002_seed_default_layout.py 一致 */
const GRID = ['#############', '#d..........#', '#.ss...ss...#', '#.ww...ww...#', '#.ww...ww...#',
  '#...ttttt...#', '#.ww...ww...#', '#.ww...ww...#', '#.ss...ss...#', '#...........#', '#############'];
const LABELS = (() => {
  const out = {}; let n = 0;
  GRID.forEach((row, r) => [...row].forEach((k, c) => { if (k === 'w') { n += 1; out[`${r}-${c}`] = `B-${String(n).padStart(2, '0')}`; } }));
  return out;
})();

function seatsSetup() {
  const { run, context } = setup();
  run("CONFIG.mode='mock';sessionId='m1';db=seed()");
  run(`db.seatLayout=${JSON.stringify({ id: 'main', name: 'B 区', rows: 11, cols: 13, grid: GRID, labels: LABELS, owners: {} })}`);
  run("db.seatPresence=[{memberId:'m3',row:3,col:2},{memberId:'m5',row:1,col:5}]");
  run("db.seatStatuses=[{memberId:'m3',statusKey:'debug',text:'在跑电机闭环'}]");
  run("db.seatCharacters=[{memberId:'m3',parts:{skin:'#eec096',hairStyle:'spike',hairColor:'#3a3f46',top:'#243E70',chair:'#9aa0a8',prop:'pc',glasses:true}}]");
  run("db.seatBubbles=[{memberId:'m3',text:'去借万用表',expiresAt:new Date(Date.now()+60000).toISOString()}]");
  run('db.seatChatUnread=3');
  return { run, context };
}

test('从导航点击进入座位页（走 go() 真实点击路径）', () => {
  const { run } = seatsSetup();
  run("NAV=[{id:'seats',label:'实验室座位',icon:'pin',permission:'page:seats',param:''}]");
  run("db.permissions=['page:seats','action:seats.move','action:seats.status','action:seats.bubble','action:seats.chat']");
  run("view='dashboard'");
  run("go('seats')");
  assert.equal(run('view'), 'seats', 'go(seats) 应把视图切到 seats');
  const out = run('renderView()');
  assert.ok(!out.includes('页面不存在'), '不得落到「页面不存在」兜底');
  assert.ok(out.includes('seat-room'), '应渲染出俯视图容器');
  assert.ok(out.includes('data-action="seat-cell"'), '应渲染出可点击格子');
  /* 注册表本身必须真的有 seats 这一项 */
  assert.equal(run('Object.hasOwn(PAGE_RENDERERS,"seats")'), true);
  assert.equal(run('typeof PAGE_RENDERERS.seats'), 'function');
});

test('全部后端导航项都有对应渲染器（防止菜单点出「页面不存在」）', () => {
  const { run } = seatsSetup();
  /* 与后端 NavItem 表一致的 24 项（见 apps/accounts/migrations） */
  const navIds = ['dashboard', 'members', 'leaves', 'assets', 'loans', 'competitions', 'tasks',
    'levels', 'checkins', 'leaderboard', 'agent', 'logs', 'profile', 'permissions',
    'announcements', 'email', 'groups', 'login-logs', 'homepage', 'seats', 'member', 'task'];
  const missing = navIds.filter((id) => run(`!Object.hasOwn(PAGE_RENDERERS,${JSON.stringify(id)})`));
  assert.deepEqual(missing, [], `这些导航项没有渲染器：${missing.join(', ')}`);
  for (const id of navIds) {
    assert.equal(run(`typeof PAGE_RENDERERS[${JSON.stringify(id)}]`), 'function', `${id} 的渲染器不是函数`);
  }
});

test('聊天态与地图编辑态：面板结构一致、地图区 DOM 完全相同（不被挤动/遮挡）', () => {
  const { run } = seatsSetup();
  run("db.permissions=['page:seats','action:seats.manage','action:seats.chat','action:seats.move']");
  run("view='seats'");
  const chat = run('renderView()');
  run('_seatEdit=seatEditDraft(seatLayout())');
  const edit = run('renderView()');

  /* 工具栏在舞台内部、两模式本就不同（图例 vs 笔刷），因此比容器开标签与几何；
     地图卡片里已不放任何工具，所以两模式留给地图的高度由结构保证一致。 */
  const stageTagOf = (html) => {
    const i = html.indexOf('<div class="seat-stage"');
    return html.slice(i, html.indexOf('>', i));
  };
  assert.equal(stageTagOf(chat), stageTagOf(edit), '两种模式的舞台容器属性必须一致');
  /* 地图卡片里只能有地图：图例/笔刷都必须在右侧控制列，否则会吃掉地图高度 */
  const stageInner = (html) => {
    const i = html.indexOf('id="seat-stage"');
    return html.slice(i, html.indexOf('id="seat-side"'));
  };
  assert.ok(!/class="seat-top"/.test(stageInner(chat)), '聊天态地图卡片内不得有工具栏');
  assert.ok(!/class="seat-top"/.test(stageInner(edit)), '编辑态地图卡片内不得有工具栏');
  assert.ok(!/seat-brushes/.test(stageInner(edit)), '笔刷不应出现在地图卡片内');
  assert.ok(!/seat-legend/.test(stageInner(chat)), '图例不应出现在地图卡片内');
  assert.ok(/class="seat-tools" id="seat-tools"/.test(chat), '图例应放在右侧控制列');
  assert.ok(/id="seat-side"[\s\S]*class="seat-tools"/.test(chat), '控制列应位于右列');
  const gridOf = (html) => (html.match(/grid-template-columns:[^"]+/) || [])[0];
  assert.equal(gridOf(chat), gridOf(edit), '网格模板（列宽行高间距）必须完全一致');
  assert.ok(/repeat\(13,64px\)/.test(gridOf(chat)) && /repeat\(11,64px\)/.test(gridOf(chat)),
    '网格应为 13×64px / 11×64px');
  const posOf = (html) => [...html.matchAll(/grid-column:(\d+);grid-row:(\d+)/g)].map((m) => m[0]).join('|');
  assert.equal(posOf(chat), posOf(edit), '每个格子的行列位置必须完全一致（地图不动）');
  assert.equal(posOf(chat).split('|').length, 143, '两模式都应是 143 个格子');
  /* 两种模式的格子总数必须相同，否则地图会被撑变形 */
  assert.equal([...chat.matchAll(/class="seat-cell/g)].length, [...edit.matchAll(/class="seat-cell/g)].length,
    '两模式格子数必须相同');
  assert.ok(/class="panel seat-panel"/.test(chat), '聊天态面板结构固定');
  assert.ok(/class="panel seat-panel"/.test(edit), '编辑态不得改变面板结构/类名');
  assert.ok(chat.indexOf('id="seat-stage"') < chat.indexOf('id="seat-side"'), '地图列在左、侧栏列在右');

  const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');
  const panel = css.slice(css.indexOf('.seat-panel {'), css.indexOf('.seat-panel {') + 400);
  assert.ok(/display: grid/.test(panel), '面板应用 Grid 布局（flex 会被侧栏内容挤动地图列）');
  assert.ok(/grid-template-columns: minmax\(0, 1fr\) var\(--seat-side-w\)/.test(panel),
    '地图列应为 minmax(0,1fr)，侧栏列宽由 --seat-side-w 定死');
  assert.ok(/--seat-side-w: 320px/.test(panel), '应有默认侧栏宽度变量');

  /* 缩放原点决定视觉盒位置：中心原点会让地图整体偏移到侧栏下面（这就是“白色遮挡”的成因） */
  const room = css.slice(css.indexOf('.seat-room {'), css.indexOf('.seat-room {') + 400);
  assert.ok(/transform-origin: top left/.test(room), '.seat-room 必须用左上角缩放原点');
  assert.ok(!/transform-origin:\s*center/.test(room), '不能用中心原点（视觉盒会偏移并溢入侧栏）');
  const fit = css.slice(css.indexOf('.seat-fit {'), css.indexOf('.seat-fit {') + 220);
  assert.ok(/overflow: hidden/.test(fit), '.seat-fit 应 overflow:hidden，兜住任何外溢');
  /* 侧栏宽度只由变量决定，不能再各自写死 */
  assert.ok(!/\.seat-chat \{[^}]*width: \d+px/.test(css), '.seat-chat 不应再写死宽度');

  /* 地图卡片内无工具 ⇒ seatFit 不该再为工具栏预留空间，直接用满整张卡片 */
  const src = readFileSync(new URL('../src/seats.js', import.meta.url), 'utf8');
  assert.ok(!/offsetHeight \+ GAP|reserved/.test(src), 'seatFit 不应再为工具栏预留高度');
  assert.ok(/availH = stage\.clientHeight - padY/.test(src), 'seatFit 应用满整张卡片的高度');
  assert.ok(/max-width: 100%/.test(fit), '.seat-fit 应限制在可用空间内');
});

test('空间预算：侧栏收窄 + 地图独占卡片后，常见屏上地图都更大', () => {
  /* 与真实 CSS 同源的算式：.content 最大宽 1600、左右内边距 60；面板 gap 12；卡片内边距 12×2 */
  const sizeAt = (W, side) => {
    const content = Math.min(1600, W - 232) - 60;
    const stage = content - side - 12;
    const inner = stage - 24;
    return { inner, widthScale: Math.floor(Math.min(1, inner / 894) * 100) / 100 };
  };
  const newSide = (W) => (W > 1680 ? 320 : W > 1280 ? 300 : 280);
  const oldSide = (W) => (W > 1680 ? 430 : W > 1440 ? 380 : 340);
  const rows = [];
  for (const W of [1920, 1440, 1366]) {
    const now = sizeAt(W, newSide(W));
    const before = sizeAt(W, oldSide(W));
    rows.push({ W, 前: before.inner, 后: now.inner, 前缩放: before.widthScale, 后缩放: now.widthScale });
    assert.ok(now.inner > before.inner, `${W}px：地图可用宽度应增加`);
    assert.ok(now.widthScale >= before.widthScale, `${W}px：宽度方向缩放不应变差`);
    assert.ok(now.widthScale >= 0.7, `${W}px：宽度方向缩放应 ≥0.7，实际 ${now.widthScale}`);
  }
  console.log('    空间预算:', rows.map((r) => `${r.W}px ${r.前}→${r.后}px(${r.前缩放}→${r.后缩放})`).join('  '));
  /* 1920 屏宽度方向不再是瓶颈 */
  assert.ok(sizeAt(1920, newSide(1920)).widthScale >= 1, '1920 屏宽度应足够 1:1');
  const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');
  for (const w of ['320px', '300px', '280px']) {
    assert.ok(css.includes(`--seat-side-w: ${w}`), `CSS 应包含侧栏宽度断点 ${w}`);
  }
});

test('座位面板的布局规则必须赢过 .page-fit > .panel 的 flex 规则（优先级）', () => {
  /* 这是真实踩过的坑：只写 `.seat-panel` 会被 `.page-fit > .panel{display:flex;flex-direction:column}`
     （2 个类）覆盖，面板被排成纵向两行 —— 地图在上、侧栏在下，地图高度只剩几百像素、
     缩放掉到 0.44，表现就是「地图特别小」。选择器必须至少同样是 3 个类。 */
  const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');
  /* 逐条扫描规则，锁定「选择器含 .seat-panel 且声明 display:grid」的那条 */
  const rules = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((m) => ({ sel: m[1].trim(), body: m[2] }));
  const gridRule = rules.find((r) => /\.seat-panel/.test(r.sel) && /display:\s*grid/.test(r.body));
  assert.ok(gridRule, '应存在 .seat-panel 的 display:grid 规则');
  assert.ok(/\.page-fit/.test(gridRule.sel) && /\.panel/.test(gridRule.sel),
    `Grid 规则的选择器必须同时含 .page-fit/.panel/.seat-panel 才能压过通用面板规则，当前是「${gridRule.sel}」`);
  /* 通用面板规则确实存在（说明这个优先级冲突是真的） */
  assert.ok(/\.page-fit\s*>\s*\.panel\s*\{[^}]*display:\s*flex/.test(css),
    '通用 .page-fit > .panel 规则应存在');
  /* 断点里的变量覆盖也要用同等优先级的写法，否则媒体查询会被基础规则压掉 */
  for (const w of ['300px', '280px']) {
    const m = css.match(new RegExp(`([^{}]+)\\{[^{}]*--seat-side-w:\\s*${w}`));
    assert.ok(m && /\.page-fit/.test(m[1]) && /\.seat-panel/.test(m[1]),
      `侧栏断点 ${w} 的选择器也必须含 .page-fit/.seat-panel`);
  }
  /* 地图盒子的尺寸不能被父容器拉伸：否则网格轨道溢出卡片，后几列飘在外面 */
  const room = css.slice(css.indexOf('.seat-room {'));
  assert.ok(/width:\s*max-content/.test(room.slice(0, 420)), '.seat-room 必须 width:max-content');
});

test('构建标记与 index.html 的版本号一致（页头数字能反映真实构建）', () => {
  const src = readFileSync(new URL('../src/seats.js', import.meta.url), 'utf8');
  const build = Number((src.match(/const SEAT_BUILD = (\d+)/) || [])[1]);
  const path = scripts.find((p) => p.startsWith('/src/seats.js')) || '';
  const v = Number(path.split('=').pop());
  assert.ok(Number.isFinite(build), 'seats.js 应有 SEAT_BUILD 常量');
  assert.equal(build, v, `SEAT_BUILD(${build}) 应与 index.html 的 ?v=(${v}) 一致，否则页头数字会骗人`);
  const { run } = seatsSetup();
  run("view='seats'");
  assert.ok(run('renderView()').includes(`b${build}`), '页头应显示构建标记，便于确认浏览器跑的是哪一版');
});

test('聊天面板与座位图并排常驻，没有收起/展开的两态切换', () => {
  const { run } = seatsSetup();
  run("view='seats'");
  const out = run('renderView()');
  /* 一进页面就同时有座位图和聊天输入框 */
  assert.ok(out.includes('id="seat-room"'), '应有座位图');
  assert.ok(out.includes('id="seat-chat-input"'), '聊天输入框应默认就在页面上');
  assert.ok(out.includes('id="seat-chat-list"'), '消息列表应默认就在页面上');
  assert.ok(out.includes('id="seat-side"'), '侧栏应有稳定锚点');
  /* 不该再有收起态（竖排 rail / 收起按钮） */
  assert.ok(!out.includes('seat-rail'), '不应再有收起态 rail');
  assert.ok(!out.includes('seat-fold'), '不应再有收起按钮');
  assert.equal(run("typeof SEATS_ACTIONS['seat-chat-toggle']"), 'undefined', '不应再有展开/收起动作');
  const src = readFileSync(new URL('../src/seats.js', import.meta.url), 'utf8');
  assert.ok(!/_seatChatOpen/.test(src), '不应再保留 _seatChatOpen 两态开关');
});

test('座位动作只做局部刷新，不整页重绘（挪位/发消息不再闪整屏）', () => {
  const src = readFileSync(new URL('../src/seats.js', import.meta.url), 'utf8');
  /* 页面上必须留出可被局部替换的锚点，否则只能靠整页重绘 */
  assert.ok(src.includes('id="seat-heading"'), '页头需要 #seat-heading 锚点');
  assert.ok(src.includes('id="seat-side"'), '侧栏需要 #seat-side 锚点');
  assert.ok(/function seatSyncTargets\(force\)/.test(src), '需要 seatSyncTargets 做局部刷新');

  /* SEATS_ACTIONS 里除「地图编辑」那几个结构性动作外，不得再调用全局 render() */
  const start = src.indexOf('const SEATS_ACTIONS = {');
  assert.ok(start > 0, '找不到 SEATS_ACTIONS');
  const body = src.slice(start);
  const marker = body.indexOf('/* ── 地图编辑 ── */');
  assert.ok(marker > 0, '找不到地图编辑分界注释');
  /* 先剥掉注释再扫，避免把注释里提到的 render() 当成调用 */
  const stripComments = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
  const runtimeActions = stripComments(body.slice(0, marker));
  const offenders = [...runtimeActions.matchAll(/(?<![\w.])render\(\)/g)];
  assert.equal(offenders.length, 0,
    `这些运行时动作仍在整页重绘：${runtimeActions.slice(Math.max(0, (offenders[0]?.index ?? 0) - 160), (offenders[0]?.index ?? 0) + 40)}`);
  /* 关键动作必须走局部刷新 */
  for (const act of ['seat-chat-send', 'seat-signout', 'seat-chat-more', 'seat-chat-del']) {
    const i = runtimeActions.indexOf(`'${act}':`);
    assert.ok(i > 0, `找不到动作 ${act}`);
    const seg = runtimeActions.slice(i, i + 700);
    assert.ok(seg.includes('seatSync'), `${act} 应调用 seatSyncTargets/seatSyncSide`);
  }
  /* 聊天输入框不能在刷新路径里被重建 */
  const syncStart = src.indexOf('function seatSyncTargets(force)');
  const sync = src.slice(syncStart, src.indexOf('\n}', syncStart));
  assert.ok(!/seat-chat-input/.test(sync), 'seatSyncTargets 不得触碰聊天输入框');
});

test('页面自己保持状态：没有刷新按钮，轮询只比签名、没变就不碰 DOM', () => {
  const { run, context } = seatsSetup();
  const src = readFileSync(new URL('../src/seats.js', import.meta.url), 'utf8');
  run("view='seats'");
  const out = run('renderView()');

  /* 「应该有刷新按键」是用户明确否掉的：状态本就自动保持，按钮只会让人以为要手动按 */
  assert.ok(!out.includes('seat-refresh'), '页头不得再有刷新按钮');
  assert.equal(run("typeof SEATS_ACTIONS['seat-refresh']"), 'undefined', '不应再保留 seat-refresh 动作');
  assert.ok(!/icon\('refresh'\)/.test(src), '座位页不应再用刷新图标');
  /* 但标题与文案是真实内容，别把「实验室座位」一起误删 */
  assert.ok(out.includes('实验室座位'));

  /* 轮询必须是轻量接口 + 页面不可见时暂停，不能再整份 workspace 重拉 */
  const poll = src.slice(src.indexOf('function seatStartPoll()'), src.indexOf('function seatHeadingHTML'));
  assert.ok(poll.includes("API.request('/seats/layout')"), '轮询应打轻量接口 /seats/layout');
  assert.ok(!/API\.load\(\)/.test(poll), '轮询不得再整份拉 workspace（那正是「隔一会闪一下」的源头之一）');
  assert.ok(/document\.hidden/.test(poll), '页面不可见时应跳过轮询');
  assert.ok(/visibilitychange/.test(src), '切回标签页时应立刻补一次');

  /* 数据没变 → seatSyncTargets 返回 false，且一次 DOM 都不碰 */
  run('seatSyncTargets(true)');
  let queried = 0;
  const realQS = context.document.querySelector;
  context.document.querySelector = (sel) => { queried += 1; return realQS(sel); };
  assert.equal(run('seatSyncTargets()'), false, '签名没变时应短路返回 false');
  assert.equal(queried, 0, '签名没变时不应查询任何 DOM 节点（否则就是在重画）');
  /* 只在真的变了（这里改在席位置）时才刷新，且只重画地图区那几块 */
  run("db.seatPresence=[{memberId:'m3',row:1,col:1}]");
  assert.equal(run('seatSyncTargets()'), true, '数据变了应刷新');
  assert.ok(queried > 0, '数据变了才该碰 DOM');
  context.document.querySelector = realQS;

  /* 别人只是说话时，地图区不该被重画（两块各自独立脏检查） */
  run("_seatChatLoaded=true;_seatChat=[]");
  run('seatSyncTargets()');
  const before = run('_seatRoomSig');
  run("_seatChat=[{id:'SC-9',memberId:'m3',text:'刚回来',created:new Date().toISOString()}]");
  assert.equal(run('seatSyncTargets()'), true, '新消息应刷新');
  assert.equal(run('_seatRoomSig'), before, '只是聊天变化时地图区签名不该变（也就不会重画地图）');

  /* 全站那支 30 秒「状态变了就重建 #content」的轮询，在座位页必须闭嘴 ——
     它会把整张地图连同聊天列表整体重建一次，那就是「隔一会儿自动刷新一下」。 */
  const features = readFileSync(new URL('../src/features.js', import.meta.url), 'utf8');
  const i = features.indexOf('let lastStatusSignature');
  assert.ok(i > 0, '找不到全站状态轮询');
  const tick = features.slice(i, features.indexOf('lastStatusSignature = signature'));
  assert.ok(/if \(view === 'seats'\) return;/.test(tick), '状态轮询应显式跳过座位页');
  assert.ok(!/content\.innerHTML/.test(tick), '跳过必须发生在重建 #content 之前');
});

test('挪位是乐观更新：本地先动、动画不等服务器往返', async () => {
  const { run, context } = seatsSetup();
  run("db.permissions=['page:seats','action:seats.move']");
  /* 当前登录身份是 m1，把他也放进席，并挑一个空格 (1,6) 作为目标 */
  run("db.seatPresence=[{memberId:'m1',row:3,col:2},{memberId:'m5',row:1,col:5}]");
  let resolveFetch;
  context.fetch = () => new Promise((r) => { resolveFetch = r; });
  assert.equal(run("seatPosOf('m1')"), '3-2');
  assert.equal(run("seatIsWalkable(seatCellKind(seatLayout(),'1-6'))"), true, '(1,6) 应可站');
  /* 不 await：只跑同步段，验证「还没等服务端就先动」 */
  const pending = run('seatMove(1,6)');
  assert.equal(run("seatPosOf('m1')"), '1-6', '应立刻本地移位');
  assert.equal(run("db.seatPresence.find(p=>p.memberId==='m1').row"), 1);
  assert.equal(run('_seatWalking'), true, '应立刻起走动动画');
  assert.equal(run("document.querySelector('#seat-walk')") !== null, true);
  /* 服务端拒绝 → 回到真值并提示 */
  resolveFetch({ ok: false, status: 409, json: async () => ({ message: '那一格有人，换个空位吧' }) });
  let err = '';
  try { await pending; } catch (e) { err = e.message; }
  assert.ok(err === '' || /有人/.test(err), `拒绝时应能拿到提示，实际：${err}`);
});

test('座位模块已接入脚本与渲染表，且定义阶段不报错', () => {
  const find = (name) => scripts.findIndex((p) => p.startsWith('/src/' + name));
  assert.ok(scripts.some((p) => p.startsWith('/src/seats.js')), 'index.html 应引入 seats.js');
  assert.ok(find('seats.js') < find('features.js'), 'seats.js 必须在 features.js 之前（动作表要先注册）');
  assert.ok(find('seats.js') < find('app.js'), 'seats.js 必须在 app.js 之前（渲染器要先存在）');
  assert.ok(find('ui.js') < find('seats.js'), 'ui.js 必须在 seats.js 之前');
  assert.ok(find('core.js') < find('seats.js'), 'core.js 必须在 seats.js 之前');
  /* 改动过的文件都必须带 ?v= 强刷版本号，否则浏览器缓存会让菜单点出「页面不存在」 */
  for (const name of ['core.js', 'checkins.js', 'features.js', 'app.js', 'seats.js']) {
    const path = scripts.find((p) => p.startsWith('/src/' + name));
    assert.ok(/\?v=\d+$/.test(path), `${name} 缺少 ?v= 版本参数（当前 ${path}）`);
  }
  const { run } = seatsSetup();
  assert.equal(run('Object.hasOwn(PAGE_RENDERERS,"seats")'), true);
  assert.equal(run('typeof window.seatsPage'), 'function');
  assert.equal(run('typeof window.SEATS_ACTIONS'), 'object');
});

test('俯视图渲染出全部格子，工位与静态家具各就各位', () => {
  const { run } = seatsSetup();
  run("view='seats'");
  const out = run('renderView()');
  assert.ok(out.length > 500);
  const cells = [...out.matchAll(/grid-column:(\d+);grid-row:(\d+)/g)].map((m) => `${m[1]},${m[2]}`);
  assert.equal(cells.length, 11 * 13);
  assert.equal(new Set(cells).size, 11 * 13);
  const workstations = [...out.matchAll(/class="seat-cell k-w/g)].length;
  assert.equal(workstations, 16);
  const floor = [...out.matchAll(/class="seat-cell k-f/g)].length;
  const storage = [...out.matchAll(/class="seat-cell k-s/g)].length;
  const bench = [...out.matchAll(/class="seat-cell k-t/g)].length;
  assert.equal(storage, 8);
  assert.equal(bench, 5);
  assert.equal(workstations + floor + storage + bench + 44 + 1, 143);
});

test('在席与姿态：工位坐姿含桌、通道站姿无桌，且共用一个头', () => {
  const { run } = seatsSetup();
  const at = run("seatCellHTML(seatLayout(),3,2,'w')");
  assert.ok(at.includes('B-01'), '工位应显示座位号');
  assert.ok(at.includes('在跑电机闭环') === false, '格子上不直接渲染状态文字');
  assert.ok(at.includes('y="24" width="56"'), '工位场景必须含桌子');
  assert.ok(at.includes('cy="7.6" r="7.2"'), '工位有头部');
  assert.ok(at.includes('cy="27.4"'), '坐姿有搭在桌上的双手');

  const walk = run("seatCellHTML(seatLayout(),1,5,'.')");
  assert.ok(!walk.includes('y="24" width="56"'), '通道格不应有桌子');
  assert.ok(walk.includes('cy="42.4"'), '通道格应为站姿（落地阴影）');

  const stand = run("seatStandSVG(seatCharacterOf('m3'))");
  const seat = run("seatSceneSVG(seatCharacterOf('m3'))");
  assert.equal((stand.match(/cx="29" cy="7\.6" r="7\.2"/g) || []).length, 1);
  assert.equal((seat.match(/cx="29" cy="7\.6" r="7\.2"/g) || []).length, 1);
});

test('气泡按人挂在自己的格子上，过期自动不再渲染', () => {
  const { run } = seatsSetup();
  assert.ok(run("seatCellHTML(seatLayout(),3,2,'w')").includes('去借万用表'));
  run("db.seatBubbles=[{memberId:'m3',text:'过期的',expiresAt:new Date(Date.now()-1000).toISOString()}]");
  assert.ok(!run("seatCellHTML(seatLayout(),3,2,'w')").includes('过期的'));
});

test('权限门控：无 seats.manage 不出现编辑地图，无 page:seats 无法进入', () => {
  const { run } = seatsSetup();
  run("view='seats'");
  run("db.permissions=['page:seats','action:seats.move','action:seats.status','action:seats.bubble','action:seats.chat']");
  const memberView = run('renderView()');
  assert.ok(!memberView.includes('seat-map-enter'), '普通成员不应看到「编辑地图」');
  assert.ok(memberView.includes('seat-character'), '普通成员应能编辑形象');

  run("db.permissions=['page:seats','action:seats.manage','action:seats.chat']");
  assert.ok(run('renderView()').includes('seat-map-enter'), '管理角色应看到「编辑地图」');

  /* 路由守卫：没有 page:seats 时 go() 不改视图 */
  run("db.permissions=[];view='dashboard'");
  run("NAV=[{id:'seats',label:'座位',icon:'pin',permission:'page:seats',param:''}]");
  run("go('seats')");
  assert.equal(run('view'), 'dashboard');
});

test('聊天头像与名字都指向成员主页（member 详情子页）', () => {
  const { run } = seatsSetup();
  run("_seatChat=[{id:'SC-001',memberId:'m3',text:'示波器我占一会儿',created:new Date().toISOString()}]");
  run('_seatChatLoaded=true');
  const list = run('seatChatListHTML()');
  assert.ok(list.includes('data-action="member-detail" data-id="m3"'), '头像应可点进成员主页');
  assert.ok(list.includes('seat-mav'));
  run("NAV=[{id:'member',param:'m',permission:'page:member.detail'}]");
  run("PAGE_RENDERERS.member=()=>'ok'");
  run("go('member/m3')");
  assert.equal(run('routeParam'), 'm3');
  assert.equal(run('view'), 'member');
});

test('聊天正文全部转义，头像不渲染任何用户提供的 SVG', () => {
  const { run } = seatsSetup();
  run("_seatChat=[{id:'SC-002',memberId:'m3',text:'<img src=x onerror=alert(1)>',created:new Date().toISOString()}]");
  run('_seatChatLoaded=true');
  assert.equal(run('_seatChat.length'), 1, '聊天缓存应为 1 条');
  assert.equal(run('_seatChatLoaded'), true, '应已标记载入完成');
  const list = run('seatChatListHTML()');
  assert.ok(!list.includes('<img'), '不得插入可执行标签');
  assert.ok(!list.includes('onerror=alert(1)>'), '标签边界必须被转义');
  assert.ok(list.includes('&lt;img src=x onerror=alert(1)&gt;'), '应整体转义为实体');
  /* 形象部件只能来自白名单，后端也会拒；前端不拼接用户字符串 */
  run("db.seatCharacters=[{memberId:'m3',parts:{skin:'<svg onload=alert(1)>',hairStyle:'flat'}}]");
  const svg = run("seatSceneSVG(seatCharacterOf('m3'))");
  assert.ok(!svg.includes('onload'), '非法部件值不得进入 SVG');
});

test('地图编辑器：改尺寸、涂改、编号重复校验、保存负载形状', () => {
  const { run } = seatsSetup();
  run('_seatEdit=seatEditDraft(seatLayout())');
  assert.equal(run('_seatEdit.rows'), 11);
  assert.equal(run('_seatEdit.grid.length'), 11);
  assert.equal(run('_seatEdit.grid[3].join("")'), '#.ww...ww...#');

  run("_seatBrush='s';SEATS_ACTIONS['seat-paint']('1-5')");
  assert.equal(run('_seatEdit.grid[1][5]'), 's', '涂改应写入草稿');
  run("_seatBrush='w';SEATS_ACTIONS['seat-paint']('1-5')");
  assert.equal(run('_seatEdit.grid[1][5]'), 'w', '改回工位');
  assert.equal(run('_seatEdit.grid[1][5]'), 'w');

  run("_seatEdit.labels['1-5']='B-99';_seatEdit.owners['1-5']='m3'");
  run("_seatBrush='s';SEATS_ACTIONS['seat-paint']('1-5')");
  assert.equal(run('_seatEdit.labels["1-5"]'), undefined, '涂成非工位应清掉编号');
  assert.equal(run('_seatEdit.owners["1-5"]'), undefined, '涂成非工位应清掉归属');

  /* 尺寸增减 */
  const before = run('_seatEdit.rows');
  run("SEATS_ACTIONS['seat-size']('row+')");
  assert.equal(run('_seatEdit.rows'), before + 1);
  run("SEATS_ACTIONS['seat-size']('row-')");
  assert.equal(run('_seatEdit.rows'), before);
  run("SEATS_ACTIONS['seat-size']('col-')");
  assert.equal(run('_seatEdit.cols'), 12);
  assert.ok(run('_seatEdit.grid').every((row) => row.length === 12), '每行都应同步缩列');

  /* 保存负载：grid 必须是字符串数组 */
  const payload = run(`JSON.stringify({grid:_seatEdit.grid.map(r=>r.join('')),labels:_seatEdit.labels,owners:_seatEdit.owners})`);
  const parsed = JSON.parse(payload);
  assert.ok(Array.isArray(parsed.grid) && parsed.grid.every((r) => typeof r === 'string'));
  assert.equal(parsed.grid.length, run('_seatEdit.rows'));
});

test('挪位：目标位置解析与可站立判定', () => {
  const { run } = seatsSetup();
  assert.equal(run("seatIsWalkable('w')"), true);
  assert.equal(run("seatIsWalkable('.')"), true);
  assert.equal(run("seatIsWalkable('#')"), false);
  assert.equal(run("seatIsWalkable('s')"), false);
  assert.equal(run("seatIsWalkable('t')"), false);
  assert.equal(run("seatIsWalkable('d')"), false);
  assert.equal(run("seatPosOf('m3')"), '3-2');
  assert.equal(run("seatCellName(3,2)"), 'B-01');
  assert.equal(run("seatCellName(1,5)"), '通道空地');
  /* 缩放基准尺寸与 CSS 里的格子尺寸同源 */
  const natural = JSON.parse(run('JSON.stringify(seatRoomNatural(seatLayout()))'));
  assert.equal(natural.w, 13 * 64 + 12 * 3 + 24 + 2);
  assert.equal(natural.h, 11 * 64 + 10 * 3 + 24 + 2);
});

test('形象部件全组合都能生成合法 SVG（白名单 × 两种姿态）', () => {
  const { run } = seatsSetup();
  const book = JSON.parse(run('JSON.stringify(SEAT_CHARACTER_BOOK)'));
  const keys = Object.keys(book);
  let combos = 0;
  const walk = (i, parts) => {
    if (i === keys.length) {
      combos += 1;
      run(`_t=${JSON.stringify(parts)}`);
      for (const expr of ['seatSceneSVG(_t)', 'seatStandSVG(_t)', 'seatSceneSVG(_t,"B-01","21 0 16 15")']) {
        const svg = run(expr);
        assert.ok(svg.startsWith('<svg viewBox='), expr);
        assert.ok(svg.endsWith('</svg>'), expr);
        assert.ok(!/undefined|NaN/.test(svg), expr);
        assert.equal((svg.match(/</g) || []).length, (svg.match(/>/g) || []).length, expr);
      }
      return;
    }
    for (const v of book[keys[i]]) walk(i + 1, { ...parts, [keys[i]]: v });
  };
  walk(0, {});
  assert.equal(combos, 4 * 4 * 4 * 5 * 4 * 4 * 2);
});