# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

基于 **NetBox 4.6** 的实验室管理平台。核心是 `lab_manager` 插件，提供硬件库存、任务分配、签到签退、LLM 智能体助手。

**技术栈：** Python 3.12+ / Django 6.x / PostgreSQL / Redis / LangChain / Docker

## 目录

```
实验室/
├── CLAUDE.md              # 本文件
├── start.sh / stop.sh     # 一键启停
├── netbox-main/           # ★ 主项目
│   ├── CLAUDE.md          # → 指向 AGENTS.md（NetBox 上游开发指南）
│   ├── AGENTS.md          # NetBox 框架架构/命令/约定（必读）
│   ├── requirements.txt
│   └── netbox/
│       ├── manage.py      # Django 入口（所有 manage.py 命令在此运行）
│       ├── netbox/
│       │   ├── configuration.py          # ★ 实际配置（gitignored）
│       │   └── configuration_docker.py   # Docker 部署模板
│       └── lab_manager/   # ★ 本项目的插件
│           ├── models/         # 拆分后的数据模型（11 个模块 / 13 个模型）
│           ├── services/       # LLM Agent + 平台数据服务
│           ├── tables/         # django-tables2 表格
│           ├── forms/          # 模型表单 + 筛选表单
│           ├── api/            # DRF REST API
│           ├── navigation/     # 左侧菜单
│           └── templates/      # 页面模板
├── Agent-Reach/            # MCP 网络搜索
├── codebase-memory-mcp/    # MCP 代码库记忆
└── config/                 # MCP 端口配置
```

## 命令

所有命令在 `netbox-main/netbox/` 下执行，需先激活虚拟环境：

```bash
cd netbox-main/netbox
source ../venv/Scripts/activate   # Windows
source ../venv/bin/activate       # macOS/Linux
```

| 命令 | 用途 |
|------|------|
| `python manage.py runserver` | 启动开发服务器 |
| `python manage.py migrate` | 应用数据库迁移 |
| `python manage.py nbshell` | Django 交互 shell（已自动加载 NetBox 上下文） |
| `python manage.py test lab_manager --keepdb` | 运行 lab_manager 测试（31 个用例，约 35s） |
| `python manage.py test lab_manager.tests.test_models --keepdb` | 运行单个测试模块 |
| `python manage.py collectstatic` | 收集静态文件 |
| `python manage.py changepassword <user>` | 重置用户密码 |

**启动/停止：** 在项目根目录执行 `bash start.sh` / `bash stop.sh`，自动处理 Docker 容器、虚拟环境、迁移。

## NetBox 框架关键约定

以下是与标准 Django 不同的 NetBox 特定模式（详见 `netbox-main/AGENTS.md`）：

### 模型
- 所有模型继承 `NetBoxModel`（非 `models.Model`），自动获得 `created`、`last_updated`、`tags`、`custom_fields`
- 模型文件放在 `models/` 子目录，在 `models/__init__.py` 中导出
- Choices 继承 `utilities.choices.ChoiceSet`，定义在 `choices.py`
- 每个模型需要：filterset、form、table、serializer、view、URL route、template

### 视图注册
- 使用 `@register_model_view(Model, 'action')` 装饰器注册视图
- 列表视图用 `generic.ObjectListView`，编辑用 `generic.ObjectEditView`，删除用 `generic.ObjectDeleteView`
- 权限控制：覆写 `has_permission()` 方法
- List views **不需要**手动 `select_related()`/`prefetch_related()`——table 会自动处理

### URL 路由
- 使用 `get_model_urls('plugin_name', 'modelname')` 生成标准 CRUD 路由
- **注意：** `get_model_urls` 中的 modelname 必须与模型 `_meta.model_name` 一致（全小写，如 `AgentTool` → `agenttool`）
- 模型的 `get_absolute_url()` 返回 `reverse('plugins:lab_manager:modelname', args=[self.pk])`

### 模板
- NetBox 会自动查找 `templates/lab_manager/<modelname>.html` 作为详情页模板
- 本项目使用自定义基类：`lab_manager/base.html` → `base/layout.html`；列表/详情/编辑/删除分别用 `object_list.html`、`object_base.html`、`object_edit_base.html`、`object_delete_base.html`
- 列表页模板名由 `get_model_urls` + `register_model_view` 自动推导

### 迁移
- **NetBox 禁用了 `makemigrations`**，会报 `CommandError`
- 需要手动用 `MigrationAutodetector` + `MigrationWriter` 生成迁移文件：
  ```python
  import django; django.setup()
  from django.db.migrations.autodetector import MigrationAutodetector
  from django.db.migrations.state import ProjectState
  from django.db.migrations.writer import MigrationWriter
  from django.db.migrations.loader import MigrationLoader
  from django.apps import apps
  loader = MigrationLoader(None, ignore_no_migrations=False)
  from_state = loader.project_state()
  target_state = ProjectState.from_apps(apps)
  autodetector = MigrationAutodetector(from_state, target_state)
  changes = autodetector.changes(graph=loader.graph)
  # 然后对 changes['lab_manager'] 中的每个 migration 调用 MigrationWriter
  ```

## lab_manager 插件架构

### 数据模型（13 个，拆分为独立文件）

| 模型 | 文件 | 说明 |
|------|------|------|
| Hardware | `models/hardware.py` | 硬件设备（名称/类别/数量/状态/保管人/审批） |
| HardwareBorrowRecord | `models/borrow.py` | 硬件借出/归还记录 |
| HardwareImportBatch | `models/import_batch.py` | 批量导入批次 |
| Task | `models/task.py` | 任务（含 TaskComment、TaskAttachment） |
| CheckInRecord | `models/checkin.py` | 签退记录（GPS + 照片） |
| MemberOpenRecord | `models/open_record.py` | 成员页面浏览记录 |
| AgentConversation / AgentMessage | `models/conversation.py` | LLM 对话历史 |
| LabProject | `models/project.py` | 实验项目（含成员 M2M） |
| AgentTool | `models/agent_tool.py` | 智能体工具定义（启用/禁用/参数管理） |
| Notification | `models/notification.py` | 站内通知 |

### LLM 智能体调用链

```
用户输入 → AgentChatProxyView (views.py)
  ↓
LangChainAgentService.process_message()  ★ 首选 → DeepSeek
  ├── _load_enabled_tools() → 从 AgentTool 模型动态加载已启用工具
  ├── _build_dynamic_tool() → 为每个工具创建 LangChain StructuredTool
  └── agent.invoke() → DeepSeek 回复
  ↓ 失败则降级
AgentToolOrchestrator.process_message()  ★ 降级 1（本地规则编排）
  ↓ 再失败
BackendAgentService.process_message()    ★ 降级 2（最终兜底）
```

### 智能体工具系统（agent tool management）

**可通过管理界面模块化管理 LLM 可调用的工具。**

三层架构：

1. **数据库层** `models/agent_tool.py` — `AgentTool` 模型存储工具元数据（名称、描述、参数 Schema、启用状态、分类、执行映射）
2. **执行层** `services/tool_registry.py` — `execution_key → handler` 映射，7 个处理器：`platform_query`、`describe_data`、`task_create`、`video_search`、`image_search`、`hardware_gap`、`find_members`
3. **LLM 层** `services/langchain_agent_service.py` — `_load_enabled_tools()` 从 DB 加载已启用工具，`_build_dynamic_tool()` 动态创建 LangChain StructuredTool

管理界面：`/plugins/lab-manager/agent-tools/`（仅管理员），支持增删改查、启用/禁用、批量操作。

**添加新工具：** ① 在 `tool_registry.py` 的 `TOOL_REGISTRY` 注册执行函数 ② 在管理界面新增 `AgentTool` 记录。

### 配置读取

```python
from netbox.plugins.utils import get_plugin_config
api_key = get_plugin_config('lab_manager', 'langchain_api_key', 'NOT SET')
```

配置在 `configuration.py` 的 `PLUGINS_CONFIG['lab_manager']` 中定义。该文件 gitignored。

### 前端

- CSS：`static/lab_manager/lab_manager.css`（约 660 行）+ `terminal_pixel.css`（主题）+ `animations.js`
- 智能体控制台：`templates/lab_manager/agent_console.html`（含自包含 Markdown 渲染器）
- 侧边栏折叠状态持久化到 `localStorage` key `lab_sidebar_collapsed`
- CSRF Token：优先使用 `window.CSRF_TOKEN`（NetBox base.html 注入）

## 开发常见任务

### 为 lab_manager 添加新模型

1. 在 `models/` 下创建模块，继承 `NetBoxModel`
2. 在 `models/__init__.py` 导出
3. 创建 `tables/<model>.py`（继承 `NetBoxTable`）
4. 在 `filtersets.py` 添加 FilterSet
5. 在 `forms/model_forms.py` 添加 Form，在 `forms/filtersets.py` 添加 FilterForm
6. 在 `views.py` 用 `@register_model_view` 注册 CRUD 视图
7. 在 `urls.py` 添加 `get_model_urls`
8. 在 `navigation/menu.py` 添加菜单项
9. 创建 `templates/lab_manager/<modelname>.html` 详情模板
10. 生成迁移（见上方"迁移"章节）→ `python manage.py migrate`

### 调试 LLM Agent

```bash
cd netbox-main/netbox
python -c "
import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
import django; django.setup()
from django.contrib.auth import get_user_model
from lab_manager.services.langchain_agent_service import LangChainAgentService
user = get_user_model().objects.first()
resp = LangChainAgentService().process_message(user=user, message='你好')
print('handled:', resp.handled, 'answer:', resp.answer_text[:200])
"
```

### 检查 LangChain 配置

```bash
cd netbox-main/netbox
python -c "
import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
import django; django.setup()
from netbox.plugins.utils import get_plugin_config
print('api_key:', repr(get_plugin_config('lab_manager', 'langchain_api_key', 'NOT SET')))
print('model:', get_plugin_config('lab_manager', 'langchain_model', 'NOT SET'))
"
```

## 本项目的 NetBox 偏离

- **Django Admin 不可用** — NetBox 不包含 `django.contrib.admin`，所有管理通过 NetBox 自带 UI + 自定义视图
- **端口偏移** — PostgreSQL 用 `5433`（非默认 5432），Redis 用 `6380`（非默认 6379），避免与本机其他服务冲突
- **LLM 配置在插件配置中** — `PLUGINS_CONFIG['lab_manager']`，非环境变量或 Django settings
- **`manage.py` 路径** — 在 `netbox-main/netbox/` 下，非仓库根目录

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

### 分页
- **全站列表默认每页 10 条**，两个入口必须保持一致：
  - NetBox 核心/插件通用列表（`ObjectListView`）读 `configuration.py` 的 `PAGINATE_COUNT`（已设 10）；
  - 插件自写列表走 `lab_manager/views.py` 的 `add_pagination()`，其 `DEFAULT_PAGE_SIZE = 10`、
    `PAGE_SIZE_CHOICES = (10, 25, 50, 100, 200)`。**新增列表请调用 `add_pagination()`，
    不要再硬编码 `default_size=25`。**
- `utilities/paginator.py`：
  - `EnhancedPaginator.default_page_lengths` 首位补了 `10`（下拉框必须包含当前页大小，否则回不到默认值）；
  - `orphans` 默认改为 `0`。NetBox 原本在 `per_page <= 50` 时用 `orphans=5` 把末页零头并进上一页，
    会出现"设置每页 10 条却显示 12 条"的观感。需要恢复该行为时显式传 `orphans=5`。
- 用户级偏好 `user.config['pagination.per_page']` 会覆盖 `PAGINATE_COUNT`；
  排查"分页设置没生效"时先查这个（`reports/qa/check_paginate_prefs.py`）。

### 测试
- 测试位于 `lab_manager/tests/`，覆盖借出库存、信号通知、404/405、媒体鉴权、打卡去重、
  导入并发、Agent API 输入校验、工具参数归一化等回归点。
