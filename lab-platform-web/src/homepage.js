'use strict';

// 主页管理：编辑官网营销首页的文案与配图（仅 superadmin，权限点 page:homepage / action:homepage.edit）。
// 独立一页、独立拉数据（仿 permissions.js），不进入 workspace 快照；保存后官网刷新即生效。

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

function imagesPanel() {
  const cards = (_hp.images || [])
    .map(
      (img) => {
        const isVideo = img.type === 'video';
        const scale = Math.min(150, Math.max(80, Number(img.scale) || 100));
        const thumb = isVideo
          ? `<span class="hp-thumb-wrap" style="--pscale:${scale}%"><video class="hp-thumb" muted preload="none" src="${esc(img.url)}"></video><span class="hp-video-badge">▶ 视频</span></span>`
          : `<span class="hp-thumb-wrap" style="--pscale:${scale}%"><img class="hp-thumb" src="${esc(img.url)}" alt="" loading="lazy"></span>`;
        const typeTag = `<span class="badge">${isVideo ? '视频' : '图片'}${img.uploaded ? ' · 已自定义' : ''}</span>`;
        return `<div class="hp-img-card">
    ${thumb}
    <div class="hp-img-meta"><div class="row" style="gap:6px"><span class="mono">${esc(img.key)}</span>${typeTag}</div><em class="small muted">${esc(img.label)}</em></div>
    <input class="hp-alt" data-hp-alt="${esc(img.key)}" value="${esc(img.alt)}" maxlength="200" placeholder="alt 描述（图片位使用）">
    <div class="row hp-scale-row"><label class="small muted">缩放</label><input type="range" class="hp-scale" min="80" max="150" step="1" data-hp-scale="${esc(img.key)}" value="${scale}" aria-label="${esc(img.label)} 缩放"><span class="mono hp-scale-val" data-hp-scale-val="${esc(img.key)}">${scale}%</span>${btn('应用', 'hp-scale-save', 'small', `data-id="${esc(img.key)}"`)}</div>
    <div class="row hp-img-btns" style="gap:6px">${btn('更换媒体', 'hp-img-upload', 'small', `data-id="${esc(img.key)}"`)}${img.uploaded ? btn('恢复默认', 'hp-img-reset', 'small text', `data-id="${esc(img.key)}"`) : ''}</div>
  </div>`;
      },
    )
    .join('');
  return `<section class="panel"><div class="panel-head"><h2>配图（${(_hp.images || []).length} 位）</h2><em class="small muted">图片 ≤10MB(jpg/png/webp) / 视频 ≤40MB(mp4/webm)，互斥替换；拖动缩放滑块可调显示大小，点“应用”生效</em></div><div class="hp-gallery">${cards}</div></section>`;
}

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

async function saveScale(key) {
  const slider = document.querySelector(`[data-hp-scale="${key}"]`);
  const scale = slider ? Number(slider.value) : 100;
  try {
    await API.request('/homepage/scale', { method: 'POST', body: JSON.stringify({ key, scale }) });
    toast(`缩放已应用（${scale}%）`);
    refreshHp();
  } catch (e) {
    toast(e.message || '保存失败', true);
  }
}

// 滑块拖动即时预览（顶层委托一次，与 click 委托对称；页面重建后仍生效）
document.addEventListener('input', (e) => {
  const s = e.target && e.target.closest ? e.target.closest('.hp-scale') : null;
  if (!s) return;
  const pct = s.value + '%';
  const card = s.closest('.hp-img-card');
  if (card) {
    const w = card.querySelector('.hp-thumb-wrap');
    if (w) w.style.setProperty('--pscale', pct);
    const v = card.querySelector('.hp-scale-val');
    if (v) v.textContent = pct;
  }
});

window.HOMEPAGE_ACTIONS = {
  'hp-texts-save': () => saveTexts(),
  'hp-img-upload': (key) => uploadMedia(key),
  'hp-img-reset': (key) => resetImage(key),
  'hp-scale-save': (key) => saveScale(key),
};

window.homepagePage = homepagePage;