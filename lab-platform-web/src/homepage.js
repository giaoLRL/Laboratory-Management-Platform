'use strict';

// 主页管理：编辑官网营销首页的文案、配图与作品集（仅 superadmin，
// 权限点 page:homepage / action:homepage.edit）。独立一页、独立拉数据（仿 permissions.js），
// 不进入 workspace 快照；保存后官网刷新即生效。
//
// 三个 tab：
//   文案  —— data-hp 文本位
//   图片  —— 固定媒体位，按「目标比例 ar + 裁切 fit + 焦点 focus + 微缩放 zoom」管理，
//            上传图片先过裁剪层（按该位 ar 出图），预览盒与官网容器共用同一套 CSS 变量
//   作品集 —— 可增删/排序/隐藏的列表（原先是写死的 work-01~08 媒体位）
// 图片 tab 右侧常驻「实时预览」iframe（官网 /?preview=1），编辑即所见。

let _hp = null;
let _hpLoading = false;
let _hpWorks = null;        // 作品集草稿（渲染与提交都以它为准）
let _hpFocusKey = null;     // 最近操作的媒体位 key，用于在预览里描边定位
let _hpPane = true;         // 预览面板开关

async function ensureHp() {
  if (_hp || _hpLoading) return;
  _hpLoading = true;
  try {
    _hp = await API.request('/homepage');
    _hpWorks = (_hp.works || []).map((w) => ({ ...w }));
  } catch (e) {
    toast(e.message || '加载失败', true);
  } finally {
    _hpLoading = false;
  }
}

function refreshHp() {
  _hp = null;
  _hpWorks = null;
  ensureHp().then(() => render());
}

function homepagePage() {
  if (!_hp) {
    ensureHp().then(() => render());
    return `${heading('主页管理', '编辑官网首页文案与配图，保存后官网刷新即生效。', '', 'HOMEPAGE / 官网内容')}<section class="panel"><div class="empty">${icon('image')}加载中…</div></section>`;
  }
  const tabs = uiTab('homepage', [
    ['texts', '文案', () => textsPanel()],
    ['images', '图片', () => imagesPanel()],
    ['works', `作品集（${(_hpWorks || []).length}）`, () => worksPanel()],
  ]);
  return `<div class="page-fit">${heading('主页管理', '编辑官网首页文案与配图，保存后官网刷新即生效。', '', 'HOMEPAGE / 官网内容')}${tabs}</div>`;
}

function textsPanel() {
  const rows = (_hp.texts || [])
    .map(
      (t) => `<div class="hp-row"><span class="mono hp-key">${esc(t.key)}</span><label class="small muted hp-label">${esc(t.label)}</label><input class="hp-val" data-hp-key="${esc(t.key)}" value="${esc(t.value)}" maxlength="1000" aria-label="${esc(t.label)}"></div>`,
    )
    .join('');
  return `<section class="panel"><div class="panel-head"><h2>文案（${(_hp.texts || []).length} 项）</h2>${btn('保存文案', 'hp-texts-save', 'primary')}</div><div class="hp-list">${rows}</div></section>`;
}

// ══════════════════ 媒体位 ══════════════════

function hpClamp(v, min, max, dflt) {
  const n = Number(v);
  if (!Number.isFinite(n)) return dflt;
  return Math.min(max, Math.max(min, Math.round(n)));
}

function hpFocusGrid(fx, fy) {
  const cells = [];
  [0, 50, 100].forEach((y) => {
    [0, 50, 100].forEach((x) => {
      const on = x === fx && y === fy ? ' active' : '';
      cells.push(`<button type="button" class="hp-focus-dot${on}" data-fx="${x}" data-fy="${y}" aria-label="焦点 ${x}% / ${y}%"></button>`);
    });
  });
  return `<span class="hp-focus-grid" role="group" aria-label="焦点位置">${cells.join('')}</span>`;
}

function hpImageCard(img) {
  const spec = img.spec || {};
  const ar = spec.ar || [4, 3];
  const min = spec.min || [800, 600];
  const isVideo = img.type === 'video';
  // 写死裁切方式的位（二维码）以 spec 为准：它的线上样式不读 --hp-fit，DB 里的旧值不可信
  const fit = spec.fitLocked ? spec.fit : img.fit === 'contain' ? 'contain' : 'cover';
  const fx = hpClamp(img.focus_x, 0, 100, 50);
  const fy = hpClamp(img.focus_y, 0, 100, 50);
  const zoom = hpClamp(img.zoom, 100, 150, 100);
  const frame = `--hp-ar:${ar[0]}/${ar[1]};--hp-fit:${fit};--hp-focus-x:${fx}%;--hp-focus-y:${fy}%;--hp-zoom:${zoom / 100}`;
  const media = !img.url
    ? '<span class="hp-thumb-empty">未上传（手机端将完整显示横版素材）</span>'
    : isVideo
      ? `<video class="hp-thumb" muted preload="metadata" src="${esc(img.url)}"></video><span class="hp-video-badge">▶ 视频</span>`
      : `<img class="hp-thumb" src="${esc(img.url)}" alt="" loading="lazy">`;
  const canCrop = !isVideo && !!img.source_url; // 只对留着原图的位开放「重新裁剪」
  return `<div class="hp-img-card" data-hp-card="${esc(img.key)}" data-fit="${fit}" data-fx="${fx}" data-fy="${fy}" data-zoom="${zoom}" data-ar-w="${ar[0]}" data-ar-h="${ar[1]}" data-min-w="${min[0]}" data-min-h="${min[1]}">
    <span class="hp-thumb-wrap" style="${frame}">${media}</span>
    <div class="hp-img-meta"><div class="row" style="gap:6px"><span class="mono">${esc(img.key)}</span><span class="badge">${isVideo ? '视频' : '图片'}${img.uploaded ? ' · 已自定义' : ''}</span></div><em class="small muted">${esc(img.label)}</em></div>
    <div class="hp-spec"><span>目标 ${ar[0]}:${ar[1]} · 建议 ≥${min[0]}×${min[1]}</span><span class="hp-see">—</span></div>
    <input class="hp-alt" data-hp-alt="${esc(img.key)}" value="${esc(img.alt)}" maxlength="200" placeholder="alt 描述（图片位使用）">
    <div class="hp-frame">
      <div class="hp-frame-row"><span class="small muted hp-frame-label">裁切</span>${
        spec.fitLocked
          ? '<span class="small muted">固定「完整」· 该位不裁切</span>'
          : `<span class="hp-fit-switch"><button type="button" class="hp-fit-opt${fit === 'cover' ? ' active' : ''}" data-fit="cover">铺满</button><button type="button" class="hp-fit-opt${fit === 'contain' ? ' active' : ''}" data-fit="contain">完整</button></span>`
      }</div>
      <div class="hp-frame-row"><span class="small muted hp-frame-label">焦点</span>${hpFocusGrid(fx, fy)}</div>
      <div class="hp-frame-row"><span class="small muted hp-frame-label">缩放</span><input type="range" class="hp-zoom" min="100" max="150" step="1" value="${zoom}" aria-label="${esc(img.label)} 构图缩放"><span class="mono hp-zoom-val">${zoom}%</span></div>
    </div>
    <div class="row" style="gap:6px">${btn('应用构图', 'hp-frame-save', 'small', `data-id="${esc(img.key)}"`)}</div>
    <div class="row hp-img-btns" style="gap:6px">${btn('更换媒体', 'hp-img-upload', 'small', `data-id="${esc(img.key)}"`)}${canCrop ? btn('重新裁剪', 'hp-img-recrop', 'small', `data-id="${esc(img.key)}"`) : ''}${img.uploaded ? btn('恢复默认', 'hp-img-reset', 'small text', `data-id="${esc(img.key)}"`) : ''}</div>
  </div>`;
}

function imagesPanel() {
  const list = _hp.images || [];
  const pane = _hpPane
    ? `<aside class="hp-preview-pane"><div class="hp-preview-head"><span class="small muted">官网实时预览 · 编辑即所见</span><button type="button" class="btn small text" data-action="hp-pane-toggle">收起</button></div><iframe id="hpPreview" class="hp-preview-frame" src="/?preview=1" title="官网实时预览"></iframe></aside>`
    : `<aside class="hp-preview-pane hp-preview-off"><button type="button" class="btn small" data-action="hp-pane-toggle">展开官网预览</button></aside>`;
  return `<section class="panel"><div class="panel-head"><h2>配图（${list.length} 位）</h2><em class="small muted">每位有固定的目标比例：「铺满」按焦点裁到目标比例，「完整」整幅显示（可能留边）。上传图片会先按该位比例裁剪，图片 ≤10MB / 视频 ≤40MB；改完点「应用构图」生效。</em></div><div class="hp-split"><div class="hp-gallery">${list.map(hpImageCard).join('')}</div>${pane}</div></section>`;
}

// ══════════════════ 作品集 ══════════════════

function hpWorkRow(w, i) {
  const thumb = w.url
    ? `<img class="hp-work-thumb" src="${esc(w.url)}" alt="" loading="lazy">`
    : '<span class="hp-work-thumb hp-thumb-empty">无图<br>（官网暂不显示）</span>';
  return `<div class="hp-work" data-hp-work="${i}">
    ${thumb}
    <div class="hp-work-fields">
      <input class="hp-val" data-w-title value="${esc(w.title || '')}" maxlength="128" placeholder="作品名" aria-label="作品名">
      <input class="hp-val" data-w-tag value="${esc(w.tag || '')}" maxlength="64" placeholder="赛事标签（如 智能导航大赛）" aria-label="赛事标签">
    </div>
    <label class="hp-work-show small muted"><input type="checkbox" data-w-visible ${w.visible ? 'checked' : ''}> 显示</label>
    <div class="hp-work-ops">
      ${btn('换图', 'hp-work-img', 'small', `data-id="${i}"`)}
      ${btn('↑', 'hp-work-up', 'small', `data-id="${i}"`)}
      ${btn('↓', 'hp-work-down', 'small', `data-id="${i}"`)}
      ${w.uploaded ? btn('还原', 'hp-work-reset', 'small text', `data-id="${i}"`) : ''}
      ${btn('删除', 'hp-work-del', 'small text', `data-id="${i}"`)}
    </div>
  </div>`;
}

function worksPanel() {
  const list = _hpWorks || [];
  const spec = _hp.workSpec || { ar: [4, 3], min: [800, 600] };
  const rows = list.length ? list.map(hpWorkRow).join('') : `<div class="empty">${icon('image')}还没有作品，点「新增作品」添加</div>`;
  return `<section class="panel"><div class="panel-head"><h2>作品集（${list.length} 条）</h2><div class="row" style="gap:6px">${btn('新增作品', 'hp-work-add', 'small')}${btn('保存作品集', 'hp-works-save', 'primary')}</div></div><div class="hp-works-head"><em class="small muted">作品格统一 ${spec.ar[0]}:${spec.ar[1]}（建议 ≥${spec.min[0]}×${spec.min[1]}），上传的图会按该比例裁剪；顺序即官网顺序，取消「显示」则官网不展示但保留条目。</em></div><div class="hp-works">${rows}</div></section>`;
}

function hpSyncWorks() {
  document.querySelectorAll('[data-hp-work]').forEach((row) => {
    const w = _hpWorks[Number(row.dataset.hpWork)];
    if (!w) return;
    w.title = row.querySelector('[data-w-title]').value;
    w.tag = row.querySelector('[data-w-tag]').value;
    w.visible = row.querySelector('[data-w-visible]').checked;
  });
}

async function saveWorks() {
  if (!_hpWorks) return false;
  hpSyncWorks();
  try {
    const res = await API.request('/homepage/works', {
      method: 'POST',
      body: JSON.stringify({
        works: _hpWorks.map((w) => ({
          id: w.id || null, title: w.title, tag: w.tag, visible: w.visible !== false,
        })),
      }),
    });
    _hpWorks = (res.works || []).map((w) => ({ ...w }));
    _hp.works = _hpWorks;
    toast('作品集已保存，官网刷新后生效');
    return true;
  } catch (e) {
    toast(e.message || '保存失败', true);
    return false;
  }
}

async function addWork() {
  hpSyncWorks();
  _hpWorks = _hpWorks || [];
  _hpWorks.push({ id: null, title: '新作品', tag: '', alt: '', url: '', uploaded: false, visible: true });
  render();
  // 新条目没有 id，先落库拿到 id 再让管理员挑图，避免"加了但传不了图"
  if (await saveWorks()) {
    refreshHp();
    toast('已新增，点「换图」上传作品图');
  }
}

function moveWork(i, delta) {
  hpSyncWorks();
  const j = i + delta;
  if (j < 0 || j >= _hpWorks.length) return;
  const [w] = _hpWorks.splice(i, 1);
  _hpWorks.splice(j, 0, w);
  render();
}

// ══════════════════ 裁剪层（上传即裁剪） ══════════════════

let _crop = null;

function hpCropLayout() {
  if (!_crop) return;
  const stage = document.getElementById('hpCropStage');
  const img = document.getElementById('hpCropImg');
  if (!stage || !img || !_crop.srcW) return;
  _crop.vw = stage.clientWidth;
  _crop.vh = stage.clientHeight;
  const base = Math.max(_crop.vw / _crop.srcW, _crop.vh / _crop.srcH); // cover：始终铺满取景框
  const s = base * _crop.z;
  _crop.dw = _crop.srcW * s;
  _crop.dh = _crop.srcH * s;
  _crop.s = s;
  hpCropClamp();
}

function hpCropClamp() {
  const { vw, vh, dw, dh } = _crop;
  _crop.ox = Math.min(0, Math.max(vw - dw, _crop.ox));
  _crop.oy = Math.min(0, Math.max(vh - dh, _crop.oy));
}

function hpCropPaint() {
  if (!_crop) return;
  const img = document.getElementById('hpCropImg');
  if (!img) return;
  hpCropClamp();
  img.style.width = _crop.dw + 'px';
  img.style.height = _crop.dh + 'px';
  img.style.left = _crop.ox + 'px';
  img.style.top = _crop.oy + 'px';
  const out = document.getElementById('hpCropSize');
  if (out) {
    const size = hpCropOutSize();
    out.textContent = `导出 ${size.w}×${size.h}（原图 ${_crop.srcW}×${_crop.srcH}）`;
  }
}

// 导出尺寸：严格按取景框比例算，长边 ≤2560，避免触发 10MB 上限
function hpCropOutSize() {
  const [aw, ah] = _crop.ar;
  const rectW = _crop.vw / _crop.s;
  const rectH = _crop.vh / _crop.s;
  const longEdge = Math.min(2560, Math.max(rectW, rectH));
  const landscape = rectW >= rectH;
  return {
    w: Math.max(1, Math.round(landscape ? longEdge : longEdge * (aw / ah))),
    h: Math.max(1, Math.round(landscape ? longEdge * (ah / aw) : longEdge)),
  };
}

function hpCropInit() {
  const stage = document.getElementById('hpCropStage');
  const img = document.getElementById('hpCropImg');
  if (!stage || !img) return;
  _crop.vw = stage.clientWidth;
  _crop.vh = stage.clientHeight;
  if (!img.complete || !img.naturalWidth) {
    img.addEventListener('load', () => {
      _crop.srcW = img.naturalWidth;
      _crop.srcH = img.naturalHeight;
      hpCropLayout();
      hpCropPaint();
    }, { once: true });
    return;
  }
  _crop.srcW = img.naturalWidth;
  _crop.srcH = img.naturalHeight;
  hpCropLayout();
  hpCropPaint();
}

/**
 * 打开裁剪层。opts = { key, ar:[w,h], file?, srcUrl?, apply(blob, sourceFile?) }
 * 取景框比例 = 该位的目标比例，导出即目标比例，于是线上再也不会有"被裁"这一说。
 */
function hpOpenCrop(opts) {
  const [aw, ah] = opts.ar;
  _crop = { ar: opts.ar, z: 1, ox: 0, oy: 0, s: 1, dw: 0, dh: 0, vw: 0, vh: 0, srcW: 0, srcH: 0, src: null, file: opts.file || null, drag: null };
  const url = opts.file ? URL.createObjectURL(opts.file) : opts.srcUrl;
  _crop.src = url;
  modal(
    `裁剪配图 · ${opts.label || opts.key}`,
    `<div class="hp-crop"><div class="hp-crop-stage" id="hpCropStage" style="aspect-ratio:${aw}/${ah}"><img id="hpCropImg" alt="" src="${esc(url)}"><span class="hp-crop-grid"></span></div>
    <div class="hp-crop-ctl"><label class="small muted">缩放</label><input type="range" id="hpCropZoom" min="100" max="400" value="100" aria-label="裁剪缩放"><span class="mono small" id="hpCropSize">—</span></div>
    <p class="small muted hp-crop-tip">拖动图片调整取景（滚轮或滑块缩放）· 取景框比例 ${aw}:${ah} 即该位的目标比例，导出后线上不会被再裁</p></div>`,
    '上传裁剪结果',
    async () => {
      const blob = await hpCropExport();
      if (!blob) throw new Error('裁剪失败，请重试');
      await opts.apply(blob, opts.file);
      document.querySelector('#modal').close();
      toast('已更新，官网刷新后生效');
      refreshHp();
    },
  );
  requestAnimationFrame(() => {
    hpCropInit();
    const stage = document.getElementById('hpCropStage');
    if (!stage) return;
    const slider = document.getElementById('hpCropZoom');
    if (slider) {
      slider.addEventListener('input', () => hpCropZoomTo(Number(slider.value) / 100));
      slider.value = 100;
    }
    let dragging = null;
    stage.addEventListener('pointerdown', (e) => {
      if (!_crop || !_crop.srcW) return;
      dragging = { x: e.clientX, y: e.clientY, ox: _crop.ox, oy: _crop.oy };
      stage.setPointerCapture(e.pointerId);
      stage.classList.add('dragging');
    });
    stage.addEventListener('pointermove', (e) => {
      if (!dragging || !_crop) return;
      _crop.ox = dragging.ox + (e.clientX - dragging.x);
      _crop.oy = dragging.oy + (e.clientY - dragging.y);
      hpCropPaint();
    });
    const stop = () => { dragging = null; stage.classList.remove('dragging'); };
    stage.addEventListener('pointerup', stop);
    stage.addEventListener('pointercancel', stop);
    stage.addEventListener('wheel', (e) => {
      if (!_crop || !_crop.srcW) return;
      e.preventDefault();
      hpCropZoomTo(_crop.z * (e.deltaY < 0 ? 1.08 : 1 / 1.08));
    }, { passive: false });
  });
}

// 以取景框中心为锚点缩放，手感跟常用图片编辑器一致
function hpCropZoomTo(z) {
  if (!_crop) return;
  const next = Math.min(4, Math.max(1, z));
  const cx = (_crop.vw / 2 - _crop.ox) / _crop.s;
  const cy = (_crop.vh / 2 - _crop.oy) / _crop.s;
  _crop.z = next;
  hpCropLayout();
  _crop.ox = _crop.vw / 2 - cx * _crop.s;
  _crop.oy = _crop.vh / 2 - cy * _crop.s;
  hpCropPaint();
  const slider = document.getElementById('hpCropZoom');
  if (slider) slider.value = Math.round(next * 100);
}

async function hpCropExport() {
  if (!_crop || !_crop.srcW) return null;
  const img = document.getElementById('hpCropImg');
  const rectW = _crop.vw / _crop.s;
  const rectH = _crop.vh / _crop.s;
  const { w: outW, h: outH } = hpCropOutSize();
  const canvas = document.createElement('canvas');
  canvas.width = outW;
  canvas.height = outH;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(img, -_crop.ox / _crop.s, -_crop.oy / _crop.s, rectW, rectH, 0, 0, outW, outH);
  const blob = await new Promise((res) => canvas.toBlob(res, 'image/webp', 0.9));
  return blob && blob.size ? blob : null;
}

function hpPickFile(accept) {
  return new Promise((res) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = accept;
    input.onchange = () => res(input.files[0] || null);
    input.click();
  });
}

// ══════════════════ 实时预览 ══════════════════

function hpPreviewHint(show) {
  const pane = document.querySelector('.hp-preview-pane');
  if (!pane) return;
  const tip = pane.querySelector('.hp-preview-tip');
  if (!show) {
    if (tip) tip.remove();
    return;
  }
  if (tip) return;
  const html = '<p class="small muted hp-preview-tip">本地开发环境里同源托管的是管理端自身（官网静态站由生产 nginx 提供），这里显示的不是官网；预览效果请在生产环境的管理端查看。</p>';
  const head = pane.querySelector('.hp-preview-head');
  if (head) head.insertAdjacentHTML('afterend', html);
  else pane.insertAdjacentHTML('afterbegin', html);
}

function hpPreviewPost(extra) {
  const frame = document.getElementById('hpPreview');
  if (!frame || !frame.contentWindow) return;
  const images = {};
  (_hp.images || []).forEach((img) => {
    const card = document.querySelector(`.hp-img-card[data-hp-card="${img.key}"]`);
    images[img.key] = {
      type: img.type,
      url: img.url,
      alt: img.alt,
      fit: card ? card.dataset.fit : img.fit,
      focus_x: card ? Number(card.dataset.fx) : img.focus_x,
      focus_y: card ? Number(card.dataset.fy) : img.focus_y,
      zoom: card ? Number(card.dataset.zoom) : img.zoom,
    };
  });
  const text = {};
  document.querySelectorAll('.hp-val[data-hp-key]').forEach((i) => {
    text[i.dataset.hpKey] = i.value;
  });
  const works = (_hpWorks || []).map((w) => ({ url: w.url, title: w.title, tag: w.tag, alt: w.alt, visible: w.visible }));
  // 预览通道只传展示参数（无隐私数据），用 '*' 以兼容本地把 iframe 指向别的静态服务
  frame.contentWindow.postMessage({ type: 'hp-preview', images, text, works, focusKey: _hpFocusKey, ...(extra || {}) }, '*');
}



// ══════════════════ 预览盒绘制 ══════════════════

function hpPaint(card) {
  const wrap = card.querySelector('.hp-thumb-wrap');
  if (wrap) {
    wrap.style.setProperty('--hp-fit', card.dataset.fit);
    wrap.style.setProperty('--hp-focus-x', card.dataset.fx + '%');
    wrap.style.setProperty('--hp-focus-y', card.dataset.fy + '%');
    wrap.style.setProperty('--hp-zoom', String(Number(card.dataset.zoom) / 100));
  }
  card.querySelectorAll('.hp-fit-opt').forEach((b) => b.classList.toggle('active', b.dataset.fit === card.dataset.fit));
  card.querySelectorAll('.hp-focus-dot').forEach((b) => {
    b.classList.toggle('active', Number(b.dataset.fx) === Number(card.dataset.fx) && Number(b.dataset.fy) === Number(card.dataset.fy));
  });
  const val = card.querySelector('.hp-zoom-val');
  if (val) val.textContent = card.dataset.zoom + '%';
  hpSee(card);
  _hpFocusKey = card.dataset.hpCard;
  hpPreviewPost();
}

// 预计可见比例 = min(素材比例, 容器比例) / max(…)：cover 下正好等于画面保留的面积占比
function hpSee(card) {
  const out = card.querySelector('.hp-see');
  if (!out) return;
  const el = card.querySelector('.hp-thumb');
  const nw = (el && (el.naturalWidth || el.videoWidth)) || 0;
  const nh = (el && (el.naturalHeight || el.videoHeight)) || 0;
  if (!nw || !nh) {
    out.textContent = '预计可见 —';
    out.classList.remove('warn');
    return;
  }
  const tooSmall = Math.min(nw / Number(card.dataset.minW), nh / Number(card.dataset.minH)) < 1;
  if (card.dataset.fit === 'contain') {
    out.textContent = `素材 ${nw}×${nh} · 完整显示`;
    out.classList.toggle('warn', tooSmall);
    return;
  }
  const mediaAr = nw / nh;
  const boxAr = Number(card.dataset.arW) / Number(card.dataset.arH);
  const pct = Math.round((Math.min(mediaAr, boxAr) / Math.max(mediaAr, boxAr)) * 100);
  out.textContent = `素材 ${nw}×${nh} · 可见 ${pct}%`;
  out.classList.toggle('warn', pct < 85 || tooSmall);
}

// 缩略图尺寸就绪后算可见比例：load 不冒泡，必须用捕获阶段委托；
// 缓存命中的图片同样会派发 load，无需额外初扫。
['load', 'loadedmetadata'].forEach((evt) => {
  document.addEventListener(
    evt,
    (e) => {
      const el = e.target;
      // 预览 iframe 也是靠 load 事件触发首帧同步（每次重建都会重新触发）
      if (el && el.id === 'hpPreview') {
        // 本地开发时后端同源托管的是管理端自身（官网静态站由生产 nginx 的 location = / 提供），
        // 这里认一下 window.CONFIG 给出提示，免得把管理端页面当成"官网预览坏了"
        let selfApp = false;
        try {
          selfApp = !!(el.contentWindow && el.contentWindow.CONFIG);
        } catch (err) {
          selfApp = false; // 跨源读不到 = 它确实不是本项目页面
        }
        hpPreviewHint(selfApp);
        hpPreviewPost();
        return;
      }
      if (!el || !el.classList || !el.classList.contains('hp-thumb')) return;
      const card = el.closest('.hp-img-card');
      if (card) hpSee(card);
    },
    true,
  );
});

// 构图控件交互（顶层委托一次，与 click/submit 委托对称；页面重建后仍生效）
document.addEventListener('click', (e) => {
  if (!e.target || !e.target.closest) return;
  const card = e.target.closest('.hp-img-card');
  if (!card) return;
  const fitBtn = e.target.closest('.hp-fit-opt');
  if (fitBtn) {
    card.dataset.fit = fitBtn.dataset.fit;
    hpPaint(card);
    return;
  }
  const dot = e.target.closest('.hp-focus-dot');
  if (dot) {
    card.dataset.fx = dot.dataset.fx;
    card.dataset.fy = dot.dataset.fy;
    hpPaint(card);
  }
});

document.addEventListener('input', (e) => {
  const s = e.target && e.target.closest ? e.target.closest('.hp-zoom') : null;
  if (!s) return;
  const card = s.closest('.hp-img-card');
  if (!card) return;
  card.dataset.zoom = s.value;
  hpPaint(card);
});

// ══════════════════ 动作 ══════════════════

async function saveTexts() {
  const values = {};
  document.querySelectorAll('.hp-val[data-hp-key]').forEach((i) => {
    values[i.dataset.hpKey] = i.value;
  });
  try {
    await API.request('/homepage/texts', { method: 'POST', body: JSON.stringify({ values }) });
    toast('文案已保存，官网刷新后生效');
    refreshHp();
  } catch (e) {
    toast(e.message || '保存失败', true);
  }
}

async function uploadMedia(key) {
  const img = (_hp.images || []).find((x) => x.key === key) || {};
  const spec = img.spec || { ar: [4, 3] };
  const file = await hpPickFile('image/*,video/*');
  if (!file) return;
  const isVideo = /^video\//.test(file.type);
  if (isVideo) {
    if (file.size > 40 * 1024 * 1024) return toast('视频不能超过 40MB', true);
    if (!/\.(mp4|webm)$/i.test(file.name)) return toast('视频仅支持 mp4 / webm', true);
    return hpSendMedia(key, file, null);
  }
  if (!/^image\//.test(file.type)) return toast('请选择图片或视频文件', true);
  if (file.size > 25 * 1024 * 1024) return toast('原图请控制在 25MB 内（导出结果会自动压到长边 2560）', true);
  hpOpenCrop({ key, label: img.label, ar: spec.ar, file, apply: (blob) => hpSendMedia(key, blob, file) });
}

// 用后台留着的那张原图重新取景，不必再让管理员翻本地文件
function recropImage(key) {
  const img = (_hp.images || []).find((x) => x.key === key);
  if (!img) return;
  if (!img.source_url) return toast('这一位当时没留原图，请用「更换媒体」重新选图', true);
  const spec = img.spec || { ar: [4, 3] };
  hpOpenCrop({ key, label: img.label, ar: spec.ar, srcUrl: img.source_url, apply: (blob) => hpSendMedia(key, blob, null) });
}

async function hpSendMedia(key, blob, sourceFile) {
  const altEl = document.querySelector(`[data-hp-alt="${key}"]`);
  const fd = new FormData();
  fd.append('media', blob, 'media.webp');
  fd.append('key', key);
  fd.append('alt', (altEl && altEl.value) || '');
  if (sourceFile) fd.append('source', sourceFile); // 原图另存，供日后「重新裁剪」
  await API.request('/homepage/images', { method: 'POST', body: fd });
}

async function resetImage(key) {
  try {
    await API.request('/homepage/images/reset', { method: 'POST', body: JSON.stringify({ key }) });
    toast('已恢复默认图片');
    refreshHp();
  } catch (e) {
    toast(e.message || '重置失败', true);
  }
}

async function saveFrame(key) {
  const card = document.querySelector(`.hp-img-card[data-hp-card="${key}"]`);
  if (!card) return;
  const body = {
    key,
    fit: card.dataset.fit,
    focus_x: Number(card.dataset.fx),
    focus_y: Number(card.dataset.fy),
    zoom: Number(card.dataset.zoom),
  };
  try {
    await API.request('/homepage/frame', { method: 'POST', body: JSON.stringify(body) });
    toast('构图已应用，官网刷新后生效');
    refreshHp();
  } catch (e) {
    toast(e.message || '保存失败', true);
  }
}

async function uploadWorkImage(i) {
  const w = _hpWorks[Number(i)];
  if (!w) return;
  if (!w.id) {
    // 新条目先落库（拿到 id 才能挂图），成功后再挑文件
    if (!(await saveWorks())) return;
    refreshHp();
  }
  const file = await hpPickFile('image/*');
  if (!file) return;
  if (file.size > 25 * 1024 * 1024) return toast('原图请控制在 25MB 内', true);
  const spec = _hp.workSpec || { ar: [4, 3] };
  hpOpenCrop({
    key: `作品 ${w.title || ''}`.trim(),
    label: w.title,
    ar: spec.ar,
    file,
    apply: async (blob) => {
      const cur = _hpWorks[Number(i)];
      if (!cur || !cur.id) throw new Error('作品条目已变化，请刷新后重试');
      const fd = new FormData();
      fd.append('media', blob, 'work.webp');
      fd.append('id', cur.id);
      await API.request('/homepage/works/image', { method: 'POST', body: fd });
    },
  });
}

async function resetWorkImage(i) {
  const w = _hpWorks[Number(i)];
  if (!w || !w.id) return;
  try {
    await API.request('/homepage/works/reset', { method: 'POST', body: JSON.stringify({ id: w.id }) });
    toast('已还原为默认图');
    refreshHp();
  } catch (e) {
    toast(e.message || '还原失败', true);
  }
}

window.HOMEPAGE_ACTIONS = {
  'hp-texts-save': () => saveTexts(),
  'hp-img-upload': (key) => uploadMedia(key),
  'hp-img-recrop': (key) => recropImage(key),
  'hp-img-reset': (key) => resetImage(key),
  'hp-frame-save': (key) => saveFrame(key),
  'hp-pane-toggle': () => {
    _hpPane = !_hpPane;
    render();
  },
  'hp-works-save': () => saveWorks().then((okDone) => okDone && refreshHp()),
  'hp-work-add': () => addWork(),
  'hp-work-up': (i) => moveWork(Number(i), -1),
  'hp-work-down': (i) => moveWork(Number(i), 1),
  'hp-work-img': (i) => uploadWorkImage(i),
  'hp-work-reset': (i) => resetWorkImage(i),
  'hp-work-del': (i) => {
    hpSyncWorks();
    _hpWorks.splice(Number(i), 1);
    render();
    toast('已移除，点「保存作品集」生效');
  },
};

window.homepagePage = homepagePage;