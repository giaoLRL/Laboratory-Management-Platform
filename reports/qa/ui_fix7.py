"""修正组件层语义令牌：改用主题中真实存在的变量，并为亮/暗主题分别定义状态色。"""
import io
import os
import sys

BASE = r'C:\Users\PC\Documents\实验室\netbox-main\netbox'
APPLY = '--apply' in sys.argv
path = os.path.join(BASE, 'lab_manager/static/lab_manager/lm-components.css')
src = io.open(path, encoding='utf-8').read()

OLD_SEMANTIC = """  /* ── semantic（跟随主题变量，亮/暗自动适配）── */
  --lm-surface-1: var(--tp-card-bg, #111726);
  --lm-surface-2: var(--tp-card-hover-bg, #161d2e);
  --lm-surface-3: var(--tp-nav-hover-bg, #1b2438);
  --lm-border-subtle: var(--tp-card-border, rgba(0, 229, 255, .14));
  --lm-border-strong: var(--tp-nav-accent, rgba(0, 229, 255, .34));
  --lm-text-primary: var(--tp-card-text, #e6f1ff);
  --lm-text-muted: var(--tp-text-muted, #8ea0b8);
  --lm-accent: var(--tp-nav-accent, #00e5ff);
  --lm-accent-soft: rgba(0, 229, 255, .12);
  --lm-ok: #00c853; --lm-warning: #ff9800; --lm-danger: #f44336; --lm-info: #2196f3;
"""

NEW_SEMANTIC = """  /* ── semantic ──────────────────────────────────────────────
     只引用主题中真实存在的变量（terminal_pixel.css 的 --tp-*）：
       --tp-card-bg / --tp-table-hover-bg / --tp-card-header-bg /
       --tp-card-header-text / --tp-card-body-text / --tp-text-muted /
       --tp-card-border / --tp-card-hover-border / --tp-nav-accent
     最后一级回退用中性值（rgba(127,127,127,x)），保证亮/暗都不出错。
     ────────────────────────────────────────────────────────── */
  --lm-surface-1: var(--tp-card-bg, #ffffff);
  --lm-surface-2: var(--tp-table-hover-bg, rgba(127, 127, 127, .08));
  --lm-surface-3: var(--tp-card-header-bg, var(--tp-table-hover-bg, rgba(127, 127, 127, .12)));
  --lm-border-subtle: var(--tp-card-border, rgba(127, 127, 127, .28));
  --lm-border-strong: var(--tp-card-hover-border, var(--tp-nav-accent, rgba(127, 127, 127, .55)));
  --lm-text-primary: var(--tp-card-header-text, var(--tp-card-body-text, var(--bs-body-color, #2b2b2b)));
  --lm-text-muted: var(--tp-text-muted, var(--tp-card-footer-text, rgba(127, 127, 127, .95)));
  --lm-accent: var(--tp-nav-accent, #0d6b63);
  --lm-accent-soft: var(--tp-nav-active-bg, rgba(127, 127, 127, .12));
  /* 状态色：浅色主题用深一档以保证 ≥4.5:1，暗色主题用高亮色 */
  --lm-ok: #0f7a3d; --lm-warning: #a35b00; --lm-danger: #c62828; --lm-info: #1565c0;
"""

if OLD_SEMANTIC not in src:
    print('!! 未找到旧的语义令牌块（可能已修改）')
    sys.exit(1)

src = src.replace(OLD_SEMANTIC, NEW_SEMANTIC, 1)

# 暗色主题的状态色覆盖（放在 :root 块之后）
if 'html[data-bs-theme=dark] {' not in src:
    marker = "/* ═══ 布局骨架 ═══ */"
    dark_block = """/* 暗色主题：状态色切回高亮版本（亮色值在暗底上对比度不足） */
html[data-bs-theme=dark] {
  --lm-ok: #00ff41; --lm-warning: #ffaa33; --lm-danger: #ff5566; --lm-info: #4aa8ff;
}

"""
    src = src.replace(marker, dark_block + marker, 1)

# 热力图：用 accent + 透明度，避免硬编码青色在浅色主题下过淡
OLD_HEAT = """.lm-heatmap__cell[data-level="1"] { background: rgba(0, 229, 255, .25); }
.lm-heatmap__cell[data-level="2"] { background: rgba(0, 229, 255, .45); }
.lm-heatmap__cell[data-level="3"] { background: rgba(0, 229, 255, .7); }
.lm-heatmap__cell[data-level="4"] { background: var(--lm-accent); }"""
NEW_HEAT = """.lm-heatmap__cell[data-level="1"] { background: var(--lm-accent); opacity: .28; }
.lm-heatmap__cell[data-level="2"] { background: var(--lm-accent); opacity: .5; }
.lm-heatmap__cell[data-level="3"] { background: var(--lm-accent); opacity: .74; }
.lm-heatmap__cell[data-level="4"] { background: var(--lm-accent); opacity: 1; }"""
if OLD_HEAT in src:
    src = src.replace(OLD_HEAT, NEW_HEAT, 1)

# 命令面板遮罩在浅色下不要过黑
src = src.replace('background: rgba(3, 6, 12, .55); backdrop-filter: blur(3px);',
                  'background: rgba(20, 20, 20, .38); backdrop-filter: blur(3px);', 1)

if APPLY:
    io.open(path, 'w', encoding='utf-8', newline='').write(src)
    print('已更新 lm-components.css')
    print('  · 语义令牌改用真实存在的 --tp-* 变量（修复浅色主题卡片标题不可见）')
    print('  · 状态色按亮/暗主题分别定义（浅色用深一档）')
    print('  · 热力图/遮罩改为主题自适应')
else:
    print('DRY-RUN：将更新语义令牌映射')
