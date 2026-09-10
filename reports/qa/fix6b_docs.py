"""批次6b：校准 AGENTS.md / CLAUDE.md 中与实现不符的数字与说明，并追加修复记录。"""
import io
import os
import sys

ROOT = r'C:\Users\PC\Documents\实验室'
APPLY = '--apply' in sys.argv
report, failures = [], []

PAIRS = [
    (
        "│       └── lab_manager/   # ★ 本项目的插件\n"
        "│           ├── models/         # 拆分后的数据模型（9 个文件）",
        "│       └── lab_manager/   # ★ 本项目的插件\n"
        "│           ├── models/         # 拆分后的数据模型（11 个模块 / 13 个模型）",
    ),
    (
        "### 数据模型（9 个，拆分为独立文件）",
        "### 数据模型（13 个，拆分为独立文件）",
    ),
    (
        "| AgentTool | `models/agent_tool.py` | 智能体工具定义（启用/禁用/参数管理） |",
        "| AgentTool | `models/agent_tool.py` | 智能体工具定义（启用/禁用/参数管理） |\n"
        "| Notification | `models/notification.py` | 站内通知 |",
    ),
    (
        "2. **执行层** `services/tool_registry.py` — `execution_key → handler` 映射，6 个处理器：`platform_query`、`describe_data`、`task_create`、`video_search`、`hardware_gap`、`find_members`",
        "2. **执行层** `services/tool_registry.py` — `execution_key → handler` 映射，7 个处理器：`platform_query`、"
        "`describe_data`、`task_create`、`video_search`、`image_search`、`hardware_gap`、`find_members`",
    ),
    (
        "- CSS：`static/lab_manager/lab_manager.css`（~290 行，ChatGPT 风格侧边栏）",
        "- CSS：`static/lab_manager/lab_manager.css`（约 660 行）+ `terminal_pixel.css`（主题）+ `animations.js`",
    ),
    (
        "### 模板\n"
        "- NetBox 会自动查找 `templates/lab_manager/<modelname>.html` 作为详情页模板\n"
        "- 通用模板继承 `generic/object.html`、`generic/object_list.html` 等\n"
        "- 列表页模板名由 `get_model_urls` + `register_model_view` 自动推导",
        "### 模板\n"
        "- NetBox 会自动查找 `templates/lab_manager/<modelname>.html` 作为详情页模板\n"
        "- 本项目使用自定义基类：`lab_manager/base.html` → `base/layout.html`；"
        "列表/详情/编辑/删除分别用 `object_list.html`、`object_base.html`、"
        "`object_edit_base.html`、`object_delete_base.html`\n"
        "- 列表页模板名由 `get_model_urls` + `register_model_view` 自动推导",
    ),
    (
        "| `python manage.py test lab_manager --keepdb` | 运行 lab_manager 测试 |",
        "| `python manage.py test lab_manager --keepdb` | 运行 lab_manager 测试（31 个用例，约 35s） |",
    ),
]

APPENDIX = """

## 2026-09 修复记录（QA 全面测试后）

本轮针对 `reports/QA测试报告.md` 中确认的问题做了修复，改动涉及以下约定，后续开发请注意：

### 权限
- `management/commands/setup_permissions.py` **必须能正常执行**：NetBox 的 `ObjectPermission.actions`
  只能填 `view/add/change/delete`（后端拼成 `<app>.<action>_<model>`）。旧版本误填
  `view_hardware` 之类完整权限名，会生成永远匹配不到的权限，导致成员在受限表单里选不到任何对象。
- 运行 `python manage.py setup_permissions` 后，需把成员加入「实验室成员」组。
- `configuration.py` 中 `ENABLE_DEBUG_TOOLBAR = False`：工具栏会遮挡窄屏页面控件，并让
  `manage.py test` 直接报 `debug_toolbar.E001`。

### 借出与库存
- `Hardware.quantity` 语义是 **在库可用数量**：借出时由 `HardwareBorrowRecord.save()` 扣减，
  归还/删除记录时回补（删除走 `signals.restore_hardware_stock`，因为 `QuerySet.delete()`
  不会调用 `Model.delete()`）。新增借出流程时不要直接改 `quantity`。

### 智能体工具
- `services/tool_registry.normalize_platform_args()` 负责把 LLM 按 `parameters_schema`
  传来的 `filters_json` / `fields_json` / `record_id` 归一化成执行层的
  `filters` / `fields` / `id`。新增工具时保持这一层归一化。
- `AgentTool.requires_superuser` 由 `execute_tool()` 统一强制（LangChain 与降级路径都生效）。
- Agent API（`lab_manager/agent_api.py`）：
  - 会话鉴权的请求必须通过 CSRF 校验（仅网关令牌路径豁免）；
  - `agent_api_allow_user_impersonation` / `agent_api_allow_superuser_impersonation`
    控制 `X-User-ID` 代调用范围，默认**不允许冒充超管**；
  - `agent_api_token` 必须替换为随机值，不能沿用仓库示例值。

### 媒体文件
- 插件上传目录（`checkins/`、`task_attachments/`、`hardware/`）在 `MediaView` 中做对象级鉴权；
  附件与发票强制 `Content-Disposition: attachment`。

### 测试
- 测试位于 `lab_manager/tests/`，覆盖借出库存、信号通知、404/405、媒体鉴权、打卡去重、
  导入并发、Agent API 输入校验、工具参数归一化等回归点。
"""


def apply_pairs(name):
    full = os.path.join(ROOT, name)
    if not os.path.exists(full):
        failures.append(f'{name}: 文件不存在')
        return
    src = io.open(full, encoding='utf-8').read()
    orig = src
    for old, new in PAIRS:
        n = src.count(old)
        if n != 1:
            report.append(f'  -- {name}: 跳过（{n} 次命中）{old.strip().splitlines()[0][:48]}')
            continue
        src = src.replace(old, new)
        report.append(f'  ok {name}: {old.strip().splitlines()[0][:56]}')
    if '## 2026-09 修复记录' not in src:
        src = src.rstrip('\n') + APPENDIX
        report.append(f'  ok {name}: 追加修复记录')
    if src != orig and APPLY:
        io.open(full, 'w', encoding='utf-8', newline='').write(src)


for f in ['AGENTS.md', 'CLAUDE.md']:
    apply_pairs(f)

print('\n'.join(report))
if failures:
    print('失败:')
    for x in failures:
        print('  !!', x)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
