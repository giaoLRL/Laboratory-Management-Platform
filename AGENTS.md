# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## 项目概览

**具身智能实验室 · 管理平台**。前后端分离架构：后端为独立 Django 工程 `lab-platform`（纯 JSON API，不托管任何 HTML 模板），前端为无运行时依赖的原生 JS SPA `lab-platform-web`。营销首页是独立静态页，部署在服务器 `/opt/lab/homepage`。

**技术栈：** Python 3.12+ / Django 6.x / Django REST Framework / PostgreSQL（生产）/ SQLite（本地开发）/ Gunicorn / 原生 JS（无构建步骤）。**已彻底脱离 NetBox**（旧 `netbox-main` 已删除）。

## 目录

```
实验室/
├── AGENTS.md              # 本文件
├── lab-platform/          # ★ 后端 Django 工程（纯 JSON API）
│   ├── manage.py          # Django 入口
│   ├── requirements.txt   # 运行时依赖（全部，见下文）
│   ├── Dockerfile         # 多阶段镜像，gunicorn 1 worker 起 8001
│   ├── db.sqlite3         # 本地开发库
│   ├── lab_api/           # 工程配置
│   │   ├── settings.py    # ★ 环境变量驱动配置
│   │   ├── urls.py        # 总路由（/api/ 前缀 + /media/ 鉴权）
│   │   ├── wsgi.py
│   ├── apps/              # 业务 app（Django 原生分割，非 NetBox 插件）
│   │   ├── common/        # 跨 app 工具：auth / response / permissions / ids / media_views / workspace
│   │   ├── accounts/      # 认证、成员、操作日志
│   │   ├── inventory/     # 硬件资产 + 借用/归还
│   │   ├── leaves/        # 请假审批
│   │   ├── competitions/  # 比赛管理
│   │   ├── tasksapp/      # 任务看板
│   │   ├── checkins/      # 打卡签退（GPS+照片）
│   │   ├── agent/         # LLM 智能体
│   ├── media/             # 上传文件（按 app/年月 分目录）
│   └── scripts/
│       ├── etl.py         # 旧 NetBox Postgres → lab2 数据抽取（一次性）
│       └── deploy_server.sh  # ★ 服务器一键部署脚本
├── lab-platform-web/      # ★ 前端 SPA（无运行时依赖）
│   ├── index.html         # 入口（资源用绝对 /src/... 引用）
│   ├── src/               # core / features / app / ui / 各业务模块
│   └── tests/             # node --test 单元测试
├── 参考前端/              # 被改造前的参考实现（只读参考）
└── reports/ / docs/       # 历史报告与文档
```

## 命令

后端命令在 `lab-platform/` 下执行：

```bash
# 本地开发：默认 SQLite，Django 同时托管 API 和 SPA（同源 Cookie）
cd lab-platform
python -m pip install -r requirements.txt
python manage.py runserver            # http://127.0.0.1:8000

# 生产用 Docker（见 deploy_server.sh，服务实际跑在 8001）
```

前端测试：

```bash
cd lab-platform-web
npm test      # node --test tests/*.test.mjs（无运行时依赖，仅 Node>=20）
```

## 后端：lab-platform（Django + DRF）

### 通用约定

- **纯 JSON API**：不使用 Django 模板/Admin（未装 `django.contrib.admin`、无 templates）。所有业务逻辑在 `apps/*/api.py` 的**函数式视图**（`@api_view`）里，不用 ViewSet/序列化器 for 业务体（`serializers.py` 仅用于字典/序列化）。
- **统一前缀**：所有接口挂在 `/api/` 下（`lab_api/urls.py` 用 `path('api/', include(api_patterns))`）。生产 nginx 不剥前缀，开发/生产行为一致。
- **统一响应**：一律用 `apps.common.response.ok()` / `fail()`：
  - 成功 → `{"data": ...}`；无数据时返回 `{"data": {"ok": true}}`（契约不允许空 204）
  - 失败 → `{"message": "可展示给用户"}`
  - 新增接口**必须**走这两个 helper，不要自拼 Response 或裸返回 dict。
- **认证**：DRF 默认认证用 `apps.common.auth.CsrfExemptSessionAuthentication`。会话 Cookie 设 `SameSite=Lax` 阻断跨站，DRF 层豁免 CSRF 强制校验。该认证器实现了 `authenticate_header` 返回 `'Session'`，使未登录返回 **401 而非 403**——SPA 以 401 判定跳登录页，改成 403 会致前端启动抛错空白。**不要改掉这个行为。**
- **权限**：默认 `IsAuthenticated`；登录、公开入口用 `@permission_classes([])`。业务角色/成员档通过 `apps.common.permissions.get_member()/is_staff()` 判断（注意 `MemberProfile` 通过 `user.member_profile` 关联，账号主键与成员档主键不同，对外统一用 `apps.common.ids` 生成的短 ID `Mxxxx`）。
- **数据库**：`LAB_DB_ENGINE` 环境变量切换 `sqlite`（默认，本地）/ `postgres`（生产）。生产 Key 全部走 `LAB_*` 环境变量，见 `settings.py` 头注释。**默认 SECRET_KEY 仅限本地**，生产必须注入。
- **分页/大数据聚合**：列表快照统一由 `GET /api/workspace`（`apps.common.workspace.build_workspace`）返回一次拉全量，业务 app 的 `api.py` 提供 `workspace_slice(profile, staff)` 往快照里追加各自数据数组，并用 `_ts`（最新修改时间戳）参与快照 `version` 计算实现增量。新增数据类目时按此模式接入，不要绕过 `build_workspace`。
- **媒体鉴权**：上传文件统一走 `map/{app}/{yyyyMM}/...` 落盘；访问统一走 `media/<path>` 的 `apps.common.media_views.protected_media`（登录+对象级鉴权后返回），**直接访问静态文件路径无鉴权**。index.html 引用 `/media/` 必须以 `/` 开头（http:// 相对路径在 /login/ 等子路径下会解析错，如 media 404 → 图片全挂）。

### app 与 API 面（均在 /api/ 前缀下）

| 模块 | app | 主要接口 |
|------|-----|---------|
| 认证 / 成员 / 日志 | `accounts` | `auth/login` `auth/me` `auth/logout` `workspace` `members`(增/改/改状态) |
| 硬件资产 / 借用 | `inventory` | `assets`(+维护/报废) `loans`(+审批/出借/归还) |
| 请假 | `leaves` | `leaves`(+审批/取消) |
| 比赛 | `competitions` | `competitions`(+更新/归档) |
| 任务看板 | `tasksapp` | `tasks`(+更新/删除/附件) |
| 打卡 | `checkins` | `checkins`(GPS+照片) |
| 智能体 | `agent` | `agent/chat` `agent/conversations`(+详情) |

完整字段契约见 `lab-platform-web/API.md`。

### LLM 智能体（apps/agent）

- 走 DeepSeek `OpenAI` 兼容协议，配置为 `LAB_LLM_API_KEY / LAB_LLM_BASE_URL / LAB_LLM_MODEL` 环境变量（`settings.py`）。
- 核心逻辑在 `apps/agent/service.py`；`apps/agent/api.py` 提供聊天与对话历史接口。
- 与旧 NetBox 版不同：**不再有 `AgentTool` 动态工具注册表/三层降级链**，改为由后端 service 直接编排平台数据查询。改动智能体行为时只动 `service.py` 与对话历史模型（`agent/models.py`）。

## 前端：lab-platform-web（无依赖原生 JS SPA）

### 架构（注册式页面模式，非构建式框架）

- **无任何运行时依赖**：不引 npm 包、无打包；`index.html` 以 `<script>` 按序引入 `src/` 下 JS（核心文件组 + 业务模块文件），资源用**绝对路径 `/src/...`**（相对路径在 `/login/` 等子路径文档下会解析成错误 URL → JS 报 `Unexpected token '<'`）。
- **`core.js`**：全局 `CONFIG`（`mode: 'api'`，`API_BASE_URL='/api'`）、`NAV` 菜单、`ROLE` 角色、常量、工具函数（`esc/date/fmt/uid/percentage/countStatuses`）与 API 封装（`API.load/login/logout/...`）。`CONFIG.mode='mock'` 切换为纯前端演示（不连后端）。
- **`features.js`**：按功能注册的页面组件/业务函数（成员、资产、借用、请假、比赛等的渲染与交互），以及 `handleAction(type, btn)` 处理 `data-action`。新增页面模块请沿用这里的注册式风格。
- **`app.js`**：入口。`pages` 路由表（`view → page 函数`）、`render()` 渲染 `shell()`(登录后) / `loginPage()`(未登录)、全局事件委托（click/submit）、hash 路由、`init()`。
- **`ui.js`**：通用 UI 组件（badge/stack/toast/empty/modal/icon 图标表 等）。
- 业务展示文件：`tasks.js`（任务看板）、`checkins.js`（打卡）、`competitions.js`（比赛）、`agent.js`（智能体控制台）。（seed.js 是 mock 演示种子数据，API 模式不参与。）
- **交互约定**：页面元素用 `data-action` / `data-view` 委托给 `handleAction`/`go`；格式化直接用 `core.js` 的 `fmt/esc`，**不要内联裸拼接用户输入**（XSS）。

### 依赖版本 Go 模型

- 前端以 `API.load()` 拉 `/api/workspace` 快照进内存（`db`），本地过滤/渲染，写操作调后端对应接口。改后端 workspace_slice 时务必同步 `API.md` 契约与前端消费字段。

## 部署（服务器 /opt/lab，2GB 内存）

- 一键脚本 `lab-platform/scripts/deploy_server.sh`，流程：清残留 → `docker build lab-platform` → 起容器(自动 migrate，gunicorn **1 worker + 4 threads** 绑 8001) → ETL → 冒烟 → 铺 SPA 静态到 `/opt/lab/spa` → 改写 BT 面板 nginx `netbox_ssl.conf`。
- **内存红线**：2GB 机器只能 1 worker（多 worker 会 OOM，历史上用 2 个导致内存耗尽）。内存敏感时用 `free -h` 排查。
- **nginx 关键路径**（`/www/server/panel/vhost/nginx/netbox_ssl.conf`，BT 面板 nginx）：
  - `/api/` → proxy `127.0.0.1:8001`
  - `/media/` → proxy `127.0.0.1:8001`（Django 鉴权后返回）
  - `/assets/` → `alias /opt/lab/homepage/assets/`（营销首页静态资源，**单独 location，不可并入 `=` 块**，否则资源被代理到后端 404）
  - `/` → try_files 回退 `index.html`（SPA hash 路由无需 nginx rewrite）
- 静态目录权限：scp 后目录 755、文件 644，否则 nginx worker(www) 读不了报 500。
- HTTPS：Let's Encrypt 证书在 `/opt/lab/certs`，acme.sh cron 自动续期；80 强制 301 到 443。
- `etl.py`（一次性）：从旧 NetBox Postgres 抽数据到 `lab2` 库。生产注入 `SOURCE_DB_*` 环境变量执行；脚本只在注释里提到旧 venv 路径作为历史，**不要**依赖旧 NetBox 目录运行。

## 数据库与账号迁移状态

- 线上数据在 `lab2` Postgres 库（宿主机 netbox-postgres 容器 5432）。`auth_user`（Django 原生）+ `account_memberprofile`（成员档）+ 各业务表。
- 用户沿用原 NetBox 密码直接登录（同一 `auth_user`）。成员对外 ID 用 `apps.common.ids` 生成的短 ID，不要用裸主键/`username` 拼 URL。

## 开发常见任务

### 新增一个业务模块
1. 在 `apps/` 下建 app（模型继承 `models.Model`，普通 Django，非 NetBoxModel）。
2. `apps/<app>/models.py` → `apps/<app>/api.py`（函数式视图，`ok()/fail()`）。
3. `apps/<app>/urls.py` 定义接口，在 `lab_api/urls.py` 的 `api_patterns` 加入 `path('', include(...))`（前缀统一 `/api/`）。
4. `apps/common/workspace.py` 的 `build_workspace` 导入你的 `workspace_slice(profile, staff)` 把数据追加进快照。
5. `INSTALLED_APPS` 注册（`settings.py`）。`manage.py makemigrations <app>` + `migrate`（**普通 Django，可正常 makemigrations**，与旧 NetBox 不同）。
6. 前端 `src/features.js` 注册渲染与 `handleAction`，`core.js` 的 `NAV`/`CONFIG` 决定是否接入入口；`API.md` 同步契约。

### 测试
- 后端暂无 Django 测试目录；回归验证用 `scripts/deploy_server.sh` 的冒烟（`/api/auth/me`、`/media/` 预期 401/403）。
- 前端纯逻辑测试：`lab-platform-web/tests/*.test.mjs`，`npm test`。

## 关键坑（必读）

- 后端认证器务必保持返回 **401**（`authenticate_header`→`'Session'`）；改 403 会弄坏 SPA 登录判定。
- 前端 `index.html` 资源引用必须**绝对路径 `/src/`**；`MEDIA_URL` 已固定为 `/media/`（起 `/`）。二者相对化都会导致子路径 404。
- `API.md`、`core.js` 的 `workspace` 快照键、`accounts/api.py workspace` 三处**必须保持字段一致**，改后端快照结构要同步三处。
- 生产 nginx 静态资源 location（`/assets/`）与营销首页 `location = /` 分开，勿合并成万能块。
- 不要用裸 `username`/主键做客户端标识，用 `Mxxxx` 短 ID。