'use strict';

// 主页管理：编辑官网营销首页的文案与配图（仅 superadmin，权限点 page:homepage / action:homepage.edit）。
// 独立一页、独立拉数据（仿 permissions.js），不进入 workspace 快照；保存后官网刷新即生效。
//
// 图片位按「目标比例 ar + 裁切 fit + 焦点 focus + 微缩放 zoom」管理：ar/min 来自后端
// IMAGE_DEFAULTS 的 spec（固定不可改，只能按它选素材），fit/focus/zoom 可编辑。
// 预览盒与官网容器共用同一套 CSS 变量（--hp-ar/--hp-fit/--hp-focus-x/y/--hp-zoom），
// 保证后台所见即线上所得（此前固定 4:3 预览 + 单一 scale 滑块是"后台没问题、线上被裁"的根因）。

let _hp = null;
let _hpLoading = false;

async function ensureHp() {
  if (_hp || _hpLoading) return;
  _hpLoading = true;
  try {
    _hp = await API.request('/homepage');
  } catch (e) {
    toast(e.message || '加载失败', true);
  } finally {
    _hpLoading = false;
  }
}

function refreshHp() {
  _hp = null;
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
    <div class="row hp-img-btns" style="gap:6px">${btn('更换媒体', 'hp-img-upload', 'small', `data-id="${esc(img.key)}"`)}${img.uploaded ? btn('恢复默认', 'hp-img-reset', 'small text', `data-id="${esc(img.key)}"`) : ''}</div>
  </div>`;
}

function imagesPanel() {
  const list = _hp.images || [];
  return `<section class="panel"><div class="panel-head"><h2>配图（${list.length} 位）</h2><em class="small muted">每位有固定的目标比例：「铺满」按焦点裁到目标比例，「完整」整幅显示（可能留边）。图片 ≤10MB(jpg/png/webp) / 视频 ≤40MB(mp4/webm)，互斥替换；改完点「应用构图」生效。</em></div><div class="hp-gallery">${list.map(hpImageCard).join('')}</div></section>`;
}

// ── 预览盒绘制：草稿值写进 CSS 变量，与官网容器同一套变量 ──
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

async function saveTexts() {
  const values = {};
  document.querySelectorAll('.hp-val').forEach((i) => {
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

function uploadMedia(key) {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/*,video/*';
  input.onchange = async () => {
    const file = input.files[0];
    if (!file) return;
    try {
      const isVideo = /^video\//.test(file.type);
      if (isVideo) {
        if (file.size > 40 * 1024 * 1024) throw new Error('视频不能超过 40MB');
        if (!/\.(mp4|webm)$/i.test(file.name)) throw new Error('视频仅支持 mp4 / webm');
      } else {
        if (!/^image\//.test(file.type)) throw new Error('请选择图片或视频文件');
        if (file.size > 10 * 1024 * 1024) throw new Error('图片不能超过 10MB');
      }
      const altEl = document.querySelector(`[data-hp-alt="${key}"]`);
      const fd = new FormData();
      fd.append('media', file);
      fd.append('key', key);
      fd.append('alt', (altEl && altEl.value) || '');
      await API.request('/homepage/images', { method: 'POST', body: fd });
      toast(isVideo ? '视频已更新' : '图片已更新');
      refreshHp();
    } catch (e) {
      toast(e.message || '上传失败', true);
    }
  };
  input.click();
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

window.HOMEPAGE_ACTIONS = {
  'hp-texts-save': () => saveTexts(),
  'hp-img-upload': (key) => uploadMedia(key),
  'hp-img-reset': (key) => resetImage(key),
  'hp-frame-save': (key) => saveFrame(key),
};

window.homepagePage = homepagePage;