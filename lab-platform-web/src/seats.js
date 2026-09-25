'use strict';
/* ============================================================================
   可视化座位（实验室俯视图）
   - 小人 = 今日已打卡且未签退（后端派生，本模块只消费 seatPresence）
   - 位置真值来自 workspace 快照 db.seatPresence，挪位走 POST /seats/move
   - 形象只接受白名单部件，前端拼 SVG（不渲染任何用户提供的 SVG/HTML）
   - 聊天正文不进 workspace 快照，走 GET /seats/chat 独立分页
   ========================================================================== */

const SEAT_STATUSES = [
  { key: 'work', label: '在工位', color: '#18a778' },
  { key: 'debug', label: '调试中', color: '#243e70' },
  { key: 'meeting', label: '开会', color: '#7b5ea7' },
  { key: 'rest', label: '休息', color: '#e49739' },
  { key: 'out', label: '实验室外', color: '#7a7a78' },
  { key: 'custom', label: '自定义', color: '#2f7f8f' },
];
const SEAT_STATUS_MAP = Object.fromEntries(SEAT_STATUSES.map((s) => [s.key, s]));

/* 与后端 apps/seats/api.py 的 CHARACTER_BOOK 保持同源；后端拒绝白名单外的取值 */
const SEAT_CHARACTER_BOOK = {
  skin: ['#f6d0ac', '#eec096', '#d8a377', '#c08a5e'],
  hairStyle: ['flat', 'cap', 'bob', 'spike'],
  hairColor: ['#3a3f46', '#6a5a41', '#2e3648', '#1b1d21'],
  top: ['#243E70', '#6f7c8c', '#3e6b5a', '#96603a', '#6a4a7f'],
  chair: ['#9aa0a8', '#6d747d', '#b9a68a', '#c3c7cd'],
  prop: ['none', 'pc', 'wrench', 'book'],
  glasses: [false, true],
};
const SEAT_PART_LABEL = { skin: '肤色', hairStyle: '发型', hairColor: '发色', top: '上衣',
  chair: '椅背', prop: '桌上物品', glasses: '眼镜' };
const SEAT_HAIR_LABEL = { flat: '短发', cap: '工帽', bob: '齐耳', spike: '寸头' };
const SEAT_PROP_LABEL = { none: '无', pc: '笔记本', wrench: '焊枪', book: '技术书' };
const SEAT_DEFAULT_PARTS = { skin: '#f6d0ac', hairStyle: 'flat', hairColor: '#3a3f46',
  top: '#243E70', chair: '#9aa0a8', prop: 'none', glasses: false };

const SEAT_CELL_PX = 64, SEAT_GAP = 3, SEAT_PAD = 12, SEAT_BORDER = 1;
/* 构建标记：显示在页头，用来一眼确认浏览器跑的是哪一版（改代码时与 index.html 的 ?v= 一起加）
   看不到这里的数字变大，就说明浏览器还在用旧的 index.html。 */
const SEAT_BUILD = 10;
const SEAT_WALK_MS = 300;
/* 轮询间隔：只拉座位状态那一小份数据，比整份 workspace 轻得多，所以可以比原来更勤；
   真正决定「会不会闪」的不是频率而是签名比对 —— 数据没变就一个 DOM 都不碰。 */
const SEAT_POLL_MS = 15000;
const SEAT_BRUSHES = [
  ['w', '工位'], ['.', '通道空地'], ['s', '储物柜'], ['t', '测试台'], ['d', '门口'],
  ['#', '墙体'], ['label', '编号 / 归属'],
];
const SEAT_KIND_CLASS = { w: 'k-w', '.': 'k-f', s: 'k-s', t: 'k-t', d: 'k-d', '#': 'k-x' };
const SEAT_KIND_TEXT = { w: '', '.': '', s: '柜', t: '台', d: '门', '#': '' };

let _seatChat = [], _seatChatHasMore = false, _seatChatLoaded = false;
let _seatWalking = false, _seatEdit = null, _seatPainting = false, _seatTimer = null;
let _seatBrush = 'w';
/* 上一次同步时的签名：地图区与消息列表各存一份，各自独立脏检查 ——
   别人只是在聊天，就只重画消息列表，地图连碰都不碰。 */
let _seatRoomSig = '', _seatChatSig = '';

/* ────────────────────────── 小人与场景 SVG ────────────────────────── */

function seatHeadSVG(p) {
  const ink = '#20242c', sk = p.skin, hc = p.hairColor;
  let g = `<circle cx="29" cy="7.6" r="7.2" fill="${sk}"/>`;
  if (p.hairStyle === 'flat')
    g += `<path d="M21.8 7.8c0-4.1 3.2-6.7 7.2-6.7s7.2 2.6 7.2 6.7c-2.3-2.1-4.7-3-7.2-3s-4.9.9-7.2 3z" fill="${hc}"/>`;
  if (p.hairStyle === 'bob') {
    g += `<path d="M21.8 7.8c0-4.1 3.2-6.7 7.2-6.7s7.2 2.6 7.2 6.7c-2.3-2.1-4.7-3-7.2-3s-4.9.9-7.2 3z" fill="${hc}"/>`;
    g += `<rect x="21.1" y="6.6" width="2.5" height="6.6" rx="1.25" fill="${hc}"/>`;
    g += `<rect x="34.4" y="6.6" width="2.5" height="6.6" rx="1.25" fill="${hc}"/>`;
  }
  if (p.hairStyle === 'cap') {
    g += `<path d="M21.8 7.6c0-4 3.2-6.6 7.2-6.6s7.2 2.6 7.2 6.6z" fill="${hc}"/>`;
    g += `<rect x="19.6" y="6.6" width="18.8" height="2.6" rx="1.3" fill="${hc}"/>`;
  }
  if (p.hairStyle === 'spike')
    g += `<path d="M22 8.2 24.2 1.2 26.7 6 29 0.2 31.3 6 33.8 1.2 36 8.2z" fill="${hc}"/>`;
  g += `<circle cx="26.2" cy="8.4" r="1.35" fill="${ink}"/><circle cx="31.8" cy="8.4" r="1.35" fill="${ink}"/>`;
  g += `<path d="M27.4 11.6q1.6 1.3 3.2 0" stroke="${ink}" stroke-width="1.1" fill="none" stroke-linecap="round"/>`;
  if (p.glasses)
    g += `<circle cx="26.2" cy="8.4" r="2.8" fill="none" stroke="${ink}" stroke-width="1"/>`
      + `<circle cx="31.8" cy="8.4" r="2.8" fill="none" stroke="${ink}" stroke-width="1"/>`
      + `<path d="M29 8.4h.4M23.4 7.6 22 7.1M34.6 7.6 36 7.1" stroke="${ink}" stroke-width="1" stroke-linecap="round"/>`;
  return g;
}

/* 坐姿：桌子常驻底部，小人坐在桌后，双手搭在桌面上（腿被桌沿遮挡）。
   crop 用于聊天头像这类局部特写（只取头部）。 */
function seatSceneSVG(p, label, crop) {
  /* sk/tp 必须提到函数作用域：桌上物品与双手在另一个 if 块里也要用 */
  const sk = p ? p.skin : '', tp = p ? p.top : '';
  let g = '';
  if (p) {
    g += `<rect x="16.5" y="8" width="25" height="16" rx="8" fill="${p.chair}" opacity=".6"/>`;
    g += `<path d="M20.6 16.5Q17 21 16.2 26.4" stroke="${tp}" stroke-width="4.4" stroke-linecap="round" fill="none"/>`;
    g += `<path d="M37.4 16.5Q41 21 41.8 26.4" stroke="${tp}" stroke-width="4.4" stroke-linecap="round" fill="none"/>`;
    g += `<path d="M19.5 18.6q0-5.6 5.6-5.6h7.8q5.6 0 5.6 5.6V24H19.5z" fill="${tp}"/>`;
    g += seatHeadSVG(p);
  } else {
    /* 空工位：留一把空椅子，别让人看成一块空白方块 */
    g += `<rect x="17.5" y="9" width="23" height="14" rx="7" fill="#d9d6cd" opacity=".75"/>`;
    g += `<rect x="18.8" y="10.4" width="20.4" height="11.2" rx="5.6" fill="#fbfaf7" opacity=".85"/>`;
  }
  g += `<rect x="1" y="24" width="56" height="20" rx="4" fill="#e6dfcd" stroke="#cfc3a6" stroke-width="1"/>`;
  g += `<path d="M2.6 24.7h52.8" stroke="#f5f1e5" stroke-width="1.3" stroke-linecap="round"/>`;
  g += `<rect x="1" y="37.6" width="56" height="6.4" rx="4" fill="#d5ccb6"/>`;
  if (label)
    g += `<text x="4.8" y="35" font-size="7.5" font-family="inherit" fill="#9c9384">${esc(label)}</text>`;
  if (p) {
    if (p.prop === 'pc')
      g += `<rect x="23.4" y="25.8" width="11.2" height="8" rx="1.6" fill="#dfe2e6" stroke="#9aa0a8" stroke-width=".9"/>`
        + `<rect x="25" y="27.2" width="8" height="5.2" rx=".7" fill="#5d6b82"/>`;
    if (p.prop === 'book')
      g += `<rect x="23.6" y="26.2" width="10.8" height="8.4" rx="1.6" fill="#d99a3e" stroke="#a8781f" stroke-width=".9"/>`
        + `<path d="M29 26.2v8.4" stroke="#a8781f" stroke-width=".8"/>`;
    if (p.prop === 'wrench') {
      g += `<path d="M24 33.6 33.4 27.4" stroke="#8b8f96" stroke-width="2.6" stroke-linecap="round"/>`;
      g += `<circle cx="34.6" cy="26.8" r="2.6" fill="none" stroke="#c07a2f" stroke-width="2"/>`;
    }
    g += `<circle cx="16" cy="27.4" r="2.6" fill="${sk}"/><circle cx="42" cy="27.4" r="2.6" fill="${sk}"/>`;
  } else {
    /* 空工位桌面的标配：显示器 + 键盘，让空位也一眼看出是工位 */
    g += `<rect x="23.4" y="25.8" width="11.2" height="8" rx="1.6" fill="#e4e7ea" stroke="#a6acb4" stroke-width=".9"/>`
      + `<rect x="25" y="27.2" width="8" height="5.2" rx=".7" fill="#8d99ad"/>`;
    g += `<rect x="20.4" y="35.2" width="17.2" height="2.4" rx="1.2" fill="#cec5b1"/>`;
  }
  return `<svg viewBox="${crop || '0 0 58 44'}" aria-hidden="true">${g}</svg>`;
}

/* 站姿：走到通道空地时用，与坐姿共用同一个头，站起来还是同一个人 */
function seatStandSVG(p) {
  const sk = p.skin, tp = p.top;
  let g = `<ellipse cx="29" cy="42.4" rx="10.5" ry="2.2" fill="#1b1d21" opacity=".1"/>`;
  g += `<rect x="24.2" y="28.4" width="4.6" height="11.6" rx="2.3" fill="#5a5e66"/>`;
  g += `<rect x="29.2" y="28.4" width="4.6" height="11.6" rx="2.3" fill="#5a5e66"/>`;
  g += `<rect x="22.9" y="39" width="7.2" height="3.6" rx="1.8" fill="#2b2f37"/>`;
  g += `<rect x="27.9" y="39" width="7.2" height="3.6" rx="1.8" fill="#2b2f37"/>`;
  g += `<path d="M21.6 21.4q0-4.8 4.8-4.8h5.2q4.8 0 4.8 4.8v7.6q0 2.8-2.8 2.8h-9.2q-2.8 0-2.8-2.8z" fill="${tp}"/>`;
  g += `<rect x="18.2" y="18.8" width="4.4" height="12.6" rx="2.2" fill="${tp}"/>`;
  g += `<rect x="35.4" y="18.8" width="4.4" height="12.6" rx="2.2" fill="${tp}"/>`;
  g += `<circle cx="20.4" cy="32.6" r="2.2" fill="${sk}"/><circle cx="37.6" cy="32.6" r="2.2" fill="${sk}"/>`;
  g += `<rect x="27" y="14.2" width="4" height="3.2" rx="1.6" fill="${sk}"/>`;
  g += seatHeadSVG(p);
  return `<svg viewBox="0 0 58 44" aria-hidden="true">${g}</svg>`;
}

/* ────────────────────────── 快照读取 ────────────────────────── */

function seatLayout() { return db?.seatLayout || null; }

function seatMemberName(mid) {
  const m = (db?.members || []).find((x) => x.id === mid);
  return m ? m.name : mid;
}
function seatMemberIndex(mid) { return Math.max(0, (db?.members || []).findIndex((m) => m.id === mid)); }

function seatCharacterOf(mid) {
  /* 没设过形象的人按成员序号取一组稳定搭配，保证同图里各不相同 */
  const i = seatMemberIndex(mid);
  const fallback = { ...SEAT_DEFAULT_PARTS,
    skin: SEAT_CHARACTER_BOOK.skin[i % 4],
    hairStyle: SEAT_CHARACTER_BOOK.hairStyle[i % 4],
    hairColor: SEAT_CHARACTER_BOOK.hairColor[(i + 1) % 4],
    top: SEAT_CHARACTER_BOOK.top[(i * 2) % 5],
    chair: SEAT_CHARACTER_BOOK.chair[i % 4] };

  const saved = (db?.seatCharacters || []).find((c) => c.memberId === mid);
  if (!saved || !saved.parts) return fallback;
  /* 逐槽位再按白名单过滤一遍：部件值会被拼进 SVG 属性，
     即使服务端下发了脏值也不能落进标记里（后端也会拒，这里是第二道防线）。 */
  const out = { ...fallback };
  for (const slot of Object.keys(SEAT_CHARACTER_BOOK)) {
    const value = saved.parts[slot];
    if (value === undefined || value === null) continue;
    if (SEAT_CHARACTER_BOOK[slot].includes(value)) out[slot] = value;
  }
  return out;
}

function seatStatusOf(mid) {
  const s = (db?.seatStatuses || []).find((x) => x.memberId === mid);
  const key = s?.statusKey || 'work';
  return { key, text: s?.text || (SEAT_STATUS_MAP[key] || SEAT_STATUSES[0]).label };
}
function seatStatusColor(key) { return (SEAT_STATUS_MAP[key] || SEAT_STATUSES[0]).color; }

/* 在席位置：'m3' → '3-2' */
function seatPosMap() {
  const out = {};
  for (const p of db?.seatPresence || []) out[p.memberId] = `${p.row}-${p.col}`;
  return out;
}
function seatPosOf(mid) { return seatPosMap()[mid] || ''; }

/* 未过期的气泡（服务端已过滤，前端按 expiresAt 兜一层，避免轮询间隙残留） */
function seatBubbles() {
  const now = serverNow().getTime();
  const out = {};
  for (const b of db?.seatBubbles || []) {
    if (!b.expiresAt || Date.parse(b.expiresAt) > now) out[b.memberId] = b.text;
  }
  return out;
}

function seatCellKind(lo, key) {
  const [r, c] = key.split('-').map(Number);
  const row = (lo.grid || [])[r];
  return row ? row[c] || '.' : '.';
}
function seatIsWalkable(kind) { return kind === '.' || kind === 'w'; }

/* 我是否还在席：自己的小人还在图上就是（presence 由「今日打卡未签退」派生）。
   万一在席却没分到格子（地图被改小），退回查今天的打卡记录。 */
function seatAmOnDuty() {
  const meId = me()?.id;
  if (!meId) return false;
  if (seatPosMap()[meId]) return true;
  const asOf = serverNow().toDateString();
  return (db?.checkins || []).some(
    (c) => c.memberId === meId && c.onDuty === true && new Date(c.created).toDateString() === asOf);
}

/* ────────────────────────── 俯视图渲染 ────────────────────────── */

function seatRoomNatural(lo) {
  const w = lo.cols * SEAT_CELL_PX + (lo.cols - 1) * SEAT_GAP + SEAT_PAD * 2 + SEAT_BORDER * 2;
  const h = lo.rows * SEAT_CELL_PX + (lo.rows - 1) * SEAT_GAP + SEAT_PAD * 2 + SEAT_BORDER * 2;
  return { w, h };
}

function seatCellHTML(lo, r, c, kind) {
  const key = `${r}-${c}`;
  const grid = `grid-column:${c + 1};grid-row:${r + 1}`;
  const pos = seatPosMap();
  const bubbles = seatBubbles();
  const mid = Object.keys(pos).find((k) => pos[k] === key);
  const meId = me()?.id;
  const isMe = mid && mid === meId;
  const person = mid && !(isMe && _seatWalking) ? mid : null;
  const st = person ? seatStatusColor(seatStatusOf(person).key) : 'transparent';
  const canGo = seatIsWalkable(kind) && !mid;

  if (kind === 'w') {
    const cls = ['seat-cell', 'k-w'];
    if (mid) cls.push('occ');
    if (isMe) cls.push('mine'); else if (mid) cls.push('taken');
    if (canGo) cls.push('free');
    return `<div class="${cls.join(' ')}" style="${grid};--seat-st:${st}" data-action="seat-cell" data-id="${key}">
      ${mid ? '<span class="seat-ring"></span>' : ''}
      <div class="seat-scene">${seatSceneSVG(person ? seatCharacterOf(person) : null, lo.labels?.[key])}</div>
      ${person ? `<span class="seat-name${isMe ? ' mine' : ''}"><i style="background:${st}"></i><b>${esc(seatMemberName(person))}</b></span>
        ${bubbles[person] ? `<span class="seat-bubble" data-action="seat-bubble-close" data-id="${person}">${esc(bubbles[person])}</span>` : ''}`
        : '<span class="seat-desk-ph"></span>'}
    </div>`;
  }
  /* 通道空地：可以站人 */
  const cls = ['seat-cell', 'k-f'];
  if (mid) cls.push('occ');
  if (isMe) cls.push('mine');
  if (canGo) cls.push('free');
  return `<div class="${cls.join(' ')}" style="${grid};--seat-st:${st}" data-action="seat-cell" data-id="${key}">
    ${mid ? '<span class="seat-ring"></span>' : ''}
    ${person ? `<div class="seat-scene">${seatStandSVG(seatCharacterOf(person))}</div>
      <span class="seat-name${isMe ? ' mine' : ''}"><i style="background:${st}"></i><b>${esc(seatMemberName(person))}</b></span>
      ${bubbles[person] ? `<span class="seat-bubble" data-action="seat-bubble-close" data-id="${person}">${esc(bubbles[person])}</span>` : ''}` : ''}
  </div>`;
}

function seatStaticCellHTML(r, c, kind) {
  const grid = `grid-column:${c + 1};grid-row:${r + 1}`;
  if (kind === '#') return `<div class="seat-cell k-x" style="${grid}"></div>`;
  if (kind === 's') return `<div class="seat-cell k-s" style="${grid}"></div>`;
  if (kind === 't') return `<div class="seat-cell k-t" style="${grid}"><span>测试台</span></div>`;
  if (kind === 'd') return `<div class="seat-cell k-d" style="${grid}"><span>入口</span></div>`;
  return '';
}

function seatCellsHTML(lo) {
  let html = '';
  for (let r = 0; r < lo.rows; r += 1) {
    const row = (lo.grid || [])[r] || '';
    for (let c = 0; c < lo.cols; c += 1) {
      const kind = row[c] || '.';
      html += kind === 'w' || kind === '.'
        ? seatCellHTML(lo, r, c, kind)
        : seatStaticCellHTML(r, c, kind);
    }
  }
  return html;
}

function seatLegendHTML(lo) {
  const pos = seatPosMap();
  const onDuty = Object.keys(pos).length;
  const seats = (lo.grid || []).join('').split('').filter((k) => k === 'w').length;
  return `<div class="seat-legend">
    <span class="seat-pill"><i class="seat-dot on"></i>在席 <b>${onDuty}</b> / ${seats}</span>
    ${SEAT_STATUSES.map((s) => `<span class="seat-pill"><i class="seat-dot" style="background:${s.color}"></i>${s.label}</span>`).join('')}
    <span class="seat-hint-inline">点空位走过去 · 点小人看他状态</span>
  </div>`;
}

/* ────────────────────────── 实验室大厅 ────────────────────────── */

function seatChatListHTML() {
  if (!_seatChatLoaded) return '<div class="seat-chat-hint">正在载入…</div>';
  if (!_seatChat.length) return '<div class="seat-chat-hint">还没有人说话，来第一句吧</div>';
  const meId = me()?.id;
  return (_seatChatHasMore ? '<button class="seat-more" data-action="seat-chat-more">加载更早的消息</button>' : '')
    + _seatChat.map((m) => {
      const who = (db?.members || []).find((x) => x.id === m.memberId);
      const mine = m.memberId === meId;
      /* 头像即入口：点进成员主页（后端 nav 里 member 是带参数的详情子页） */
      return `<div class="seat-msg${mine ? ' mine' : ''}">
        <button class="seat-mav" data-action="member-detail" data-id="${esc(m.memberId)}"
          title="查看 ${esc(seatMemberName(m.memberId))} 的主页" aria-label="查看${esc(seatMemberName(m.memberId))}的主页">
          ${seatSceneSVG(seatCharacterOf(m.memberId), '', '21 0 16 15')}
        </button>
        <div class="seat-msg-body">
          <div class="seat-msg-meta">
            <button class="seat-msg-name" data-action="member-detail" data-id="${esc(m.memberId)}">${esc(seatMemberName(m.memberId))}</button>
            ${mine ? '<i class="seat-me-tag">我</i>' : ''}
            <time>${fmt(m.created, true)}</time>
          </div>
          <div class="seat-msg-text">${esc(m.text)}</div>
        </div>
        ${can('action:seats.manage') ? `<button class="seat-del" data-action="seat-chat-del" data-id="${esc(m.id)}" title="撤回这条消息" aria-label="撤回">${icon('close')}</button>` : ''}
      </div>`;
    }).join('');
}

/* 实验室大厅：与座位图并排常驻显示，不收起、不隐藏，页面上没有两态切换 */
function seatChatHTML() {
  return `<div class="seat-chat">
    <div class="seat-chat-head">
      <div><strong>实验室大厅</strong><small>公共频道 · 全员可见</small></div>
      <span class="seat-chat-count">${_seatChat.length} 条消息</span>
    </div>
    <div class="seat-chat-list" id="seat-chat-list">${seatChatListHTML()}</div>
    <div class="seat-chat-foot">
      <input type="text" id="seat-chat-input" maxlength="200" placeholder="说点什么…（Enter 发送）"
        ${can('action:seats.chat') ? '' : 'disabled'}>
      ${btn('发送', 'seat-chat-send', 'primary')}
      <label class="seat-bub-opt"><input type="checkbox" id="seat-chat-bubble" checked>同时在座位上冒气泡</label>
    </div>
  </div>`;
}

/* 载入消息。首次进入用服务端这一页覆盖；之后（轮询）只**追加**新消息 ——
   否则每轮都会把列表整体换掉，既会顶掉「加载更早的消息」翻出来的历史，
   也会让消息列表每 15 秒闪一次。要强制重取（撤回后）先把 _seatChatLoaded 置 false。 */
async function seatChatLoad(more = false) {
  const anchor = more && _seatChat.length ? _seatChat[0].id : '';
  const res = await API.request(`/seats/chat${anchor ? `?before=${encodeURIComponent(anchor)}` : ''}`);
  const got = res.messages || [];
  if (more) {
    _seatChat = [...got, ..._seatChat];
  } else if (!_seatChatLoaded) {
    _seatChat = got;
  } else {
    const seen = new Set(_seatChat.map((m) => m.id));
    const added = got.filter((m) => !seen.has(m.id));
    if (added.length) _seatChat = [..._seatChat, ...added];
  }
  _seatChatHasMore = !!res.hasMore;
  _seatChatLoaded = true;
}

/* 大厅常驻可见 ⇒ 进页面就载入一次并标记已读（不需要「点开才算看过」） */
function seatStartChat() {
  if (typeof document === 'undefined') return;
  const done = () => { if (view === 'seats') seatSyncTargets(); };
  if (!_seatChatLoaded) seatChatLoad().then(seatChatMarkRead).then(done).catch(() => {});
  else seatChatMarkRead().then(done).catch(() => {});
}

async function seatChatMarkRead() {
  try {
    await API.request('/seats/chat/read', { method: 'POST' });
    if (db) db.seatChatUnread = 0;
  } catch (e) { /* 标已读失败不影响使用，下次轮询再试 */ }
}

/* ────────────────────────── 页面 ────────────────────────── */

function seatsPage() {
  const lo = seatLayout();
  if (!lo) {
    return `<div class="page-fit">${heading('实验室座位', '把「谁在实验室、在干什么」变成一张看得懂的俯视图。', '', 'SEATS / 在场可视化')}
      <section class="panel">${empty('还没有配置实验室布局', can('action:seats.manage')
        ? '点右上角「编辑地图」画出第一版实验室平面。' : '请联系指导老师或负责人配置实验室布局。')}
        ${can('action:seats.manage') ? `<div class="controls-wrap">${btn('编辑地图', 'seat-map-enter', 'primary')}</div>` : ''}
      </section></div>`;
  }

  const cell = SEAT_CELL_PX, gap = SEAT_GAP;
  const room = `<div class="seat-room" id="seat-room"
      style="grid-template-columns:repeat(${lo.cols},${cell}px);grid-template-rows:repeat(${lo.rows},${cell}px);gap:${gap}px;padding:${SEAT_PAD}px">
      <div class="seat-walk" id="seat-walk"></div>
      ${_seatEdit ? seatEditCellsHTML(lo) : seatCellsHTML(lo)}
    </div>`;

  /* 图例与编辑工具统统放到右侧控制列，地图卡片里只剩地图：
     这样地图能拿到整个可用高度，且两种模式留给地图的空间由结构保证完全一致 */
  const side = _seatEdit
    ? seatEditSideHTML(lo)
    : `<div class="seat-tools" id="seat-tools">${seatLegendHTML(lo)}</div>${seatChatHTML()}`;

  seatStartPoll();
  seatStartChat();
  return `<div class="page-fit">
    <div id="seat-heading">${seatHeadingHTML()}</div>
    <section class="panel seat-panel">
      <div class="seat-stage" id="seat-stage">
        <div class="seat-fit" id="seat-fit">${room}</div>
      </div>
      <aside class="seat-side" id="seat-side">${side}</aside>
    </section>
  </div>`;
}

/* ────────────────────────── 地图编辑 ────────────────────────── */

function seatEditCellsHTML(lo) {
  let html = '';
  for (let r = 0; r < lo.rows; r += 1) {
    for (let c = 0; c < lo.cols; c += 1) {
      const key = `${r}-${c}`;
      const kind = seatCellKind(lo, key);
      const label = lo.labels?.[key] || '';
      const owner = lo.owners?.[key] || '';
      /* 显式定位：与聊天态的座位格用同一套坐标，编辑时地图几何完全不动 */
      html += `<button class="seat-cell seat-paint ${SEAT_KIND_CLASS[kind] || 'k-f'}"
        style="grid-column:${c + 1};grid-row:${r + 1}"
        data-action="seat-paint" data-id="${key}" title="${key} · ${SEAT_KIND_TEXT[kind] || '通道'}">
        <span class="seat-paint-t">${kind === 'w' ? esc(label) || '#' : esc(SEAT_KIND_TEXT[kind] || '')}</span>
        ${owner ? `<span class="seat-paint-o">${esc(seatMemberName(owner).slice(-2))}</span>` : ''}
      </button>`;
    }
  }
  return html;
}

/* 笔刷面板：放在右侧控制列里（地图卡片内不放任何工具） */
function seatBrushesHTML() {
  return `<div class="seat-brushes">
    ${SEAT_BRUSHES.map(([kind, label]) => `<button class="seat-brush${_seatBrush === kind ? ' active' : ''}"
      data-action="seat-brush" data-id="${kind}"><i class="${SEAT_KIND_CLASS[kind] || 'k-f'}"></i>${label}</button>`).join('')}
  </div>
  <div class="seat-hint">选一支笔，点格子涂改；选「编号 / 归属」后点工位可设置座位号与默认主人</div>`;
}

function seatEditSideHTML(lo) {
  const stat = {};
  for (let r = 0; r < lo.rows; r += 1)
    for (let c = 0; c < lo.cols; c += 1) {
      const k = seatCellKind(lo, `${r}-${c}`);
      stat[k] = (stat[k] || 0) + 1;
    }
  return `<div class="seat-chat">
    <div class="seat-chat-head">
      <div><strong>地图编辑</strong><small>${lo.rows} × ${lo.cols} · 涂改后记得保存</small></div>
      <span class="seat-chat-count">${stat.w || 0} 工位</span>
    </div>
    <div class="seat-edit-body">
      ${seatBrushesHTML()}
      <div class="seat-size">
        <span>行数 <b>${lo.rows}</b></span>
        <button data-action="seat-size" data-id="row-">−</button>
        <button data-action="seat-size" data-id="row+">＋</button>
      </div>
      <div class="seat-size">
        <span>列数 <b>${lo.cols}</b></span>
        <button data-action="seat-size" data-id="col-">−</button>
        <button data-action="seat-size" data-id="col+">＋</button>
      </div>
      <dl class="seat-stat">
        <div><dt>工位</dt><dd>${stat.w || 0}</dd></div>
        <div><dt>通道</dt><dd>${stat['.'] || 0}</dd></div>
        <div><dt>储物柜</dt><dd>${stat.s || 0}</dd></div>
        <div><dt>测试台</dt><dd>${stat.t || 0}</dd></div>
        <div><dt>门口</dt><dd>${stat.d || 0}</dd></div>
        <div><dt>墙体</dt><dd>${stat['#'] || 0}</dd></div>
      </dl>
      <div class="seat-edit-note">保存时整份校验：每行长度、未知格子类型、座位号重复、尺寸范围。改小地图或把工位涂成家具时，站在上面的人会退回自动分配。</div>
      ${btn('恢复为默认布局', 'seat-map-reset')}
    </div>
  </div>`;
}

function seatEditDraft(lo) {
  return {
    id: lo.id, name: lo.name, rows: lo.rows, cols: lo.cols,
    grid: (lo.grid || []).map((row) => String(row).split('')),
    labels: { ...(lo.labels || {}) }, owners: { ...(lo.owners || {}) },
  };
}

function seatEditRender() {
  const lo = { ..._seatEdit, grid: _seatEdit.grid.map((row) => row.join('')) };
  const room = document.querySelector('#seat-room');
  const side = document.querySelector('.seat-edit-body');
  const box = side && side.parentElement;
  if (room) room.innerHTML = seatEditCellsHTML(lo);
  if (box) box.outerHTML = seatEditSideHTML(lo);
  seatFit();
}

/* 涂格子：只改这一格的 DOM，避免整页重绘（拖拽涂色时很关键） */
function seatPaint(key, el) {
  if (!_seatEdit) return;
  const [r, c] = key.split('-').map(Number);
  if (!_seatEdit.grid[r]) return;
  if (_seatBrush === 'label') { seatLabelForm(key); return; }
  _seatEdit.grid[r][c] = _seatBrush;
  if (_seatBrush !== 'w') {
    delete _seatEdit.labels[key];
    delete _seatEdit.owners[key];
  }
  if (el) {
    const kind = _seatBrush;
    el.className = `seat-cell seat-paint ${SEAT_KIND_CLASS[kind] || 'k-f'}`;
    el.innerHTML = `<span class="seat-paint-t">${kind === 'w' ? '#' : SEAT_KIND_TEXT[kind] || ''}</span>`;
  }
}

function seatLabelForm(key) {
  const lo = _seatEdit;
  const kind = lo.grid[Number(key.split('-')[0])]?.[Number(key.split('-')[1])];
  if (kind !== 'w') { toast('只有工位能设编号和默认主人'); return; }
  const members = (db?.members || []).filter((m) => m.active !== false);
  modal(`工位 ${key} · 编号与归属`,
    `<div class="field"><label for="seat-label-input">座位号</label>
       <input id="seat-label-input" name="label" value="${esc(lo.labels[key] || '')}" placeholder="如 B-03" maxlength="16"></div>
     <div class="field"><label for="seat-owner-input">默认主人（可选）</label>
       <select id="seat-owner-input" name="owner">${options([['', '不指定']].concat(members.map((m) => [m.id, m.name])), lo.owners[key] || '')}</select></div>
     <p class="hint">默认主人打卡后会优先坐到这里；不指定则按空工位顺序自动分配。</p>`,
    '保存',
    (form) => {
      const label = String(form.get('label') || '').trim();
      const owner = String(form.get('owner') || '');
      if (label) {
        const dup = Object.entries(lo.labels).find(([k2, v]) => v === label && k2 !== key);
        if (dup) { toast(`座位号 ${label} 已被 ${dup[0]} 占用`, true); return false; }
        lo.labels[key] = label;
      } else {
        delete lo.labels[key];
      }
      if (owner) lo.owners[key] = owner; else delete lo.owners[key];
      document.querySelector('#modal').close();
      render();
      return true;
    });
}

async function seatSaveLayout() {
  const lo = _seatEdit;
  if (!lo) return;
  const payload = { id: lo.id, name: lo.name, rows: lo.rows, cols: lo.cols,
    grid: lo.grid.map((row) => row.join('')), labels: lo.labels, owners: lo.owners };
  await API.mutate('/seats/layout/save', payload);
  _seatEdit = null;
  render();
  toast('布局已保存');
}

/* ────────────────────────── 挪位与走动 ────────────────────────── */

function seatRoomOffset(key) {
  const room = document.querySelector('#seat-room');
  if (!room) return null;
  const [r, c] = key.split('-').map(Number);
  return { x: SEAT_PAD + c * (SEAT_CELL_PX + SEAT_GAP), y: SEAT_PAD + r * (SEAT_CELL_PX + SEAT_GAP) };
}

/* 走过去：本地先动（乐观更新）+ 立刻起动画，服务端在后台确认；
   被拒（那一格有人 / 未打卡）再回到服务端真值并说明原因。
   这样挪位不等一次服务器往返，才有「游戏里点哪走哪」的手感。 */
function seatMove(row, col) {
  const meId = me()?.id;
  const key = `${row}-${col}`;
  const fromKey = seatPosOf(meId);
  const from = fromKey ? seatRoomOffset(fromKey) : null;

  db.seatPresence = (db.seatPresence || []).map((p) => (p.memberId === meId ? { ...p, row, col } : p));
  _seatWalking = true;
  seatSyncTargets();

  const to = seatRoomOffset(key);
  const layer = document.querySelector('#seat-walk');
  if (from && to && layer) {
    layer.innerHTML = `<div class="seat-walker" style="transform:translate(${from.x}px,${from.y}px)">${seatStandSVG(seatCharacterOf(meId))}</div>`;
    const walker = layer.firstElementChild;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      walker.style.transform = `translate(${to.x}px,${to.y}px)`;
    }));
    setTimeout(() => {
      _seatWalking = false;
      seatSyncTargets();
      toast(`已走到 ${seatCellName(row, col)}`);
    }, SEAT_WALK_MS + 40);
  } else {
    _seatWalking = false;
    seatSyncTargets();
    toast(`已到 ${seatCellName(row, col)}`);
  }

  return API.request('/seats/move', { method: 'POST', body: JSON.stringify({ row, col }) })
    .catch(async (err) => {
      _seatWalking = false;
      toast(err.message || '挪位没成功', true);
      await API.load();
      seatSyncTargets();
    });
}

function seatCellName(row, col) {
  const lo = seatLayout();
  return lo?.labels?.[`${row}-${col}`] || '通道空地';
}

/* ────────────────────────── 面板与表单 ────────────────────────── */

function seatSelfPanel() {
  const meId = me().id;
  const st = seatStatusOf(meId);
  const pos = seatPosOf(meId);
  return modal(`我的位置 · ${seatCellName(...(pos ? pos.split('-').map(Number) : [0, 0]))}`,
    `<div class="seat-self">
       <div class="seat-self-av">${seatSceneSVG(seatCharacterOf(meId))}</div>
       <div>
         <strong>${esc(me().name)}</strong>
         <div class="seat-self-st"><i style="background:${seatStatusColor(st.key)}"></i>${esc((SEAT_STATUS_MAP[st.key] || {}).label || '')}</div>
         <div class="seat-self-tx">${esc(st.text)}</div>
         <div class="seat-self-pos">当前位置 ${esc(seatCellName(...(pos ? pos.split('-').map(Number) : [0, 0])))} · 走开后原位立即空出</div>
       </div>
     </div>
     <div class="seat-menu">
       ${can('action:seats.status') ? `<button class="seat-menu-btn" data-action="seat-status"><b>改状态</b><small>加点文字，让大家知道你在忙什么</small></button>` : ''}
       ${can('action:seats.bubble') ? `<button class="seat-menu-btn" data-action="seat-bubble"><b>冒条气泡</b><small>15 秒后自动消失，可点击提前关闭</small></button>` : ''}
       ${can('action:seats.status') ? `<button class="seat-menu-btn" data-action="seat-character"><b>编辑形象</b><small>肤色 / 发型 / 衣着 / 桌上物品</small></button>` : ''}
       <button class="seat-menu-btn" data-action="seat-highlight"><b>高亮可去位置</b><small>把当前所有能过去的空位点亮</small></button>
     </div>`,
    '',
    null,
    can('action:checkin.create')
      ? btn(`${icon('logout')} 下班签退`, 'seat-signout')
      : '');
}

function seatOtherPanel(mid) {
  const st = seatStatusOf(mid);
  const pos = seatPosOf(mid);
  modal('',
    `<div class="seat-self">
       <div class="seat-self-av">${seatSceneSVG(seatCharacterOf(mid))}</div>
       <div>
         <strong>${esc(seatMemberName(mid))}</strong>
         <div class="seat-self-st"><i style="background:${seatStatusColor(st.key)}"></i>${esc((SEAT_STATUS_MAP[st.key] || {}).label || '')}</div>
         <div class="seat-self-tx">${esc(st.text)}</div>
         <div class="seat-self-pos">当前位置 ${esc(seatCellName(...(pos ? pos.split('-').map(Number) : [0, 0])))} · 只能由本人移动</div>
       </div>
     </div>`,
    '',
    null,
    btn('进他的主页', 'member-detail', '', `data-id="${esc(mid)}"`)
      + (can('action:seats.chat') ? btn('在大厅 @ 他', 'seat-chat-at', 'primary', `data-id="${esc(mid)}"`) : ''));
}

function seatStatusForm() {
  const meId = me().id;
  const st = seatStatusOf(meId);
  modal('设置状态',
    `<div class="seat-chips" id="seat-status-chips">
       ${SEAT_STATUSES.map((s) => `<button class="seat-chip${s.key === st.key ? ' active' : ''}" data-action="seat-status-pick" data-id="${s.key}">
         <i style="background:${s.color}"></i>${s.label}</button>`).join('')}
     </div>
     <div class="field"><label for="seat-status-text">状态文字（≤ 30 字）</label>
       <input id="seat-status-text" name="text" value="${esc(st.text)}" maxlength="30" placeholder="例如：在跑电机闭环"></div>
     <p class="hint">状态持续到签退或下次修改，全员可见；格子上的边框与名字前的圆点取状态色。</p>`,
    '保存状态',
    (form) => {
      const key = document.querySelector('.seat-chip.active')?.dataset.id || 'custom';
      const text = String(form.get('text') || '').trim();
      if (key === 'custom' && !text) { toast('自定义状态要填文字', true); return false; }
      return API.mutate('/seats/status', { statusKey: key, text }).then(() => {
        document.querySelector('#modal').close();
        seatSyncTargets();
        toast('状态已更新');
        return true;
      });
    });
}

function seatBubbleForm() {
  modal('冒一条气泡',
    `<div class="field"><label for="seat-bubble-text">消息内容（≤ 50 字）</label>
       <input id="seat-bubble-text" name="text" maxlength="50" placeholder="例如：去借万用表，马上回"></div>
     <p class="hint">气泡浮在你的小人上方，15 秒后自动消失；点击气泡可提前关闭。同一人 60 秒内只能发一条。</p>`,
    '发送气泡',
    (form) => {
      const text = String(form.get('text') || '').trim();
      if (!text) { toast('先写点内容', true); return false; }
      return API.mutate('/seats/bubble', { text }).then(() => {
        document.querySelector('#modal').close();
        seatSyncTargets();
        toast('气泡已发出');
        return true;
      });
    });
}

function seatCharacterEditor() {
  const meId = me().id;
  const draft = { ...seatCharacterOf(meId) };
  const body = () => {
    const opts = (slot) => {
      const values = SEAT_CHARACTER_BOOK[slot];
      if (slot === 'glasses')
        return values.map((v) => `<button class="seat-opt${draft[slot] === v ? ' active' : ''}" data-action="seat-char-pick" data-id="${slot}:${v}">${v ? '有镜框' : '不戴'}</button>`).join('');
      if (slot === 'hairStyle' || slot === 'prop') {
        const names = slot === 'hairStyle' ? SEAT_HAIR_LABEL : SEAT_PROP_LABEL;
        return values.map((v) => `<button class="seat-opt${draft[slot] === v ? ' active' : ''}" data-action="seat-char-pick" data-id="${slot}:${v}">${esc(names[v] || v)}</button>`).join('');
      }
      return values.map((v) => `<button class="seat-swatch${draft[slot] === v ? ' active' : ''}" data-action="seat-char-pick"
        data-id="${slot}:${v}" style="background:${v}" aria-label="${v}"></button>`).join('');
    };
    return `<div class="seat-char">
        <div class="seat-char-prev" id="seat-char-prev">${seatSceneSVG(draft)}</div>
        <div class="seat-char-parts">
          ${Object.keys(SEAT_CHARACTER_BOOK).map((slot) => `<div class="seat-part">
            <label>${SEAT_PART_LABEL[slot]}</label><div class="seat-opts">${opts(slot)}</div></div>`).join('')}
        </div>
      </div>
      <p class="hint">形象由白名单部件拼装（不接受上传任意 SVG），保存后全员可见。</p>`;
  };
  modal('编辑我的形象', body(), '保存形象', () => {
    const parts = {};
    for (const slot of Object.keys(SEAT_CHARACTER_BOOK)) parts[slot] = draft[slot];
    return API.mutate('/seats/character', { parts }).then(() => {
      document.querySelector('#modal').close();
      seatSyncTargets();
      toast('形象已保存');
      return true;
    });
  });
  _seatCharDraft = draft;
}
let _seatCharDraft = null;

/* 形象编辑器里改一个部件：只重画预览与选中态，不关弹窗 */
function seatCharPick(token) {
  if (!_seatCharDraft) return;
  const i = token.indexOf(':');
  const slot = token.slice(0, i), raw = token.slice(i + 1);
  _seatCharDraft[slot] = slot === 'glasses' ? raw === 'true' : raw;
  const prev = document.querySelector('#seat-char-prev');
  if (prev) prev.innerHTML = seatSceneSVG(_seatCharDraft);
  document.querySelectorAll('[data-action="seat-char-pick"]').forEach((el) => {
    const [s, v] = el.dataset.id.split(':');
    el.classList.toggle('active', String(_seatCharDraft[s]) === v);
  });
}

/* ────────────────────────── 自适应缩放 ────────────────────────── */

/* 自适应缩放：让座位图完整落在自己的卡片里。
   关键点：
   1. `.seat-room` 用 `transform-origin: top left` 缩放 —— 否则缩放后仍以「未缩放盒的中心」
      为原点，视觉盒会整体向右/向下偏移（(原尺寸-缩放后)/2），右侧就被聊天面板盖住。
      改左上角原点后，视觉盒与 #seat-fit 的尺寸框完全重合。
   2. 地图卡片里只有地图（图例与工具都在右侧控制列），所以可用高度就是整张卡片，
     且两种模式完全一致 —— 地图尺寸不会因为切模式而变。 */
function seatFit() {
  const lo = seatLayout();
  const stage = document.querySelector('#seat-stage');
  const fit = document.querySelector('#seat-fit');
  const room = document.querySelector('#seat-room');
  if (!lo || !stage || !fit || !room) return;

  const style = typeof getComputedStyle === 'function' ? getComputedStyle(stage) : null;
  const num = (v) => parseFloat(v) || 0;
  const padX = style ? num(style.paddingLeft) + num(style.paddingRight) : 24;
  const padY = style ? num(style.paddingTop) + num(style.paddingBottom) : 20;

  const availW = stage.clientWidth - padX;
  const availH = stage.clientHeight - padY;
  const natural = seatRoomNatural(lo);
  const raw = Math.min(1, availW / natural.w, availH / natural.h);
  const scale = Math.max(0.3, Math.floor(raw * 100) / 100);

  room.style.transform = `scale(${scale})`;
  fit.style.width = `${Math.round(natural.w * scale)}px`;
  fit.style.height = `${Math.round(natural.h * scale)}px`;
}

/* 轮询：只拉 GET /seats/layout（座位状态那一小份数据），不再整份 workspace。
   页面不可见、正在编辑地图、正在走动、有弹窗打开时都跳过这一轮。
   拿回数据后先比签名，没变就一个 DOM 都不碰 —— 界面因此是「一直保持」的，
   不会隔一会闪一下（那种闪就是因为每轮都把 143 个格子 + 内联 SVG 重画了一遍）。 */
function seatStartPoll() {
  if (typeof setInterval !== 'function' || typeof document === 'undefined') return;
  if (_seatTimer) clearInterval(_seatTimer);
  _seatTimer = setInterval(seatPollOnce, SEAT_POLL_MS);
  if (typeof requestAnimationFrame === 'function') requestAnimationFrame(seatFit);
}

async function seatPollOnce() {
  if (view !== 'seats' || !me()) {
    if (_seatTimer) { clearInterval(_seatTimer); _seatTimer = null; }
    return;
  }
  if (_seatEdit || _seatWalking || _seatPainting) return;
  /* 切到别的标签页/最小化时不轮询，回来时由 visibilitychange 立即补一次 */
  if (typeof document.hidden === 'boolean' && document.hidden) return;
  const dialog = document.querySelector('#modal');
  if (dialog && dialog.open) return;
  try {
    const st = await API.request('/seats/layout');
    if (db) {
      db.seatLayout = st.layout;
      db.seatPresence = st.presence;
      db.seatStatuses = st.statuses;
      db.seatCharacters = st.characters;
      db.seatBubbles = st.bubbles;
      db.seatChatUnread = st.unread;
    }
    await seatChatLoad();
    /* 大厅常驻可见 ⇒ 看到了就算已读；只在真有未读时才写一次，避免每轮都打服务器 */
    if ((db?.seatChatUnread || 0) > 0) await seatChatMarkRead();
    seatSyncTargets();
  } catch (e) { /* 轮询失败静默，下一轮再试 */ }
}

/* 页头（标题 / 文案 / 按钮）单独抽出来：在席状态一变就要跟着变，单独换它便宜得多 */
function seatHeadingHTML() {
  if (_seatEdit) {
    return heading('实验室座位', '选一支笔涂改实验室平面，改完记得保存。',
      btn(`${icon('close')} 取消编辑`, 'seat-map-exit') + btn(`${icon('check')} 保存布局`, 'seat-map-save', 'primary'),
      'SEATS / 地图编辑');
  }
  return heading('实验室座位',
    seatAmOnDuty() ? '点空位就能走过去；签退后小人消失。' : '你还没在席 —— 先去打卡，小人就会出现在座位上。',
    /* 这里不放「刷新」：座位状态是自动保持的（轮询 + 签名比对），
       手动刷新按钮只会让人以为页面要自己按一下才更新 */
    btn(`${icon('user')} 我的形象`, 'seat-character')
      + btn(`${icon('pin')} 高亮可去位置`, 'seat-highlight')
      + (seatAmOnDuty() && can('action:checkin.create') ? btn(`${icon('logout')} 下班签退`, 'seat-signout') : '')
      + (can('action:seats.manage') ? btn(`${icon('grid')} 编辑地图`, 'seat-map-enter') : ''),
    'SEATS / 在场可视化 · b' + SEAT_BUILD);
}

/* 只换侧栏（进/出地图编辑是结构变化时才用） */
function seatSyncSide() {
  const side = document.querySelector('#seat-side');
  if (side && !_seatEdit) side.innerHTML = seatChatHTML();
}

/* 地图区「会变化的部分」的签名：布局 / 在席位置 / 状态 / 形象 / 气泡 / 模式 / 我是否在席。
   轮询时先比签名，一样就连一次 DOM 都不碰 —— 否则每轮都把 143 个格子 + 内联 SVG
   重画一遍，看起来就是「隔一会自动刷新一下」。 */
function seatRoomSig() {
  const lo = seatLayout();
  if (!lo) return 'none';
  const pos = seatPosMap();
  const bubbles = seatBubbles();
  const ids = Object.keys(pos).sort();
  return [
    lo.updated || '', lo.rows, lo.cols, (lo.grid || []).join(''),
    JSON.stringify(lo.labels || {}), JSON.stringify(lo.owners || {}),
    _seatEdit ? 'edit' : 'chat', _seatWalking ? 'walking' : '',
    seatAmOnDuty() ? 'onduty' : 'off',
    ids.map((m) => `${m}>${pos[m]}`).join(','),
    ids.map((m) => `${m}:${seatStatusOf(m).key}:${seatStatusOf(m).text}`).join(','),
    ids.map((m) => JSON.stringify(seatCharacterOf(m))).join(','),
    Object.keys(bubbles).sort().map((m) => `${m}:${bubbles[m]}`).join(','),
  ].join('|');
}

/* 消息列表的签名：只在真的多了/少了/改了一条消息，或未读数变了时才重画列表 */
function seatChatSig() {
  return `${db?.seatChatUnread || 0}|${_seatChatLoaded ? 1 : 0}|${_seatChatHasMore ? 1 : 0}|`
    + _seatChat.map((m) => `${m.id}:${m.text}`).join(',');
}

/* 局部刷新：只换真正变了的那几块，地图区与消息列表各自独立脏检查。
   绝不重建 shell，也绝不重建聊天输入框；两处都没变时返回 false，一个 DOM 都不碰。 */
function seatSyncTargets(force) {
  const roomSig = seatRoomSig(), chatSig = seatChatSig();
  const roomDirty = force || roomSig !== _seatRoomSig;
  const chatDirty = force || chatSig !== _seatChatSig;
  if (!roomDirty && !chatDirty) return false;
  _seatRoomSig = roomSig;
  _seatChatSig = chatSig;

  const lo = seatLayout();
  if (roomDirty) {
    const room = document.querySelector('#seat-room');
    if (lo && room) room.innerHTML = `<div class="seat-walk" id="seat-walk"></div>${_seatEdit ? seatEditCellsHTML(lo) : seatCellsHTML(lo)}`;
    const head = document.querySelector('#seat-heading');
    if (head) head.innerHTML = seatHeadingHTML();
    /* 图例在右侧控制列里，就地更新 */
    const tools = document.querySelector('#seat-tools');
    if (lo && tools) tools.innerHTML = seatLegendHTML(lo);
    seatFit();
  }
  if (chatDirty) {
    const count = document.querySelector('#seat-side .seat-chat-count');
    if (count) count.textContent = `${_seatChat.length} 条消息`;
    /* 消息列表重画，但保留阅读位置：原本贴着底部就跟着新消息走 */
    const list = document.querySelector('#seat-chat-list');
    if (list) {
      const atBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 48;
      const keep = list.scrollTop;
      list.innerHTML = seatChatListHTML();
      list.scrollTop = atBottom ? list.scrollHeight : keep;
    }
  }
  return true;
}

/* ────────────────────────── 动作表 ────────────────────────── */

const SEATS_ACTIONS = {
  'seat-cell': (key) => {
    const lo = seatLayout();
    if (!lo) return;
    const pos = seatPosMap();
    const mid = Object.keys(pos).find((k) => pos[k] === key);
    if (mid) {
      if (mid === me().id) seatSelfPanel();
      else seatOtherPanel(mid);
      return;
    }
    const kind = seatCellKind(lo, key);
    if (!seatIsWalkable(kind)) { toast('那一格放不下人（墙 / 储物柜 / 测试台 / 门口）', true); return; }
    if (!can('action:seats.move')) { toast('没有移动小人的权限', true); return; }
    const [r, c] = key.split('-').map(Number);
    return seatMove(r, c);
  },
  'seat-bubble-close': (mid) => {
    /* 只在前端收起，服务端 15 秒后自然过期 */
    if (db?.seatBubbles) db.seatBubbles = db.seatBubbles.filter((b) => b.memberId !== mid);
    seatSyncTargets();
  },
  'seat-status': () => seatStatusForm(),
  'seat-status-pick': (key) => {
    document.querySelectorAll('.seat-chip').forEach((el) => el.classList.toggle('active', el.dataset.id === key));
  },
  'seat-bubble': () => seatBubbleForm(),
  'seat-character': () => seatCharacterEditor(),
  'seat-char-pick': (token) => seatCharPick(token),
  'seat-highlight': () => {
    const room = document.querySelector('#seat-room');
    if (!room) return;
    const on = room.classList.toggle('hl');
    toast(on ? '可去的空位已高亮' : '已取消高亮');
  },
  'seat-signout': () => modal('下班签退',
    '<p style="line-height:1.9;font-size:13px">签退后今天不能再打卡，你在座位上的小人会立刻消失。确定离开实验室吗？</p>',
    '确认签退',
    async () => {
      await API.request('/checkins/signout', { method: 'POST' });
      await API.load();
      document.querySelector('#modal')?.close();
      seatSyncTargets();
      toast('已签退，座位上的小人已消失');
    }),
  'seat-chat-more': async () => {
    await seatChatLoad(true);
    seatSyncTargets();
  },
  'seat-chat-send': async () => {
    const input = document.querySelector('#seat-chat-input');
    const text = String(input?.value || '').trim();
    if (!text) { toast('先写点内容', true); return; }
    const bubble = !!document.querySelector('#seat-chat-bubble')?.checked;
    await API.mutate('/seats/chat/send', { text, bubble });
    await seatChatLoad();
    /* 局部刷新：输入框不重建，发完还停在原地可以直接接着打 */
    if (input) input.value = '';
    seatSyncTargets();
    document.querySelector('#seat-chat-input')?.focus();
    toast('已发送到实验室大厅');
  },
  'seat-chat-at': (mid) => {
    document.querySelector('#modal')?.close();
    /* 大厅常驻显示，这里只要把光标放到输入框并预填 @他 */
    seatChatLoad().then(() => {
      seatSyncTargets();
      const input = document.querySelector('#seat-chat-input');
      if (input) { input.value = `@${seatMemberName(mid)} `; input.focus(); }
    });
  },
  /* 撤回是管理端动作：不走 confirmation（它内部会 render() 整页重绘） */
  'seat-chat-del': (id) => modal('撤回这条消息',
    '<p style="line-height:1.9;font-size:13px">撤回后其他人将看不到这条消息（保留审计记录）。确定撤回吗？</p>',
    '确认撤回',
    async () => {
      await API.request(`/seats/chat/${id}/delete`, { method: 'POST' });
      /* 撤回后必须整份重取（轮询默认只追加新消息，不会把撤掉的从列表里摘掉） */
      _seatChatLoaded = false;
      await seatChatLoad();
      document.querySelector('#modal')?.close();
      seatSyncTargets();
      toast('已撤回');
    }),
  /* ── 地图编辑 ── */
  'seat-map-enter': () => {
    const lo = seatLayout();
    if (!lo) return;
    _seatEdit = seatEditDraft(lo);
    _seatBrush = 'w';
    render();
    toast('已进入编辑模式，选笔后点格子涂改');
  },
  'seat-map-exit': () => {
    _seatEdit = null;
    render();
    toast('已取消编辑');
  },
  'seat-map-save': () => seatSaveLayout(),
  'seat-map-reset': () => {
    if (!_seatEdit) return;
    _seatEdit = { ..._seatEdit, rows: 11, cols: 13,
      grid: ['#############', '#d..........#', '#.ss...ss...#', '#.ww...ww...#', '#.ww...ww...#',
        '#...ttttt...#', '#.ww...ww...#', '#.ww...ww...#', '#.ss...ss...#', '#...........#',
        '#############'].map((r) => r.split('')),
      labels: {}, owners: {} };
    let n = 0;
    _seatEdit.grid.forEach((row, r) => row.forEach((k, c) => {
      if (k === 'w') { n += 1; _seatEdit.labels[`${r}-${c}`] = `B-${String(n).padStart(2, '0')}`; }
    }));
    seatEditRender();
    toast('已恢复为默认布局（未保存）');
  },
  'seat-brush': (kind) => {
    _seatBrush = kind;
    document.querySelectorAll('.seat-brush').forEach((el) => el.classList.toggle('active', el.dataset.id === kind));
    if (kind === 'label') toast('点任意工位设置座位号与默认主人');
  },
  'seat-paint': (key) => seatPaint(key, document.querySelector(`.seat-paint[data-id="${key}"]`)),
  'seat-size': (op) => {
    if (!_seatEdit) return;
    const grow = op.endsWith('+');
    if (op.startsWith('row')) {
      const next = _seatEdit.rows + (grow ? 1 : -1);
      if (next < 3 || next > 40) { toast('行数需在 3~40 之间', true); return; }
      if (grow) _seatEdit.grid.push(new Array(_seatEdit.cols).fill('.'));
      else {
        _seatEdit.grid.pop();
        for (const k of Object.keys({ ..._seatEdit.labels })) if (Number(k.split('-')[0]) >= next) delete _seatEdit.labels[k];
        for (const k of Object.keys({ ..._seatEdit.owners })) if (Number(k.split('-')[0]) >= next) delete _seatEdit.owners[k];
      }
      _seatEdit.rows = next;
    } else {
      const next = _seatEdit.cols + (grow ? 1 : -1);
      if (next < 3 || next > 40) { toast('列数需在 3~40 之间', true); return; }
      _seatEdit.grid = _seatEdit.grid.map((row) => (grow ? [...row, '.'] : row.slice(0, next)));
      if (!grow) {
        for (const k of Object.keys({ ..._seatEdit.labels })) if (Number(k.split('-')[1]) >= next) delete _seatEdit.labels[k];
        for (const k of Object.keys({ ..._seatEdit.owners })) if (Number(k.split('-')[1]) >= next) delete _seatEdit.owners[k];
      }
      _seatEdit.cols = next;
    }
    seatEditRender();
  },
};

window.seatsPage = seatsPage;
window.SEATS_ACTIONS = SEATS_ACTIONS;

/* 拖拽涂色：按住左键划过格子连续涂改（捕获阶段，先于 app.js 的委托） */
if (typeof document !== 'undefined' && document.addEventListener) {
  document.addEventListener('mousedown', (e) => {
    if (!_seatEdit) return;
    const cell = e.target?.closest?.('[data-action="seat-paint"]');
    if (cell) _seatPainting = true;
  });
  document.addEventListener('mouseup', () => { _seatPainting = false; });
  document.addEventListener('mouseover', (e) => {
    if (!_seatPainting || !_seatEdit || _seatBrush === 'label') return;
    const cell = e.target?.closest?.('[data-action="seat-paint"]');
    if (cell) seatPaint(cell.dataset.id, cell);
  });
  window.addEventListener('resize', () => { if (view === 'seats') seatFit(); });
  /* 切回本标签页时立刻补一次，而不是等下一个轮询周期 */
  document.addEventListener('visibilitychange', () => {
    if (view === 'seats' && document.hidden === false) seatPollOnce();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' || view !== 'seats') return;
    if (e.target?.id === 'seat-chat-input') { e.preventDefault(); SEATS_ACTIONS['seat-chat-send'](); }
  });
}