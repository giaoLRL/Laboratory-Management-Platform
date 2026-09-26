'use strict';
// 界面动效（克制版）：卡片浮现 + 统计数字滚动。
// - 位移 ≤24px、时长 ≤0.6s、单次播放不循环
// - 尊重 prefers-reduced-motion：系统开启减动效时完全跳过
// - 元素超过 60 个时降级为无动画（低性能设备）
function initAnimations() {
  if (typeof IntersectionObserver === 'undefined' || typeof MutationObserver === 'undefined') return;
  try {
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  } catch (e) {
    return;
  }
  const TARGETS = '.panel, .member-card, .task-card, .contest-card, .news-card, .competition-brief, .stat-value';
  const seen = new WeakSet();
  const io = new IntersectionObserver(
    (entries) => {
      for (const en of entries) {
        if (!en.isIntersecting) continue;
        const el = en.target;
        if (el.classList.contains('stat-value')) animateNumber(el);
        else el.classList.add('in');
        io.unobserve(el);
      }
    },
    { threshold: 0.15 },
  );
  function collect() {
    const all = document.querySelectorAll(TARGETS);
    if (all.length > 60) return; // 数据量过大：跳过动画
    all.forEach((el) => {
      if (seen.has(el) || el.closest('dialog')) return; // 弹窗内部不带动效，避免弹出卡顿/闪烁
      seen.add(el);
      el.classList.add('anim-target');
      io.observe(el);
    });
  }
  function animateNumber(el) {
    const node = el.childNodes[0];
    const raw = (node?.textContent || '').trim();
    // 文本型统计值（如「已打卡 / 未扫码」）不做数字滚动：否则 parseFloat 得到 NaN，
    // 会被兜底成 0 覆盖掉原文案
    if (!/^\d+(\.\d+)?$/.test(raw)) {
      el.classList.add('in');
      return;
    }
    const target = parseFloat(raw);
    const start = performance.now();
    const dur = 550;
    function tick(t) {
      const p = Math.min(1, (t - start) / dur);
      const val = Math.round(target * (1 - Math.pow(1 - p, 3)));
      node.textContent = String(val);
      if (p < 1) requestAnimationFrame(tick);
      else el.classList.add('in');
    }
    requestAnimationFrame(tick);
  }
  collect();
  const root = document.querySelector('#content') || document.body;
  const mo = new MutationObserver(() => queueMicrotask(collect));
  mo.observe(root, { childList: true, subtree: true });
}
document.addEventListener('DOMContentLoaded', initAnimations, { once: true });