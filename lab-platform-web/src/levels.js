'use strict';
// 关卡系统前端：技能进度图 + 关卡网格 + 详情（任务/通关墙/提交/审核/配置）。
// 数据来自 workspace 的 levels（快照）+ /levels/<id>/detail（详情）。

const LEVEL_CHAINS = ['51单片机', '物联网', '电赛', '无人机', '嵌入式', '其他'];
const LEVEL_STATUS = [['open', '开放'], ['closed', '已关闭']];
let _levelDetail = null;
let _levelDetailPending = false;

// 流程画布交互状态（全局场景，声明置于顶部避免 TDZ 问题）
let _drag = null;          // {mode, id, startX, startY, ox, oy, moved}
let _connDraft = null;     // 拖拽连线中的预览线 {fromId, x, y}
let _justDragged = false;  // 拖拽结束后抑制紧随其后的点击
let _sinkUntil = 0;        // 手势结束后吞掉点击的时间窗（毫秒时间戳）

const _murl = (u) => (u || '').startsWith('/') ? u : '/' + (u || '#');
const _isImg = (a) => /\.(jpg|jpeg|png|gif|webp|avif)$/i.test((a && (a.name || a.url)) || '');
const _isVid = (a) => /\.(mp4|mov)$/i.test((a && (a.name || a.url)) || '');

function _stars(s) {
  return `<span class="score-chip grade-${Math.max(0, Math.min(3, s || 0))}">${['', '一档', '二档', '三档'][Math.max(0, Math.min(3, s || 0))]}</span>`;
}

// ── 技能关卡选关路径（技能线 tab + 节点进阶图）──

let _levelChain = '';
let _lvFlowDirty = false;      // 画布是否有未保存的拖拽/连线改动
let _flowEdit = false;         // 是否处于编辑模式（可拖拽/连线/加节点）
const _flowPos = {};           // id -> {x,y}（拖拽暂存，保存时才落库）

function _chainList() {
  return (db.levels || []).filter((l) => l.chain === _levelChain);
}

function _lvNode(id) {
  return (db.levels || []).find((l) => l.id === id) || null;
}

function levelsPage() {
  const canManage = can('action:level.manage');
  const chains = [...new Set((db.levels || []).map((l) => l.chain))];
  if (!_levelChain || !chains.includes(_levelChain)) _levelChain = chains[0] || '';
  const tabs = chains.length
    ? `<div class="view-tabs" role="tablist">${chains.map((c) => `<button class="vt ${_levelChain === c ? 'active' : ''}" data-action="level-chain" data-id="${esc(c)}" role="tab" aria-selected="${_levelChain === c}">${esc(c)}</button>`).join('')}</div>`
    : '';
  const actions = (canManage ? btn(`${icon('plus')} 新建关卡`, 'level-new', 'primary') : '') + (can('action:level.review') ? btn(`${icon('shield')} 审核`, 'level-review-center') : '');
  const meta = `<div class="chain-meta"><span class="large">${esc(_levelChain)}</span><small class="muted">已通过 ${_chainList().filter((l) => l.my && ['passed', 'done'].includes(l.my.status)).length} / ${_chainList().length} 关</small></div>`;
  return `<div class="page-fit">${heading('技能关卡', `按连线顺序逐关进阶。拖动卡片可调整布局，四边圆点连接下级关卡。当前技能线：${esc(_levelChain) || '—'}`, actions, 'LEVELS / 技能关卡')}${tabs}${meta}<div class="level-map-wrap">${_levelChain ? flowCanvas() : empty('暂无技能线', '管理员发布关卡后这里会出现进阶路径。')}</div></div>`;
}

// 卡片静态口径：宽 150、高 88（外部流经 margin-left）
const LV_W = 150, LV_H = 76;

function _lvPos(l) {
  return _flowPos[l.id] || { x: l.posX || 0, y: l.posY || 0 };
}

// 四边占位坐标（连线的起终点用卡片中心，表现为视觉上的圆点）
function _lvPort(l, side) {
  const p = _lvPos(l);
  const cx = p.x + LV_W / 2, cy = p.y + LV_H / 2;
  return {
    T: [cx, p.y], B: [cx, p.y + LV_H], L: [p.x, cy], R: [p.x + LV_W, cy],
  }[side];
}

function flowCanvas() {
  const list = _chainList();
  if (!list.length) return empty('该技能线暂无关卡', '管理员发布关卡后即可开始进阶。');
  const canManage = can('action:level.manage');
  // 画布尺寸：按每个节点的坐标 + 卡片尺寸计算，右下留白
  const xs = list.map((l) => _lvPos(l).x), ys = list.map((l) => _lvPos(l).y);
  const W = Math.max(720, Math.max(...xs) + LV_W + 40), H = Math.max(460, Math.max(...ys) + LV_H + 40);

  const nodes = list.map((l) => {
    const p = _lvPos(l);
    const doneSt = l.my && ['passed', 'done'].includes(l.my.status);
    const cls = !l.unlocked ? 'lock' : doneSt ? 'done' : l.my && l.my.status === 'pending' ? 'pending' : 'active';
    if (!canManage) {
      return `<button class="lv-flow-node ${cls}" data-action="level-open" data-id="${esc(l.id)}" data-lvid="${esc(l.id)}" style="left:${p.x}px;top:${p.y}px" title="${esc(l.title)} · ${esc(l.description || '')}">
        <span class="n-cap">${esc(l.title)}</span><span class="n-sub">${!l.unlocked ? '未解锁' : l.chapter}</span><i class="chp chp-${l.chapter}"></i></button>`;
    }
    // 管理态 + 编辑态才显示四边端口；查看态不渲染端口（消除误点）
    // L/R 表示链路的前后关系（L=前置，R=后续），T/B 只用于换方向新建
    const prevLv = _lvNode(l.requirePassId);
    const nextLv = _lvNode(l.flowNextId);
    const portBtn = (side, show, title) =>
      `<span class="lv-port lv-port${side} ${show ? 'minus' : 'add'}" data-flow-side="${side}" data-id="${esc(l.id)}" data-flow-action="${show ? 'del' : 'add'}" title="${title}">${show ? '−' : '＋'}</span>`;
    const ports = (_flowEdit && canManage)
      ? `${portBtn('L', !!prevLv, prevLv ? `断开前置「${prevLv.title}」` : '在左侧新建前置关卡')}
         ${portBtn('T', false, '在上方新建前置关卡')}
         ${portBtn('B', false, '在下方新建后续关卡')}
         ${portBtn('R', !!nextLv, nextLv ? `断开后续「${nextLv.title}」` : '在右侧新建后续关卡')}`
      : '';
    return `<button class="lv-flow-node ${cls}${_flowEdit ? ' edit' : ''}" data-action="level-open" data-id="${esc(l.id)}" data-lvid="${esc(l.id)}" style="left:${p.x}px;top:${p.y}px" title="${esc(l.title)} · ${esc(l.description || '')}">
      ${ports}
      <span class="n-cap">${esc(l.title)}</span><span class="n-sub">${!l.unlocked ? '未解锁' : l.chapter}</span><i class="chp chp-${l.chapter}"></i>${nextLv ? '<i class="lv-nextdot"></i>' : ''}</button>`;
  }).join('');

  const editbar = canManage
    ? `<div class="lv-flow-tools">${btn(_flowEdit ? '完成' : '编辑布局', 'lv-flow-toggle', _flowEdit ? 'primary' : '')}${_flowEdit ? `${btn('重排', 'lv-flow-auto')}${_lvFlowDirty ? btn('保存布局', 'lv-flow-save', 'primary') : ''}` : ''}</div>`
    : '';
  return `<div class="lv-flow${_flowEdit ? ' editing' : ''}">
    ${editbar}
    ${_flowEdit ? `<div class="lv-flow-hint">${icon('move')} 拖动卡片调整位置 · 拖动卡片右侧圆点拖到另一张卡片，形成「本关 → 下一关」的顺序 · ＋ 在对应方向新建关卡（左/上=前置，右/下=后续，自动连线） · − 断开已有连线</div>` : ''}
    <div class="lv-flow-canvas" style="width:${W}px;height:${H}px">
      <svg class="lv-flow-edges" width="${W}" height="${H}"><defs><marker id="arrowLvF" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0 0 L9 4.5 L0 9 Z" fill="#7c8aa5"/></marker></defs>${_lvEdges()}${_connLine()}</svg>
      <div class="lv-flow-nodes">${nodes}</div>
    </div>
  </div>`;
}

// ── 画布交互：卡片拖动 / 圆点连线 / 定点新增 ──
const _DRAG_BIND = (e) => {
  const t = e.target;
  const port = t.closest('.lv-port');
  const node = t.closest('.lv-flow-node');
  if (!node) return;
  if (!_flowEdit) return;      // 查看模式不干预，点击卡片照常打开详情
  const lv = _lvNode(node.dataset.id);
  if (!lv) return;
  _justDragged = false;        // 新一轮手势开始，允许后续点击（消除拖拽后的误抑制）
  _drag = { id: lv.id, startX: e.clientX, startY: e.clientY, moved: false };
  if (port) {
    _drag.mode = 'conn';
    _connDraft = { fromId: lv.id, x: e.clientX, y: e.clientY };
  } else {
    _drag.mode = 'move';
    _drag.ox = _lvPos(lv).x;
    _drag.oy = _lvPos(lv).y;
  }
  document.addEventListener('pointermove', _flowMove, { passive: false });
  document.addEventListener('pointerup', _flowUp);
  document.addEventListener('pointercancel', _flowCancel);
};

function _flowCanvasPoint(clientX, clientY) {
  const c = document.querySelector('.lv-flow-canvas');
  if (!c) return { x: 0, y: 0 };
  const r = c.getBoundingClientRect();
  return { x: clientX - r.left + c.scrollLeft, y: clientY - r.top + c.scrollTop };
}

function _flowMove(e) {
  if (!_drag) return;
  e.preventDefault();
  if (Math.abs(e.clientX - _drag.startX) + Math.abs(e.clientY - _drag.startY) < 5) return;
  _drag.moved = true;
  if (_drag.mode === 'conn' && _connDraft) {
    const p = _flowCanvasPoint(e.clientX, e.clientY);
    _connDraft.x = p.x; _connDraft.y = p.y;
    _renderEdges();
  } else if (_drag.mode === 'move') {
    const dx = e.clientX - _drag.startX, dy = e.clientY - _drag.startY;
    const p = { x: Math.max(0, _drag.ox + dx), y: Math.max(0, _drag.oy + dy) };
    _flowPos[_drag.id] = p;
    _lvFlowDirty = true;
    const el = document.querySelector(`.lv-flow-node[data-lvid="${_drag.id}"]`);
    if (el) { el.style.left = p.x + 'px'; el.style.top = p.y + 'px'; }
    _renderEdges();
  }
}

function _flowUp(e) {
  if (!_drag) return;
  if (_drag.moved && _drag.mode === 'conn' && _connDraft) {
    const t = document.elementFromPoint(e.clientX, e.clientY);
    const target = t && t.closest ? t.closest('.lv-flow-node') : null;
    if (target && target.dataset.id !== _drag.id) {
      levelConnect(_drag.id, target.dataset.id); // 连线：拖拽起点成为落点关卡的前置
    }
    _connDraft = null;
  }
  _cleanDrag();
}

function _flowCancel() { _connDraft = null; _cleanDrag(); }

let _justDraggedTimer = 0;
function _cleanDrag() {
  if (_drag && _drag.moved) {
    _justDragged = true;
    // 拖拽结束的短窗口内吞掉全部后续点击（含浏览器合成出的双击第二击）
    _sinkUntil = Date.now() + 250;
  }
  const redraw = _drag && _lvFlowDirty;
  _drag = null;
  document.removeEventListener('pointermove', _flowMove);
  document.removeEventListener('pointerup', _flowUp);
  document.removeEventListener('pointercancel', _flowCancel);
  if (redraw) render();
}

// 边：前置 → 后续（箭头指向下一关）；同一前置的多个后续在源头纵向错位
function _lvEdges() {
  const list = _chainList();
  const fan = {};
  list.forEach((l) => { if (l.requirePassId && _lvNode(l.requirePassId)) (fan[l.requirePassId] = fan[l.requirePassId] || []).push(l.id); });
  return list.filter((l) => l.requirePassId && _lvNode(l.requirePassId)).map((l) => {
    const p = _lvNode(l.requirePassId);
    const kids = fan[l.requirePassId] || [];
    const idx = Math.max(0, kids.indexOf(l.id));
    const spread = Math.min(24, Math.max(0, (kids.length - 1) * 12));
    const off = spread === 0 ? 0 : -spread / 2 + (spread * idx) / (kids.length - 1);
    const a = _lvPort(p, 'R');
    const b = _lvPort(l, 'L');
    b[1] += off;
    const meDone = l.my && ['passed', 'done'].includes(l.my.status);
    const green = meDone && p.my && ['passed', 'done'].includes(p.my.status);
    const cx = (a[0] + b[0]) / 2;
    return `<path d="M${a[0]} ${a[1]} C${cx} ${a[1]}, ${cx} ${b[1]}, ${b[0]} ${b[1]}" fill="none" stroke="${green ? '#26a078' : '#7c8aa5'}" stroke-width="2.5" opacity="${meDone ? 1 : .8}" stroke-dasharray="${green ? '0' : '6 4'}" marker-end="url(#arrowLvF)" stroke-linecap="round"/>`;
  }).join('');
}

function _renderEdges() {
  const svg = document.querySelector('.lv-flow-edges');
  if (!svg) return;
  const W = svg.getAttribute('width') || 720, H = svg.getAttribute('height') || 460;
  svg.innerHTML = `<defs><marker id="arrowLvF" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0 0 L9 4.5 L0 9 Z" fill="#7c8aa5"/></marker></defs>${_lvEdges()}${_connLine()}`;
}

// 新建关卡（含方向默认位置）＋ 自动连线：左/上=成为本关的前置，右/下=成为本关的后续
function _levelNewAt(side, id) {
  const lv = _lvNode(id);
  if (!lv) return;
  const p = _lvPos(lv);
  let x = p.x, y = p.y;
  if (side === 'R') x = p.x + LV_W + 26;
  else if (side === 'B') y = p.y + LV_H + 26;
  else if (side === 'L') x = Math.max(0, p.x - LV_W - 26);
  else if (side === 'T') y = Math.max(0, p.y - LV_H - 26);
  // 目标格若已被同链其他卡片占用，向下逐格避让，避免新建卡与已有卡重叠
  const taken = (tx, ty) => _chainList().some((o) => {
    const q = _lvPos(o);
    return Math.abs(q.x - tx) < LV_W / 2 && Math.abs(q.y - ty) < LV_H / 2;
  });
  for (let i = 0; i < 20 && taken(x, y); i++) y += LV_H + 26;
  _flowEdit = true;
  const asPrev = side === 'L' || side === 'T';
  levelForm(null, {
    x, y, chain: lv.chain, chapter: lv.chapter,
    // 作为前置：承接本关原有的前置，创建后再把本关接到新关之后
    linkTo: asPrev ? (lv.requirePassId || '') : lv.id,
    prevOf: asPrev ? lv.id : '',
  });
}

// 拖拽连线：from → target（from 成为 target 的前置）
function levelConnect(fromId, targetId) {
  return API.request(`/levels/${targetId}/connect`, { method: 'POST', body: JSON.stringify({ targetId: fromId }) })
    .then(() => { _levelDetail = null; return API.load(); })
    .then(() => { render(); toast('已连接'); })
    .catch((err) => { toast(err && err.message ? err.message.replace('Bad Request: ', '') : '连线失败', true); });
}

function _flowLayoutAuto() {
  // 清除临时摆放后请求后端自动布局（重排 = 重置坐标）
  return API.request('/levels/positions', {
    method: 'POST',
    body: JSON.stringify({ positions: (db.levels || []).map((l) => ({ id: l.id, x: 0, y: 0 })) }),
  }).then(() => { Object.keys(_flowPos).forEach((k) => delete _flowPos[k]); return API.load(); }).then(() => { render(); toast('已重排，保存后生效'); });
}

function _flowSave() {
  const items = Object.entries(_flowPos).map(([id, p]) => ({ id, x: p.x, y: p.y }));
  if (!items.length) { toast('没有需要保存的改动'); return; }
  API.request('/levels/positions', { method: 'POST', body: JSON.stringify({ positions: items }) })
    .then(() => { _lvFlowDirty = false; Object.keys(_flowPos).forEach((k) => delete _flowPos[k]); return API.load(); })
    .then(() => { render(); toast('布局已保存'); });
}

function _connLine() {
  if (!_connDraft) return '';
  const f = _lvNode(_connDraft.fromId);
  if (!f) return '';
  const [x1, y1] = _lvPort(f, 'R');
  const x2 = _connDraft.x, y2 = _connDraft.y;
  const cx = (x1 + x2) / 2;
  return `<path d="M${x1} ${y1} C${cx} ${y1}, ${cx} ${y2}, ${x2} ${y2}" fill="none" stroke="#3b5c93" stroke-width="2" stroke-dasharray="5 4" opacity=".85" stroke-linecap="round" marker-end="url(#arrowLvF)"/>`;
}

function levelStatusChip(s) {
  return { pending: badge('待审核'), pass: badge('已通过'), done: badge('已通过'), reject: badge('未通过') }[s] || '';
}

// ── 详情 ──

function ensureLevelDetail(lid) {
  if (_levelDetail?.level?.id === lid) return Promise.resolve();
  _levelDetail = null;
  _levelDetailPending = true;
  return Promise.resolve()
    .then(() => (CONFIG.mode === 'api' ? API.request(`/levels/${lid}/detail`) : { level: findLevel(lid) || null, wall: [], tasks: [] }))
    .then((d) => { _levelDetail = d; })
    .catch((err) => { _levelDetail = { level: null, error: err.message }; })
    .finally(() => { _levelDetailPending = false; });
}

function levelOpen(lid) {
  modal('关卡详情', `<div class="empty">${icon('clock')}加载中…</div>`, '', null, '');
  ensureLevelDetail(lid).then(() => levelDetailModal(lid));
}

function _wallBox(w) {
  const img = (w.media || []).filter(_isImg).slice(0, 3);
  const vids = (w.media || []).filter(_isVid).slice(0, 1);
  const thumbs = img.map((m) => `<button class="media-img" data-action="task-lightbox" data-url="${esc(_murl(m.url))}" style="background-image:url('${esc(_murl(m.url))}')"></button>`).join('');
  return `<div class="wall-box"><div class="row"><strong>${esc(w.memberName)}</strong>${_stars(w.stars)}<small class="muted">${w.score} 分${w.featured ? ' · 精选' : ''}${w.firstPass ? ' · 首次通过' : ''}</small></div><div class="wall-media">${thumbs}${vids.map((m) => `<video src="${esc(_murl(m.url))}" controls preload="none" playsinline style="height:64px;border-radius:6px"></video>`).join('')}</div>${w.opinion ? `<small class="muted">${esc(w.opinion)}</small>` : ''}</div>`;
}

function levelDetailModal(lid) {
  if (_levelDetailPending) {
    modal('关卡详情', `<div class="empty">${icon('clock')}加载中…</div>`, '', null, '');
    return;
  }
  if (!_levelDetail || _levelDetail.level?.id !== lid) {
    levelOpen(lid);
    modal('关卡详情', `<div class="empty">${icon('clock')}加载中…</div>`, '', null, '');
    return;
  }
  const { level, wall = [], tasks = [], error } = _levelDetail;
  if (!level) {
    modal('关卡详情', `<p class="muted">${esc(error || '关卡不存在')}</p>`, '', null, '');
    return;
  }
  const canManage = can('action:level.manage');
  const canReview = can('action:level.review');
  const mine = level.my;
  const submitBtn = level.status === 'open' && (!mine || mine.status === 'rejected' || mine.status === 'pending')
    ? (mine ? (mine.status === 'pending' ? '' : btn('重新提交', 'level-submit', 'primary', `data-id="${level.id}"`)) : btn('提交完成成果', 'level-submit', 'primary', `data-id="${level.id}"`))
    : '';
  const infoRows = [
    ['技能线', level.chain],
    ['章节', level.chapter],
    ['满分', `${level.scoreLimit} 分`],
    ['档位规则', level.starsRule || '60·80 分档'],
    ['通过人数', `${level.passedCount} 人`],
    ['审核人', level.reviewers.map((r) => r.name).join('、') || '—'],
    ['状态', level.status === 'open' ? '开放中' : '已关闭'],
  ];
  const myBox = mine
    ? `<div class="wall-box ${mine.status}"><div class="row"><strong>我的进度</strong><span class="score-chip grade-${Math.max(0, Math.min(3, mine.stars || 0))}">${['', '一档', '二档', '三档'][Math.max(0, Math.min(3, mine.stars || 0))] || (mine.status === 'pending' ? '待评定' : mine.status === 'rejected' ? '未通过' : '')}</span><small class="muted">${mine.status === 'passed' || mine.status === 'done' ? mine.score + ' 分' : (mine.status === 'rejected' ? '未通过，可重新提交' : '待审核中')}</small></div>${mine.note ? `<small class="muted">${esc(mine.note)}</small>` : ''}</div>`
    : '';
  const wallBox = wall.length ? wall.map(_wallBox).join('') : '<div class="empty small">${icon}暂无通过记录</div>'.replace('${icon}', icon('trophy'));
  const taskRows = tasks.length
    ? tasks.map((t) => `<div class="todo"><span class="todo-icon ${t.status === 'done' ? '' : 'orange'}">${icon('task')}</span><div>${stack(t.title, `${t.id} · ${t.assigneeName || '待分配'}${t.score ? ' · ' + t.score + '分' : ''}`)}${(t.media && t.media.length) ? `<div class="lv-task-thumbs">${t.media.filter(_isImg).slice(0, 2).map((m) => `<button class="media-img" data-action="task-lightbox" data-url="${esc(_murl(m.url))}" style="width:52px;height:40px;background-image:url('${esc(_murl(m.url))}')" title="${esc(m.name)}"></button>`).join('')}</div>` : ''}</div>${recordButton('详情', 'task-detail', t.id)}</div>`).join('')
    : '<div class="empty small">${icon}本关暂无任务</div>'.replace('${icon}', icon('task'));
  const manageBox = canManage
    ? `<section class="lv-sec"><div class="sub-head"><strong>关卡配置</strong><span class="small muted">分数/星级/前置可改</span></div><div class="row" style="gap:8px;margin-top:10px">${btn('编辑信息', 'level-edit', '', `data-id="${level.id}"`)}${btn('挂接任务', 'level-link-task', '', `data-id="${level.id}"`)}${btn('增删审核人', 'level-reviewers', '', `data-id="${level.id}"`)}${level.status === 'open' ? btn('关闭', 'level-toggle', '', `data-id="${level.id}"`) : btn('开放', 'level-toggle', '', `data-id="${level.id}"`)}${btn('删除', 'level-delete', 'danger', `data-id="${level.id}"`)}</div></section>`
    : '';
  const reviewRow = canReview
    ? `<section class="lv-sec"><div class="row between"><strong>待我审核</strong>${btn('去审核', 'level-review-center')}</div></section>`
    : '';
  modal(
    `关卡 · ${esc(level.title)}`,
    `<div class="lv-detail">${details(infoRows)}${manageBox}${myBox}${submitBtn ? `<div class="lv-sec">${submitBtn}</div>` : ''}<section class="lv-sec"><div class="sub-head"><strong>关卡任务</strong><small>${tasks.length} 件</small></div>${taskRows}</section><section class="lv-sec"><div class="sub-head"><strong>通过墙</strong><small>${wall.length} 人</small></div>${wallBox}</section>${reviewRow}</div>`,
    '',
    null,
    '',
  );
}

// ── 提交 / 审核人 / 配置 ──

function levelSubmit(lid) {
  modal(
    '提交成果',
    `<div class="notice">上传完成截图或视频（可选，单文件 ≤40MB），并留一句完成说明。</div><div class="field" style="margin-top:14px"><label>完成图 / 视频</label><input type="file" name="file" id="lv-file" accept=".jpg,.jpeg,.png,.gif,.webp,.mp4,.mov,image/*,video/*"></div><div class="field" style="margin-top:14px"><label>完成说明</label><textarea name="note" maxlength="512" style="min-height:80px"></textarea></div>`,
    '提交审核',
    async (f) => {
      const file = f.get('file') || document.querySelector('#lv-file')?.files?.[0];
      const note = (f.get('note') || '').trim();
      requirePermission(file || note, '请上传完成图/视频或填写说明');
      if (file) requirePermission(file.size <= 40 * 1024 * 1024, '文件不能超过 40MB');
      const fd = new FormData();
      fd.append('note', note);
      if (file) fd.append('file', file);
      await API.request(`/levels/${lid}/submit`, { method: 'POST', body: fd });
      _levelDetail = null;
      invalidateProfile();
      await API.load();
      document.querySelector('#modal')?.close();
      render();
      toast('已提交，等待审核');
    },
  );
}

function levelReviewForm(lid) {
  const lv = findLevel(lid);
  requirePermission(lv, '关卡不存在');
  modal(
    '审核通过',
    `<div class="field"><label>选择成员</label><select name="memberId" id="lv-rv-mid">${((db.members || []).filter((m) => m.active)).map((m) => `<option value="${esc(m.id)}">${esc(m.name)}</option>`).join('')}</select></div><div class="form-grid" style="margin-top:14px">${selectField('决策', 'decision', [['pass', '通过'], ['reject', '未通过']], 'pass')}${field('得分', 'score', Math.floor((lv?.scoreLimit || 100) * 0.8), 'number', `min="0" max="${lv?.scoreLimit || 100}"`)}</div><label class="check-label" style="margin-top:12px"><input type="checkbox" name="featured"> 精选作品（上榜置顶）</label><div class="field" style="margin-top:12px"><label>审核意见</label><textarea name="opinion" maxlength="2000" style="min-height:80px"></textarea></div>`,
    '确认',
    async (f) => {
      const decision = f.get('decision');
      const payload = { memberId: f.get('memberId'), decision, featured: !!f.get('featured'), opinion: f.get('opinion') };
      if (decision === 'pass') payload.score = Number(f.get('score') || 0);
      await API.request(`/levels/${lid}/review`, { method: 'POST', body: JSON.stringify(payload) });
      _levelDetail = null;
      invalidateProfile();
      await API.load();
      document.querySelector('#modal')?.close();
      render();
      toast(decision === 'pass' ? '已通过并打分' : '已标记未通过');
    },
  );
}

function levelReviewCenter() {
  const pending = (db.levels || []).filter((l) => l.my && l.my.status === 'pending');
  modal(
    '关卡审核',
    pending.length
      ? `<div class="notice">待我处理的关卡：${pending.length} 个</div><div style="margin-top:12px">${pending.map((l) => `<button class="text-btn" data-action="level-open" data-id="${esc(l.id)}">${esc(l.title)}</button><span class="muted small"> · 待审核</span><br>`).join('')}</div>`
      : '<div class="empty small">${icon}暂无待审核关卡</div>'.replace('${icon}', icon('shield')),
    '',
    null,
    '',
  );
}

function levelForm(id = null, preset = null) {
  const lv = id ? findLevel(id) : null;
  const chain = lv?.chain || preset?.chain || '51单片机';
  const chapter = lv?.chapter || preset?.chapter || '基础';
  modal(
    id ? '编辑关卡' : '新建关卡',
    `<div class="form-grid">${field('关卡名称 *', 'title', lv?.title || '', 60)}${selectField('技能线', 'chain', LEVEL_CHAINS.map((c) => [c, c]), chain)}${selectField('章节', 'chapter', [['基础', '基础'], ['进阶', '进阶'], ['大师', '大师']], chapter)}${field('满分 / 每关分数（可后台改）', 'scoreLimit', lv?.scoreLimit ?? 100, 'number', 'min="1" max="1000"')}${field('星级阈值（分号分隔，如 60,80）', 'starsRule', lv?.starsRule || '60,80', 40)}${selectField('状态', 'status', LEVEL_STATUS, lv?.status || 'open')}${preset ? '' : ''}<div class="field" style="grid-column:1/-1"><label>关卡说明</label><textarea name="description" maxlength="2000" style="min-height:90px">${esc(lv?.description || '')}</textarea></div></div>`,
    id ? '保存' : '创建',
    async (f) => {
      const data = {
        title: f.get('title').trim(), chain: f.get('chain'), chapter: f.get('chapter'),
        scoreLimit: Number(f.get('scoreLimit') || 100), starsRule: f.get('starsRule'),
        status: f.get('status'), description: f.get('description'),
      };
      requirePermission(data.title, '请填写关卡名称');
      let nid = id;
      if (id) {
        await API.request(`/levels/${id}/update`, { method: 'POST', body: JSON.stringify(data) });
      } else {
        if (preset) {
          data.pos = { x: preset.x ?? 0, y: preset.y ?? 0 };
          data.linkTo = preset.linkTo || '';
        }
        const r = await API.request('/levels/create', { method: 'POST', body: JSON.stringify(data) });
        nid = r && r.id;   // API.request 已解包 data.data
        // 作为某关的前置新建：创建后把该关接到新关之后
        if (nid && preset.prevOf) {
          await API.request(`/levels/${preset.prevOf}/connect`, { method: 'POST', body: JSON.stringify({ targetId: nid }) });
        }
      }
      await API.load();
      _levelDetail = null;
      document.querySelector('#modal')?.close();
      render();
      toast(id ? '关卡已更新' : '关卡已创建');
    },
  );
}

function levelLinkTask(lid) {
  const linked = new Set(((db.levels || []).find((l) => l.id === lid)?.tasksLink) || []);
  const freeTasks = (db.tasks || []).filter((t) => !linked.has(t.id));
  modal(
    '挂接关卡任务',
    `<div class="notice">把已有任务挂到本关，任务提交/审核沿用任务系统。</div><div class="field" style="margin-top:14px"><label>选择任务</label><select name="taskId">${freeTasks.map((t) => `<option value="${esc(t.id)}">${esc(t.id)} · ${esc(t.title)}</option>`).join('') || '<option value="">暂无可挂任务（先到任务看板创建）</option>'}</select></div><div class="field" style="margin-top:12px">${selectField('类型', 'kind', [['main', '主线'], ['bonus', '加分']], 'main')}</div>`,
    '挂接',
    async (f) => {
      const taskId = f.get('taskId');
      requirePermission(taskId, '请选择任务');
      await API.request(`/levels/${lid}/tasks`, { method: 'POST', body: JSON.stringify({ taskId, kind: f.get('kind') }) });
      _levelDetail = null;
      await API.load();
      document.querySelector('#modal')?.close();
      render();
      toast('任务已挂接');
    },
  );
}

function levelReviewers(lid) {
  const lv = findLevel(lid);
  const list = lv?.reviewers || [];
  const memberIds = list.map((r) => r.memberId);
  modal(
    '关卡审核人',
    `<div class="sub-head"><strong>当前审核人</strong><small>${list.length} 人</small></div><div style="margin:10px 0">${list.map((r) => `<div class="row between"><span>${esc(r.name)}</span><button class="text-btn danger-text" data-action="level-reviewer-remove" data-id="${esc(lv.id)}:${esc(r.memberId)}">移除</button></div>`).join('') || '<div class="empty small">${icon}暂无审核人</div>'.replace('${icon}', icon('shield'))}</div><div class="field" style="margin-top:14px"><label>新增审核人</label><select id="lv-rv-add" name="memberId">${((db.members || []).filter((m) => m.active && !memberIds.includes(m.id))).map((m) => `<option value="${esc(m.id)}">${esc(m.name)}</option>`).join('') || '<option value="">无可用成员</option>'}</select></div>`,
    '添加',
    async (f) => {
      const mid = f.get('memberId');
      requirePermission(mid, '请选择成员');
      await API.request(`/levels/${lid}/reviewers`, { method: 'POST', body: JSON.stringify({ memberId: mid }) });
      _levelDetail = null;
      await API.load();
      document.querySelector('#modal')?.close();
      render();
      toast('审核人已添加');
    },
  );
  // 「移除」按钮复用 data-action 委托，在 FORM_ACTIONS 注册
}

function findLevel(id) {
  return (db.levels || []).find((l) => l.id === id) || null;
}

const LEVELS_ACTIONS = {
  'level-chain': (c) => {
    _levelChain = c;
    _lvFlowDirty = false;
    Object.keys(_flowPos).forEach((k) => delete _flowPos[k]);
    _connDraft = null;
    _flowEdit = false;
    render();
  },
  'lv-flow-toggle': () => { _flowEdit = !_flowEdit; render(); },
  'lv-flow-auto': () => _flowLayoutAuto(),
  'lv-flow-save': () => _flowSave(),
  'level-open': (id) => levelDetailModal(id),
  'level-new': () => levelForm(),
  'level-edit': (id) => levelForm(id),
  'level-delete': (id) => confirmation('删除关卡', '确认删除该关卡？相关提交通过记录将一并删除。', `/levels/${id}/delete`, {}, () => { _levelDetail = null; }),
  'level-toggle': (id) => API.request(`/levels/${id}/update`, { method: 'POST', body: JSON.stringify({ status: findLevel(id)?.status === 'open' ? 'closed' : 'open' }) }).then(async () => { _levelDetail = null; await API.load(); render(); }),
  'level-submit': (id) => levelSubmit(id),
  'level-review': (id) => levelReviewForm(id),
  'level-review-center': () => levelReviewCenter(),
  'level-link-task': (id) => levelLinkTask(id),
  'level-reviewers': (id) => levelReviewers(id),
  'level-reviewer-remove': (payload) => {
    const [lid, mid] = String(payload).split(':');
    return API.request(`/levels/${lid}/reviewers/${mid}`, { method: 'POST', body: JSON.stringify({}) }).then(async () => { _levelDetail = null; await API.load(); render(); toast('审核人已移除'); });
  },
};
window.LEVELS_ACTIONS = LEVELS_ACTIONS;
window.levelsPage = levelsPage;

// 画布拖拽/点击协调。
// 关键：app.js 的全局 `[data-action]` 委托挂在 document 的冒泡阶段；
// 若在同一节点用 stopPropagation() 是拦不住它的（同节点监听器照常执行），
// 因此这里用 **捕获阶段** + stopImmediatePropagation，先于 app.js 吃掉画布内的点击。
function _swallowClick(e) {
  e.preventDefault();
  e.stopImmediatePropagation();
}

document.addEventListener('pointerdown', (e) => {
  if (!document.querySelector('.lv-flow-canvas')) return;
  if (e.target.closest('.lv-flow-node, .lv-port')) _DRAG_BIND(e);
});

document.addEventListener('click', (e) => {
  const canvas = e.target.closest ? e.target.closest('.lv-flow-canvas') : null;
  const node = e.target.closest ? e.target.closest('.lv-flow-node') : null;
  if (!canvas && !node) return;
  // 拖拽落定后的余波（含合成出的双击第二击）：只吞这一次，不打开详情
  if (_sinkUntil > Date.now()) {
    _sinkUntil = 0;
    _justDragged = false;
    _swallowClick(e);
    return;
  }
  if (!_flowEdit) return;         // 查看态：不干预，交给 app.js 打开关卡详情
  _swallowClick(e);               // 编辑态：画布内点击一律不进详情
  if (!node) return;
  const port = e.target.closest('.lv-port');
  if (!port) return;
  const side = port.dataset.flowSide, id = port.dataset.id;
  if (port.dataset.flowAction === 'del') {
    // L：断开本关的前置（清掉自己的 require_pass）；R：断开本关的后续（清掉后续的 require_pass）
    const target = side === 'R'
      ? (db.levels || []).find((l) => l.id !== id && l.requirePassId === id)?.id
      : id;
    if (!target) { toast('未找到对应连线', true); return; }
    API.request(`/levels/${target}/connect`, { method: 'POST', body: JSON.stringify({ targetId: '' }) })
      .then(async () => { _levelDetail = null; await API.load(); render(); toast('已断开连线'); })
      .catch((err) => toast(err && err.message ? err.message.replace('Bad Request: ', '') : '断开失败', true));
  } else {
    _levelNewAt(side, id);
  }
}, true);

// ── 成长档案（成员详情「成长」区 / 全局共用）──

const _pdats = {};

function invalidateProfile(mid) {
  if (mid) delete _pdats[mid];
  else for (const k of Object.keys(_pdats)) delete _pdats[k];
}
window.invalidateProfile = invalidateProfile;

function memberProfile(mid, force) {
  if (!force && _pdats[mid]) return Promise.resolve(_pdats[mid]);
  if (mid === me()?.id && db.myProfile) {
    _pdats[mid] = db.myProfile;
    return Promise.resolve(db.myProfile);
  }
  if (CONFIG.mode !== 'api') return Promise.resolve(_degradedProfile(mid));
  return API.request(`/levels/member/${mid}/profile`)
    .then((d) => { _pdats[mid] = d; return d; })
    .catch(() => { _pdats[mid] = _degradedProfile(mid); return _pdats[mid]; });
}

function _degradedProfile(mid) {
  // 接口不可用时的兜底：只展示头衔与近期通过记录，徽章隐藏
  const m = member(mid);
  const mine = (db.levels || []).filter((l) => l.my && ['passed', 'done'].includes(l.my.status));
  return {
    exp: m?.exp ?? 0, rankTitle: rankTitle(m?.exp ?? 0), passCount: mine.length,
    stars: mine.reduce((s, l) => s + (l.my?.stars || 0), 0), chains: {}, firstPassCount: 0,
    badges: [], recent: mine.map((l) => ({ levelId: l.id, title: l.title, chain: l.chain,
      chapter: l.chapter, score: l.my?.score || 0, stars: l.my?.stars || 0 })).slice(0, 6),
  };
}

function rankTitle(exp) {
  if (exp >= 1500) return '大师';
  if (exp >= 600) return '专家';
  if (exp >= 200) return '工匠';
  return '学员';
}

function rankNext(exp) {
  if (exp >= 1500) return null;
  if (exp >= 600) return 1500;
  if (exp >= 200) return 600;
  return 200;
}

function _expLine(exp, title) {
  const next = rankNext(exp);
  const base = next ? (next === 200 ? 0 : next === 600 ? 200 : 600) : 600;
  const pct = next ? Math.min(100, Math.round(((exp - base) / (next - base)) * 100)) : 100;
  return `<div class="exp-line"><span class="exp-pct">${pct}%</span><div class="exp-track"><span style="width:${Math.max(4, Math.min(100, pct))}%"></span></div><small class="muted">${next ? `${title || rankTitle(exp)} → ${rankTitle(next)} · 还差 ${next - exp} EXP` : '已达成最高水平'}</small></div>`;
}

function _badgeWall(badges) {
  if (!Array.isArray(badges) || !badges.length) return '<div class="empty small">暂未获得荣誉标章，完成关卡即可点亮。</div>';
  return `<div class="bdg-grid">${badges.map((b) => `<span class="bdg-tile${b.earned ? ' earned' : ''}${b.tier ? ' tier' + b.tier : ''}" title="${esc(b.desc)}">${icon(b.earned ? 'trophy' : 'lock')}<i>${esc(b.title)}</i></span>`).join('')}</div>`;
}

function _skillsRows(pd) {
  const chains = new Set([...(db.levels || []).map((l) => l.chain), ...Object.keys(pd.chainsProgress || {})]);
  const rows = [...chains].map((c) => {
    const ls = (db.levels || []).filter((l) => l.chain === c);
    const done = ls.filter((l) => l.my && ['passed', 'done'].includes(l.my.status)).length;
    const total = (pd.chainsProgress?.[c]?.total ?? ls.length) || 1;
    return `<div class="skill-row"><span class="skill-name">${esc(c)}</span><div class="skill-track"><span style="width:${Math.round((done / Math.max(total, 1)) * 100)}%"></span></div><small class="muted">${done} / ${total} 关${done >= total && total ? ' · 已完成本线' : ''}</small></div>`;
  });
  return rows.join('');
}

function _recentList(recent) {
  if (!Array.isArray(recent) || !recent.length) return '<div class="empty small">暂无通过记录</div>';
  return `<div class="rec-list">${recent.map((r) => `<div class="rec-item"><span class="score-chip grade-${Math.max(0, Math.min(3, r.stars || 0))}">${['', '一档', '二档', '三档'][Math.max(1, r.stars || 1)]}</span><div>${stack(r.title, `${esc(r.chain)}${r.firstPass ? ' · 首次通过' : ''}${r.featured ? ' · 精选' : ''}`)}</div><small class="muted">${r.score} 分</small><small class="muted">${r.reviewedAt ? fmt(r.reviewedAt, true) : ''}</small></div>`).join('')}</div>`;
}

function achievementsHTML(pd) {
  if (!pd) return `<div class="empty">${icon('trophy')}暂无成长档案</div>`;
  return `<div class="ach-grid"><section class="panel ach-panel"><div class="panel-head"><div><h2>水平 · 经验值</h2><p>每通过一关累计经验值，逐步进阶更高水平</p></div><span class="rank-chip">${esc(pd.rankTitle || rankTitle(pd.exp || 0))}</span></div><div class="ach-body">${_expLine(pd.exp || 0, pd.rankTitle || rankTitle(pd.exp || 0))}<div class="job-sum"><span><b>${pd.passCount || 0}</b><small>通过</small></span><span><b>${pd.stars || 0}</b><small>累计档位分</small></span><span><b>${pd.firstPassCount || 0}</b><small>首次通过</small></span></div></div></section><section class="panel ach-panel"><div class="panel-head"><div><h2>荣誉标章</h2><p>按技能线与累计掌握度点亮</p></div></div><div class="ach-body">${_badgeWall(pd.badges)}</div></section><section class="panel ach-panel"><div class="panel-head"><div><h2>技能线进度</h2><p>各技能线通过进度</p></div></div><div class="ach-body">${_skillsRows(pd)}</div></section><section class="panel ach-panel"><div class="panel-head"><div><h2>近期通过记录</h2><p>最近完成的关卡</p></div></div><div class="ach-body">${_recentList(pd.recent)}</div></section></div>`;
}

window.memberProfile = memberProfile;
window.achievementsHTML = achievementsHTML;
window.rankTitle = rankTitle;