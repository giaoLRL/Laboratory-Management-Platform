/* 具身智能实验室官网脚本（源码入仓：原 index.html 两段内联 <script> 拼接）*/
  // ═══ Toast ═══
  const toast = document.getElementById('toast');
  let toastTimer = null;
  function showToast(msg) {
    toast.textContent = msg; toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
  }
  // ═══ 媒体灯箱：配图/视频点击查看大图，Esc / 点击遮罩关闭 ═══
  const lightbox = document.getElementById('lightbox');
  const lightboxImg = document.getElementById('lightboxImg');
  const lightboxVideo = document.getElementById('lightboxVideo');
  function openLightbox(el) {
    if (!lightbox || !el) return;
    if (el.tagName === 'VIDEO') {
      lightboxImg.style.display = 'none';
      var v = lightboxVideo;
      v.removeAttribute('src'); // 强制重新加载新源
      v.src = el.currentSrc || el.src;
      v.muted = true; // 无用户手势兜底 + 视频位静音语义
      v.style.display = 'block';
      var p = v.play(); if (p) p.catch(function () {});
    } else {
      if (lightboxVideo) { lightboxVideo.pause(); lightboxVideo.removeAttribute('src'); lightboxVideo.style.display = 'none'; }
      lightboxImg.style.display = 'block';
      lightboxImg.src = el.currentSrc || el.src;
      lightboxImg.alt = el.alt || '';
    }
    lightbox.classList.add('open');
  }
  function closeLightbox() {
    if (lightboxVideo) { lightboxVideo.pause(); lightboxVideo.removeAttribute('src'); }
    if (lightbox) lightbox.classList.remove('open');
  }
  if (lightbox) {
    // 事件委托：兼容首页动态拉取后替换出的 video/img（一次性遍历绑定会漏掉动态元素）
    document.addEventListener('click', function (e) {
      var el = e.target && e.target.closest ? e.target.closest('.lightboxable') : null;
      if (!el) return;
      e.stopPropagation();
      openLightbox(el);
    });
    lightbox.addEventListener('click', function (e) {
      if (e.target === lightbox || e.target.classList.contains('lb-close')) closeLightbox();
    });
    addEventListener('keydown', function (e) { if (e.key === 'Escape') closeLightbox(); });
  }

  // ═══ 移动端菜单 ═══
  const burger = document.getElementById('navBurger');
  const mobileMenu = document.getElementById('mobileMenu');
  if (burger && mobileMenu) {
    burger.addEventListener('click', () => mobileMenu.classList.toggle('open'));
    mobileMenu.querySelectorAll('a').forEach(a => a.addEventListener('click', () => mobileMenu.classList.remove('open')));
  }

  // ═══ Hero 背景视频兜底：个别环境拦截 autoplay，首次交互后重试播放 ═══
  document.querySelectorAll('.hero-media video.bg').forEach(v => {
    const p = v.play();
    if (p) p.catch(() => {
      const resume = () => { v.play().catch(() => {}); };
      document.addEventListener('pointerdown', resume, { once: true });
      document.addEventListener('wheel', resume, { once: true, passive: true });
      document.addEventListener('keydown', resume, { once: true });
    });
  });

  // ═══ 关键：入场动画结束后摘除动画 ═══
  // 带 transform/opacity 动画（fill: forwards）的元素在 Chrome 中会成为渲染隔离层，
  // 导致内部按钮的 backdrop-filter 采样不到背后视频，玻璃效果失效。
  // animationend 后清除动画，让按钮恢复对视频层的磨砂采样。
  ['.hero-text', '.hero .button-group'].forEach(sel => {
    const el = document.querySelector(sel);
    if (!el) return;
    // 摘除动画的同时，用内联样式钉住"已入场"状态，双保险防隐身
    const clear = () => {
      el.style.animation = 'none';
      el.style.opacity = '1';
      el.style.transform = 'none';
    };
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) clear();
    else el.addEventListener('animationend', clear, { once: true });
  });

  // ═══ 背景音乐：每次进入页面都显示中央启动卡，点击播放后消失；右下角按钮负责暂停/恢复 ═══
  (function () {
    const btn = document.getElementById('bgmBtn');
    const audio = document.getElementById('bgm');
    const gate = document.getElementById('bgmGate');
    if (!btn || !audio) return;
    audio.volume = 0.5;
    const icOn = btn.querySelector('.ic-on'), icOff = btn.querySelector('.ic-off');
    function setUI(playing) {
      btn.classList.toggle('playing', playing);
      icOn.style.display = playing ? '' : 'none';
      icOff.style.display = playing ? 'none' : '';
    }
    function hideGate() {
      if (!gate || gate.classList.contains('hide')) return;
      gate.classList.add('hide');
      setTimeout(() => gate.remove(), 600);
    }
    function startMusic() {
      audio.play().then(() => {
        setUI(true); hideGate();
      }).catch(() => showToast('背景音乐加载失败：请确认 assets/audio/bgm.mp3 已上传'));
    }
    btn.addEventListener('click', () => {
      if (audio.paused) startMusic();
      else { audio.pause(); setUI(false); }
    });
    audio.addEventListener('error', () => {
      btn.style.display = 'none'; hideGate();
      showToast('背景音乐文件缺失：请上传 assets/audio/bgm.mp3');
    });
    if (gate) {
      gate.addEventListener('click', startMusic);
      gate.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); startMusic(); }
      });
    }
  })();

  // ═══ 滚动渐入（进入视口 15% 且过底部 6% 缓冲才触发，动效更可见） ═══
  const io = new IntersectionObserver(entries => {
    entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('visible'); io.unobserve(e.target); } });
  }, { threshold: 0.15, rootMargin: '0px 0px -6% 0px' });
  // 动态配图逐张错峰浮现
  document.querySelectorAll('.news-photos').forEach(g => {
    [...g.querySelectorAll('img')].forEach((el, i) => {
      el.classList.add('reveal');
      el.style.transitionDelay = i * 0.12 + 's';
    });
  });
  document.querySelectorAll('.reveal').forEach(el => io.observe(el));

  // ═══ 板块内容错峰渐入 ═══
  document.querySelectorAll('.research-grid, .team-grid, .gallery-masonry, .charts-row, .showcase-track').forEach(grid => {
    [...grid.querySelectorAll('.reveal')].forEach((el, i) => {
      el.style.transitionDelay = (i % 6) * 0.08 + 's';
    });
  });

  // ═══ 数字滚动（≥10 自动带 + 号） ═══
  const cio = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (!e.isIntersecting) return; cio.unobserve(e.target);
      const target = +e.target.dataset.count, t0 = performance.now(), dur = 1200;
      (function tick(t) {
        const p = Math.min((t - t0) / dur, 1), ease = 1 - Math.pow(1 - p, 3);
        e.target.textContent = Math.round(target * ease) + (p < 1 ? '' : (target >= 10 ? '+' : ''));
        if (p < 1) requestAnimationFrame(tick);
      })(t0);
    });
  }, { threshold: 0.6 });
  document.querySelectorAll('[data-count]').forEach(el => cio.observe(el));

  // ═══ 展示区横向轮播 ═══
  (function () {
    const track = document.getElementById('sc-track');
    const prev = document.getElementById('sc-prev');
    const next = document.getElementById('sc-next');
    if (!track) return;
    let offset = 0;
    function maxOffset() { return Math.max(0, track.scrollWidth - track.clientWidth); }
    function stepSize() {
      const cards = track.querySelectorAll('.showcase-card');
      if (cards.length < 2) return 340;
      return cards[0].offsetWidth + 20;
    }
    function update() {
      track.style.transform = 'translateX(' + (-offset) + 'px)';
      prev.disabled = offset <= 0;
      next.disabled = offset >= maxOffset() - 2;
    }
    prev.addEventListener('click', () => { offset = Math.max(0, offset - stepSize()); update(); });
    next.addEventListener('click', () => { offset = Math.min(maxOffset(), offset + stepSize()); update(); });
    addEventListener('resize', update);
    // 触屏手势：手机上直接左右拖动轮播
    let sx = 0, so = 0, dragging = false;
    track.addEventListener('touchstart', e => {
      sx = e.touches[0].clientX; so = offset; dragging = true;
      track.style.transition = 'none'; // 拖动期间关闭过渡，跟手
    }, { passive: true });
    track.addEventListener('touchmove', e => {
      if (!dragging) return;
      const dx = sx - e.touches[0].clientX;
      const v = Math.max(-60, Math.min(maxOffset() + 60, so + dx));
      track.style.transform = 'translateX(' + (-v) + 'px)';
    }, { passive: true });
    track.addEventListener('touchend', e => {
      if (!dragging) return;
      dragging = false;
      track.style.transition = '';
      const dx = sx - e.changedTouches[0].clientX;
      if (Math.abs(dx) > 40) offset = Math.max(0, Math.min(maxOffset(), so + dx));
      update();
    });
    update();
  })();

  // ═══ 行业前景图表（条形图生长 + 折线绘制，进入视口触发） ═══
  (function () {
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const row = document.getElementById('chartsRow');
    if (!row) return;

    function playBars() {
      row.querySelectorAll('.bar-fill').forEach((bar, i) => {
        setTimeout(() => { bar.style.width = bar.dataset.w + '%'; }, i * 120);
      });
    }
    function playLine() {
      const wrap = document.getElementById('marketLine');
      if (!wrap) return;
      const path = wrap.querySelector('.line-path');
      if (reduced) {
        path.style.strokeDashoffset = '0';
        wrap.classList.add('animate');
        return;
      }
      path.style.transition = 'stroke-dashoffset 1.3s cubic-bezier(.66,0,.34,1) .2s';
      requestAnimationFrame(() => {
        path.style.strokeDashoffset = '0';
        setTimeout(() => wrap.classList.add('animate'), 1300);
      });
    }

    if (reduced) {
      row.querySelectorAll('.bar-fill').forEach(bar => { bar.style.width = bar.dataset.w + '%'; });
      const path = document.querySelector('#marketLine .line-path');
      if (path) path.style.strokeDashoffset = '0';
      const wrap = document.getElementById('marketLine');
      if (wrap) wrap.classList.add('animate');
      return;
    }

    const gio = new IntersectionObserver(entries => {
      entries.forEach(e => {
        if (!e.isIntersecting) return;
        gio.unobserve(e.target);
        playBars();
        playLine();
      });
    }, { threshold: 0.25 });
    gio.observe(row);
  })();

  // ══════════ 首屏强制翻页（仅第一页⇄第二页整屏翻动，其余自由滚动） ══════════
  (function () {
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const isTouch = matchMedia('(hover: none)').matches; // 触屏设备保留原生滚动
    if (reduced || isTouch) return;

    // 动画期间禁用 CSS 平滑滚动（避免与 rAF 动画叠加打架）
    document.documentElement.style.scrollBehavior = 'auto';

    const hero = document.querySelector('.hero');
    let boundary = 0;
    function measure() {
      // 用 getBoundingClientRect 取文档绝对位置（offsetTop 会受 position:relative 父级影响算错）
      boundary = hero.getBoundingClientRect().top + scrollY + hero.offsetHeight;
    }
    measure();
    addEventListener('resize', measure);
    addEventListener('load', measure);

    const DUR = 500; // 翻页时长
    let animating = false, cooldownUntil = 0;
    function easeInOut(t) { return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
    function animateScroll(to) {
      const from = scrollY, delta = to - from;
      if (Math.abs(delta) < 2) return;
      animating = true;
      const t0 = performance.now();
      (function tick(t) {
        const p = Math.min((t - t0) / DUR, 1);
        scrollTo(0, from + delta * easeInOut(p));
        if (p < 1) requestAnimationFrame(tick);
        else { animating = false; cooldownUntil = performance.now() + 150; }
      })(t0);
    }

    // 滚轮：第一页向下 → 强制翻到第二页；第二页顶部/已进入第一页范围向上 → 强制翻回第一页；其余自由滚动
    addEventListener('wheel', e => {
      const cur = scrollY;
      // 第二页内部：完全自由滚动，绝不拦截（冷却期也不拦截，避免自由区卡顿）
      if (cur > boundary + 4) {
        if (animating) e.preventDefault();
        return;
      }
      if (animating || performance.now() < cooldownUntil) { e.preventDefault(); return; }
      // 上翻：位于第二页顶部，或已滚入第一页范围 → 整屏翻回第一页顶部
      if (e.deltaY < 0) {
        if (cur > 4) { e.preventDefault(); animateScroll(0); }
        return;
      }
      // 下翻：仍在第一页 → 强制翻到第二页
      if (e.deltaY > 0 && cur < boundary - 4) {
        e.preventDefault();
        animateScroll(boundary);
      }
    }, { passive: false });

    // 键盘：上/下方向键与翻页键在首屏边界处同样走强制翻页
    addEventListener('keydown', e => {
      const down = ['ArrowDown', 'PageDown', ' '].includes(e.key);
      const up = e.key === 'ArrowUp' || e.key === 'PageUp';
      if (!down && !up) return;
      const cur = scrollY;
      if (up && cur <= boundary + 4 && cur > 4) {
        e.preventDefault();
        if (!animating) animateScroll(0);
      } else if (down && cur < boundary - 4) {
        e.preventDefault();
        if (!animating) animateScroll(boundary);
      }
    });

    // 导航 / 按钮锚点 → 跨首屏边界走翻页动画，其余平滑滚动
    document.querySelectorAll('a[href^="#"]').forEach(a => {
      a.addEventListener('click', e => {
        const id = a.getAttribute('href').slice(1);
        const el = id ? document.getElementById(id) : null;
        if (!el) return;
        e.preventDefault();
        if (!animating) {
          const to = el.getBoundingClientRect().top + scrollY;
          const crossing = scrollY < boundary - 4 && to >= boundary - 4;
          if (crossing) animateScroll(to);
          else el.scrollIntoView({ behavior: 'smooth' });
        }
        const mm = document.getElementById('mobileMenu');
        if (mm) mm.classList.remove('open');
      });
    });
  })();
/* 主页内容动态化：向管理平台后端拉取已发布的文案与配图并替换页面元素。
 * data-hp="<key>" 文本 / data-hp-img="<key>" 图片；接口不可用或超时时静默回退页面默认值（渐进增强）。 */
(function () {
  if (!/^https?:$/.test(location.protocol)) return; // file:// 本地预览直接跳过

  // 比例变量 --hp-ar 落在「框」上（卡片/格/招新图），裁切变量落在框上再继承给 img/video；
  // 其余媒体位（动态配图、二维码）的 CSS 把四个变量都读在元素自身，直接设在元素上。
  var FRAME_SEL = '.showcase-card, .g-item, .join-img';
  function applyFrame(node, m) {
    if (!m || !m.fit) return;
    var frame = (node.closest && node.closest(FRAME_SEL)) || node;
    frame.style.setProperty('--hp-fit', m.fit);
    frame.style.setProperty('--hp-focus-x', m.focus_x + '%');
    frame.style.setProperty('--hp-focus-y', m.focus_y + '%');
    frame.style.setProperty('--hp-zoom', String((Number(m.zoom) || 100) / 100));
  }
  // 手机竖版 Hero（hero.portrait）：只在 ≤767px 才注入 .hp-portrait 媒体元素（宽屏不加载
  // 手机素材，省流量/体积），命中时由 CSS 隐藏横版、竖版 cover 铺满；没上传竖版素材时
  // 元素根本不存在，回退到 CSS 的 contain（不裁主体）。
  var heroPortrait = null; // { m, u }
  var heroMQ = matchMedia('(max-width: 767px)');
  function paintHeroPortrait() {
    var host = document.querySelector('.hero-media');
    if (!host) return;
    var el = host.querySelector('.hp-portrait');
    if (!heroPortrait || !heroMQ.matches) {
      if (el) el.parentNode.removeChild(el);
      host.classList.remove('has-portrait');
      return;
    }
    var m = heroPortrait.m;
    var tag = m.type === 'video' ? 'VIDEO' : 'IMG';
    if (el && el.tagName !== tag) { el.parentNode.removeChild(el); el = null; }
    if (!el) {
      el = document.createElement(tag.toLowerCase());
      el.className = 'bg hp-portrait';
      if (tag === 'VIDEO') {
        el.muted = true; el.autoplay = true; el.loop = true;
        el.playsInline = true; el.preload = 'metadata';
      }
      host.appendChild(el);
    }
    host.classList.add('has-portrait'); // CSS 据此才隐藏横版素材
    if (el.getAttribute('src') !== heroPortrait.u) el.setAttribute('src', heroPortrait.u);
    if (m.alt) el.setAttribute('alt', m.alt);
    el.style.setProperty('--hp-focus-x', m.focus_x + '%');
    el.style.setProperty('--hp-focus-y', m.focus_y + '%');
    el.style.setProperty('--hp-zoom', String((Number(m.zoom) || 100) / 100));
  }
  if (heroMQ.addEventListener) heroMQ.addEventListener('change', paintHeroPortrait);

  var ctl, t;
  try { ctl = new AbortController(); } catch (e) { return; }
  t = setTimeout(function () { try { ctl.abort(); } catch (e) {} }, 8000);
  // 带时间戳绕过边缘缓存：编辑保存后官网刷新立即生效
  fetch('/api/homepage/public?v=' + Date.now(), { signal: ctl.signal, credentials: 'omit' })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (d) {
      clearTimeout(t);
      d = d && d.data ? d.data : d;
      if (!d || !d.text) return;
      var v = Date.now();
      Object.keys(d.text || {}).forEach(function (k) {
        var el = document.querySelector('[data-hp="' + k + '"]');
        if (el && typeof d.text[k] === 'string') el.textContent = d.text[k];
      });
      Object.keys(d.images || {}).forEach(function (k) {
        var m = d.images[k] || {};
        if (!m.url) return; // 空 URL = 该位没有素材（如未上传的 hero.portrait），保持页面默认
        // 无条件剥离旧 ?v= 再追加本次加载时间戳：seed 的 ?v=2、上传图裸 URL 一起覆盖，
        // 避免命中浏览器对 /assets/(30 天) 或边缘按 path 的旧缓存
        var u = m.url.split('?')[0] + '?v=' + v;
        if (k === 'hero.portrait') { heroPortrait = { m: m, u: u }; paintHeroPortrait(); return; }
        var node = document.querySelector('[data-hp-img="' + k + '"]');
        if (!node) return;
        if (m.type === 'video') {
          if (node.tagName === 'IMG') {
            // 图片位替换为视频位（静音循环自动播放，点击可放大带声播放）
            var vd = document.createElement('video');
            vd.className = node.className + ' lightboxable';
            vd.muted = true; vd.autoplay = true; vd.loop = true;
            vd.playsInline = true; vd.preload = 'metadata';
            vd.setAttribute('src', u);
            node.parentNode.replaceChild(vd, node);
            node = vd;
          } else if (node.tagName === 'VIDEO') {
            if (node.getAttribute('src') !== u) node.setAttribute('src', u);
          }
        } else if (node.tagName !== 'VIDEO') {
          if (node.getAttribute('src') !== u) node.setAttribute('src', u);
          if (m.alt) node.setAttribute('alt', m.alt);
        }
        applyFrame(node, m);
      });
    })
    .catch(function () { clearTimeout(t); }); // 失败/超时静默，保持页面默认内容
})();
