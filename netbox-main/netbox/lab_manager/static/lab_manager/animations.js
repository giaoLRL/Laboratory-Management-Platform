/**
 * Lab Manager - Data Animation Engine v1.0
 * 数字滚动计数 + 柱状图升起 + 进度条填充动画
 *
 * 用法：
 *   <h3 class="tp-count-up" data-target="42">0</h3>
 *   <div class="tp-rise-bar" data-height="75"></div>
 *   <div class="tp-progress-fill" data-width="65"></div>
 */

(function () {
  'use strict';

  // ── 配置 ──
  // 移动端使用更短动画时长以减少 GPU 负担
  var isMobile = window.innerWidth < 768;
  var prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var DURATION = prefersReduced ? 0 : (isMobile ? 400 : 800);
  var FRAME_RATE = 16;      // ~60fps
  var BAR_DELAY = prefersReduced ? 0 : (isMobile ? 15 : 30);  // 移动端交错延迟减半

  // ── 缓动函数 (easeOutCubic) ──
  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  // ── 数字缓动 (easeOutExpo — 快速到达但收尾柔和) ──
  function easeOutExpo(t) {
    return t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
  }

  // ═══════════════════════════════════════════════
  // 1. 数字滚动计数动画
  // ═══════════════════════════════════════════════
  function animateCountUp() {
    var els = document.querySelectorAll('.tp-count-up');
    if (!els.length) return;

    for (var i = 0; i < els.length; i++) {
      (function (el) {
        var target = parseFloat(el.getAttribute('data-target'));
        if (isNaN(target)) return;

        var isFloat = el.getAttribute('data-target').indexOf('.') !== -1;
        var decimals = isFloat ? el.getAttribute('data-target').split('.')[1].length : 0;
        var suffix = el.getAttribute('data-suffix') || '';
        var prefix = el.getAttribute('data-prefix') || '';
        var start = 0;
        var startTime = null;

        // 跳过已动画的元素
        if (el._tpAnimated) return;
        el._tpAnimated = true;

        function step(timestamp) {
          if (!startTime) startTime = timestamp;
          var elapsed = timestamp - startTime;
          var progress = Math.min(elapsed / DURATION, 1);
          var easedProgress = easeOutExpo(progress);
          var current = start + (target - start) * easedProgress;

          if (isFloat) {
            el.textContent = prefix + current.toFixed(decimals) + suffix;
          } else if (target >= 1000) {
            // 大整数加千位分隔符
            el.textContent = prefix + Math.round(current).toLocaleString() + suffix;
          } else {
            el.textContent = prefix + Math.round(current) + suffix;
          }

          if (progress < 1) {
            requestAnimationFrame(step);
          } else {
            // 确保最终值精确
            if (isFloat) {
              el.textContent = prefix + target.toFixed(decimals) + suffix;
            } else if (target >= 1000) {
              el.textContent = prefix + target.toLocaleString() + suffix;
            } else {
              el.textContent = prefix + target + suffix;
            }
          }
        }
        requestAnimationFrame(step);
      })(els[i]);
    }
  }

  // ═══════════════════════════════════════════════
  // 2. 柱状图升起动画
  // ═══════════════════════════════════════════════
  function animateRiseBars() {
    var bars = document.querySelectorAll('.tp-rise-bar');
    if (!bars.length) return;

    for (var i = 0; i < bars.length; i++) {
      (function (bar, index) {
        var targetHeight = parseFloat(bar.getAttribute('data-height'));
        if (isNaN(targetHeight) || targetHeight <= 0) targetHeight = 2;

        var maxHeight = parseFloat(bar.getAttribute('data-max-height') || '100');
        if (targetHeight > maxHeight) targetHeight = maxHeight;

        if (bar._tpAnimated) return;
        bar._tpAnimated = true;

        // 保存原始高度
        var startHeight = 0;
        var startTime = null;
        var delay = index * BAR_DELAY;

        // 初始设置为 0
        bar.style.height = '0px';
        bar.style.transition = 'none';

        function step(timestamp) {
          if (!startTime) {
            if (timestamp < delay) {
              requestAnimationFrame(step);
              return;
            }
            startTime = timestamp;
          }
          var elapsed = timestamp - startTime;
          var progress = Math.min(elapsed / DURATION, 1);
          var easedProgress = easeOutCubic(progress);
          var current = startHeight + (targetHeight - startHeight) * easedProgress;
          bar.style.height = current + 'px';

          if (progress < 1) {
            requestAnimationFrame(step);
          } else {
            bar.style.height = targetHeight + 'px';
          }
        }
        // 延迟启动
        setTimeout(function () {
          requestAnimationFrame(step);
        }, delay);
      })(bars[i], i);
    }
  }

  // ═══════════════════════════════════════════════
  // 3. 进度条填充动画
  // ═══════════════════════════════════════════════
  function animateProgressBars() {
    var bars = document.querySelectorAll('.tp-progress-fill');
    if (!bars.length) return;

    for (var i = 0; i < bars.length; i++) {
      (function (bar) {
        var targetWidth = parseFloat(bar.getAttribute('data-width'));
        if (isNaN(targetWidth)) return;

        if (bar._tpAnimated) return;
        bar._tpAnimated = true;

        // 初始宽度设为 0
        bar.style.width = '0%';
        bar.style.transition = 'width ' + (DURATION / 1000) + 's cubic-bezier(0.25, 0.46, 0.45, 0.94)';

        // 触发回流后设置目标宽度
        requestAnimationFrame(function () {
          requestAnimationFrame(function () {
            bar.style.width = targetWidth + '%';
          });
        });
      })(bars[i]);
    }
  }

  // ═══════════════════════════════════════════════
  // 4. 交错卡片滑入动画（统计卡片）
  // ═══════════════════════════════════════════════
  function animateStatCards() {
    var cards = document.querySelectorAll('.tp-stat-animate-in');
    if (!cards.length) return;

    for (var i = 0; i < cards.length; i++) {
      (function (card, index) {
        if (card._tpAnimated) return;
        card._tpAnimated = true;

        card.style.opacity = '0';
        card.style.transform = 'translateY(16px)';
        card.style.transition = 'opacity 0.4s ease-out, transform 0.4s ease-out';
        card.style.transitionDelay = (index * 60) + 'ms';

        requestAnimationFrame(function () {
          card.style.opacity = '1';
          card.style.transform = 'translateY(0)';
        });
      })(cards[i], i);
    }
  }

  // ═══════════════════════════════════════════════
  // 入口：页面加载 + 可见性变化时触发
  // ═══════════════════════════════════════════════
  function runAll() {
    animateStatCards();
    // 让数字计数在卡片滑入后开始
    setTimeout(function () {
      animateCountUp();
      animateRiseBars();
      animateProgressBars();
    }, 200);
  }

  // IntersectionObserver: 元素进入视口时触发
  if ('IntersectionObserver' in window) {
    var observerOptions = { threshold: 0.15, rootMargin: '0px 0px -30px 0px' };
    var observer = new IntersectionObserver(function (entries) {
      var triggered = false;
      for (var i = 0; i < entries.length; i++) {
        if (entries[i].isIntersecting) {
          triggered = true;
          break;
        }
      }
      if (triggered) {
        runAll();
        observer.disconnect();
      }
    }, observerOptions);

    // 观察第一个统计容器
    document.addEventListener('DOMContentLoaded', function () {
      var target = document.querySelector('.tp-home-dashboard, .tp-member-detail, .tp-member-list, .tp-member-open-records');
      if (target) {
        observer.observe(target);
      } else {
        // 降级：直接运行动画
        runAll();
      }
    });
  } else {
    // 不支持 IntersectionObserver 的浏览器直接运行
    document.addEventListener('DOMContentLoaded', runAll);
  }

  // 如果 DOM 已加载则立即运行
  if (document.readyState === 'interactive' || document.readyState === 'complete') {
    var target = document.querySelector('.tp-home-dashboard, .tp-member-detail, .tp-member-list, .tp-member-open-records');
    if (target && 'IntersectionObserver' in window) {
      // 由 observer 处理
    } else {
      runAll();
    }
  }

})();
