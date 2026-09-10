/* ═══════════════════════════════════════════════════════════════
   lm-ui.js — 全站交互层（命令面板 ⌘K / AI 副驾驶 / 密度切换 /
   看板拖拽 / 投屏模式 / 表格筛选记忆）
   零依赖，全部通过 data-* 属性驱动，模板不写内联业务脚本。
   ═══════════════════════════════════════════════════════════════ */
(function () {
  'use strict';
  var BASE = window.LM_BASE_URL || '/plugins/lab-manager/';
  var CSRF = window.CSRF_TOKEN || '';

  function qs(sel, root) { return (root || document).querySelector(sel); }
  function qsa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function api(path) { return window.LM_BASE_PATH ? window.LM_BASE_PATH + path : path; }

  function postJSON(url, payload) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
      credentials: 'same-origin',
      body: JSON.stringify(payload || {})
    }).then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok, status: r.status, data: d }; }); });
  }

  /* ── 1. 表格密度切换（localStorage 持久化） ─────────────── */
  function initDensity() {
    var KEY = 'lm_table_density';
    var saved = 'comfortable';
    try { saved = localStorage.getItem(KEY) || 'comfortable'; } catch (e) { /* ignore */ }
    document.body.classList.toggle('lm-density--compact', saved === 'compact');
    qsa('[data-lm-density-toggle]').forEach(function (btn) {
      if (btn.dataset.lmBound === '1') return;
      btn.dataset.lmBound = '1';
      btn.addEventListener('click', function () {
        var compact = !document.body.classList.contains('lm-density--compact');
        document.body.classList.toggle('lm-density--compact', compact);
        try { localStorage.setItem(KEY, compact ? 'compact' : 'comfortable'); } catch (e) { /* ignore */ }
        btn.setAttribute('aria-pressed', compact ? 'true' : 'false');
      });
    });
  }

  /* ── 2. 命令面板（Ctrl/⌘ + K） ───────────────────────────── */
  function initPalette() {
    var overlay = qs('#lm-cmd-overlay');
    var panel = qs('#lm-cmd');
    if (!overlay || !panel) return;
    var input = qs('#lm-cmd-input', panel);
    var list = qs('#lm-cmd-list', panel);
    var items = null, filtered = [], active = 0;

    function iconFor(it) {
      return '<i class="mdi ' + (it.icon || 'mdi-chevron-right') + '"></i>';
    }
    function render() {
      if (!filtered.length) { list.innerHTML = '<div class="lm-cmd__hint">没有匹配项</div>'; return; }
      list.innerHTML = filtered.slice(0, 40).map(function (it, i) {
        return '<div class="lm-cmd__item' + (i === active ? ' is-active' : '') + '" data-i="' + i + '">' +
          iconFor(it) + '<span>' + (it.label || '') + '</span>' +
          (it.group ? '<small>' + it.group + '</small>' : '') + '</div>';
      }).join('');
    }
    function filter(term) {
      var t = (term || '').toLowerCase().trim();
      filtered = !t ? items.slice(0, 40) : items.filter(function (it) {
        return ((it.label || '') + ' ' + (it.keywords || '') + ' ' + (it.group || '')).toLowerCase().indexOf(t) !== -1;
      });
      active = 0; render();
    }
    function open() {
      overlay.classList.add('is-open'); panel.classList.add('is-open');
      input.value = ''; input.focus();
      if (items) { filter(''); return; }
      fetch(api(BASE + 'api/command-index/'), { credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (d) { items = (d && d.items) || []; filter(''); })
        .catch(function () { items = []; list.innerHTML = '<div class="lm-cmd__hint">索引加载失败</div>'; });
    }
    function close() { overlay.classList.remove('is-open'); panel.classList.remove('is-open'); }
    function run(i) {
      var it = filtered[i]; if (!it) return;
      close();
      if (it.action === 'goto') { window.location = it.url; }
      else if (it.url) { window.location = it.url; }
    }
    input.addEventListener('input', function () { filter(input.value); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); active = Math.min(active + 1, Math.min(filtered.length, 40) - 1); render(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); active = Math.max(active - 1, 0); render(); }
      else if (e.key === 'Enter') { e.preventDefault(); run(active); }
      else if (e.key === 'Escape') { close(); }
    });
    list.addEventListener('click', function (e) {
      var row = e.target.closest('.lm-cmd__item'); if (!row) return;
      run(parseInt(row.getAttribute('data-i'), 10));
    });
    overlay.addEventListener('click', close);
    qsa('[data-lm-cmd-open]').forEach(function (b) { b.addEventListener('click', open); });
    document.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) { e.preventDefault(); open(); }
      else if (e.key === 'Escape' && panel.classList.contains('is-open')) close();
    });
  }

  /* ── 3. AI 副驾驶（携带当前页面上下文） ─────────────────── */
  function initCopilot() {
    var btn = qs('#lm-copilot-btn');
    var panel = qs('#lm-copilot');
    if (!btn || !panel) return;
    var log = qs('#lm-copilot-log', panel);
    var input = qs('#lm-copilot-input', panel);
    var send = qs('#lm-copilot-send', panel);
    var ctxEl = qs('#lm-copilot-ctx', panel);
    var conversationPk = panel.getAttribute('data-conversation') || '';
    var ctx = document.body.getAttribute('data-lm-context') || document.title;
    if (ctxEl) ctxEl.textContent = '上下文：' + ctx;

    function bubble(text, who) {
      var d = document.createElement('div');
      d.className = 'lm-copilot__msg lm-copilot__msg--' + who;
      d.textContent = text;
      log.appendChild(d); log.scrollTop = log.scrollHeight;
      return d;
    }
    btn.addEventListener('click', function () {
      panel.classList.toggle('is-open');
      if (panel.classList.contains('is-open')) {
        input.focus();
        if (!log.children.length) bubble('我是实验室副驾驶。当前页面：' + ctx + '\n可以直接问：这个硬件还能借吗 / 帮我写采购建议 / 该成员最近做了什么。', 'bot');
      }
    });
    function submit() {
      var text = input.value.trim(); if (!text) return;
      input.value = '';
      bubble(text, 'user');
      var pending = bubble('思考中…', 'bot');
      var payload = { message: text, page_context: ctx };
      if (conversationPk) payload.conversation_pk = conversationPk;
      postJSON(BASE + 'agent/chat/', payload).then(function (res) {
        var d = res.data || {};
        var answer = d.answer || d.answer_text || (d.data && (d.data.answer || d.data.answer_text)) || d.message || '（无回复）';
        if (d.conversation_pk) conversationPk = d.conversation_pk;
        pending.textContent = answer;
      }).catch(function () { pending.textContent = '请求失败，请稍后再试。'; });
    }
    send.addEventListener('click', submit);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
    });
  }

  /* ── 4. 看板拖拽改状态 ───────────────────────────────────── */
  function initKanban() {
    var board = qs('[data-lm-kanban]');
    if (!board) return;
    var url = board.getAttribute('data-lm-kanban');
    var dragEl = null;
    qsa('.lm-kanban__card', board).forEach(function (card) {
      card.setAttribute('draggable', 'true');
      card.addEventListener('dragstart', function () { dragEl = card; card.classList.add('is-dragging'); });
      card.addEventListener('dragend', function () { card.classList.remove('is-dragging'); });
    });
    qsa('.lm-kanban__col', board).forEach(function (col) {
      col.addEventListener('dragover', function (e) { e.preventDefault(); col.classList.add('is-drop-target'); });
      col.addEventListener('dragleave', function () { col.classList.remove('is-drop-target'); });
      col.addEventListener('drop', function (e) {
        e.preventDefault(); col.classList.remove('is-drop-target');
        if (!dragEl) return;
        var status = col.getAttribute('data-status');
        var list = qs('.lm-kanban__list', col);
        if (list) list.appendChild(dragEl);
        var pk = dragEl.getAttribute('data-pk');
        postJSON(url, { pk: pk, status: status }).then(function (r) {
          if (!r.ok) { alert('状态更新失败，请刷新重试'); }
          var badge = qs('.lm-kanban__col-head .count', col);
          if (badge) badge.textContent = qsa('.lm-kanban__card', col).length;
        });
      });
    });
  }

  /* ── 5. 投屏模式（指挥舱） ───────────────────────────────── */
  function initProjector() {
    var btn = qs('[data-lm-projector-toggle]');
    if (!btn) return;
    var KEY = 'lm_projector';
    var on = false;
    try { on = localStorage.getItem(KEY) === '1'; } catch (e) { /* ignore */ }
    document.body.classList.toggle('lm-projector', on);
    btn.addEventListener('click', function () {
      on = !document.body.classList.contains('lm-projector');
      document.body.classList.toggle('lm-projector', on);
      try { localStorage.setItem(KEY, on ? '1' : '0'); } catch (e) { /* ignore */ }
      if (on && document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().catch(function () { /* 用户拒绝则仅样式生效 */ });
      } else if (!on && document.exitFullscreen && document.fullscreenElement) {
        document.exitFullscreen().catch(function () { /* ignore */ });
      }
    });
    var auto = qs('[data-lm-autorefresh]');
    if (auto && document.body.classList.contains('lm-projector')) {
      setTimeout(function () { window.location.reload(); }, parseInt(auto.getAttribute('data-lm-autorefresh'), 10) * 1000);
    }
  }

  /* ── 6. 卡片行点击（替代内联 onclick） ───────────────────── */
  function initRowLinks() {
    qsa('[data-lm-href]').forEach(function (el) {
      if (el.dataset.lmBound === '1') return;
      el.dataset.lmBound = '1';
      el.style.cursor = 'pointer';
      el.addEventListener('click', function (e) {
        if (e.target.closest('a, button, input, select')) return;
        window.location = el.getAttribute('data-lm-href');
      });
      el.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') window.location = el.getAttribute('data-lm-href');
      });
    });
  }

  /* ── 6b. 侧栏滚动位置保持：整页跳转也不会把菜单弹回顶部 ── */
  function initSidebarScroll() {
    var nav = document.querySelector('.navbar-vertical .navbar-collapse, .navbar-vertical');
    if (!nav) return;
    var KEY = 'lm_sidebar_scroll';
    try {
      var saved = parseInt(sessionStorage.getItem(KEY) || '0', 10);
      if (saved > 0) nav.scrollTop = saved;
    } catch (e) { /* ignore */ }
    window.addEventListener('pagehide', function () {
      try { sessionStorage.setItem(KEY, String(nav.scrollTop || 0)); } catch (e) { /* ignore */ }
    });
  }

  /* ── 7. 悬停预取：鼠标移到链接上就预取目标页，点击后命中缓存（导航更跟手） ── */
  function initPrefetch() {
    if (!('prefetch' in document.createElement('link'))) return;
    var seen = Object.create(null);
    document.addEventListener('mouseover', function (e) {
      var a = e.target.closest && e.target.closest('a[href]');
      if (!a) return;
      var href = a.getAttribute('href') || '';
      if (!href || href.charAt(0) !== '/' || a.target === '_blank' || seen[href]) return;
      if (a.hasAttribute('data-bs-toggle') || href.indexOf('#') === 0) return;
      seen[href] = 1;
      var link = document.createElement('link');
      link.rel = 'prefetch';
      link.href = href;
      document.head.appendChild(link);
    }, { passive: true });
  }

  /* ── 8. 特效开关（默认关闭全屏无限动画） ── */
  function initEffects() {
    var KEY = 'lm_effects';
    var on = false;
    try { on = localStorage.getItem(KEY) === '1'; } catch (e) { /* ignore */ }
    document.documentElement.classList.toggle('lm-effects', on);
    qsa('[data-lm-effects-toggle]').forEach(function (btn) {
      btn.textContent = on ? '关闭特效' : '开启特效';
      if (btn.dataset.lmBound === '1') return;
      btn.dataset.lmBound = '1';
      btn.addEventListener('click', function () {
        on = !document.documentElement.classList.contains('lm-effects');
        document.documentElement.classList.toggle('lm-effects', on);
        try { localStorage.setItem(KEY, on ? '1' : '0'); } catch (e) { /* ignore */ }
        btn.textContent = on ? '关闭特效' : '开启特效';
      });
    });
  }

  /* ── 9. 侧栏局部导航（HTMX boost 的守门与善后） ─────────────────
     目标：点击左侧菜单时只替换内容区，侧栏 DOM 完全不动（不再"菜单刷新"）。
     风险控制：对含内联脚本或文件上传的页面禁用 boost，退回整页跳转；
             换页后重新执行内容区脚本并重新初始化交互组件。 ── */
  var BOOST_BLOCKLIST = ['/agent/', '/checkins/new/', '/logout/', '/login/'];

  function initBoost() {
    // 说明：本项目的 HTMX 打包在 netbox.js 内，window.htmx 可能不存在，
    // 因此不依赖它做判断，直接按属性生效（无 HTMX 时这些属性是无害的）。
    var boosted = document.querySelector('[hx-boost="true"]');
    if (!boosted) return;
    // 给不能局部替换的链接关闭 boost
    qsa('.navbar-vertical a[href], a[data-no-boost]').forEach(function (a) {
      var href = a.getAttribute('href') || '';
      var blocked = a.hasAttribute('data-no-boost') || a.target === '_blank'
        || BOOST_BLOCKLIST.some(function (p) { return href.indexOf(p) !== -1; });
      if (blocked) a.setAttribute('hx-boost', 'false');
    });

    // htmx 在 DOMContentLoaded 时已绑定 boost 监听（bubble 阶段），
    // 因此黑名单必须在捕获阶段拦截，直接走整页跳转。
    document.addEventListener('click', function (e) {
      var a = e.target.closest && e.target.closest('a[href]');
      if (!a) return;
      var href = a.getAttribute('href') || '';
      var blocked = a.hasAttribute('data-no-boost') || a.target === '_blank'
        || BOOST_BLOCKLIST.some(function (p) { return href.indexOf(p) !== -1; });
      if (!blocked) return;
      e.stopPropagation();     // 阻止 htmx 局部替换
      e.preventDefault();
      window.location.href = a.href;
    }, true);

    // 只换内容区时，NetBox 的 OOB 片段（通知角标等）找不到目标会打印诊断，
    // 属纯提示、不影响功能，这里精确静音，避免刷控制台。
    var _consoleError = console.error;
    console.error = function () {
      var first = String((arguments && arguments[0]) || '');
      if (first.indexOf('htmx:oobErrorNoTarget') !== -1) return;
      return _consoleError.apply(console, arguments);
    };

    // 用响应里的 <title> 更新标签页标题（hx-select 只取内容区，标题不在其中）
    document.body.addEventListener('htmx:beforeSwap', function (e) {
      var xhr = e.detail.xhr;
      if (!xhr || !xhr.responseText) return;
      var m = xhr.responseText.match(/<title>([\s\S]*?)<\/title>/i);
      if (m) document.title = m[1].trim();
    });

    // OOB 片段（通知角标等）在只换内容区时找不到目标，静默跳过，避免刷控制台报错
    document.body.addEventListener('htmx:oobErrorNoTarget', function (e) {
      if (e && e.preventDefault) e.preventDefault();
    });

    // 换页后：重新执行内容区内联脚本 + 重新初始化组件
    var rebind = function () {
      qsa('#page-content script').forEach(function (old) {
        var s = document.createElement('script');
        if (old.src) s.src = old.src; else s.textContent = old.textContent;
        old.replaceWith(s);
      });
      initDensity(); initEffects(); initRowLinks(); initKanban();
    };
    document.body.addEventListener('htmx:afterSwap', rebind);
    document.body.addEventListener('htmx:afterSettle', rebind);
    // 兜底：不依赖 htmx 的事件名/实现，直接观察内容区被替换
    var content = document.getElementById('page-content');
    if (content && window.MutationObserver) {
      new MutationObserver(function (muts) {
        for (var i = 0; i < muts.length; i++) {
          if (muts[i].addedNodes && muts[i].addedNodes.length) { rebind(); return; }
        }
      }).observe(content, { childList: true });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    initDensity(); initPalette(); initCopilot(); initKanban(); initProjector(); initRowLinks();
    initPrefetch(); initEffects(); initSidebarScroll(); initBoost();
  });
})();
