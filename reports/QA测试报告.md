# 实验室管理平台 — 全面测试报告

- **被测对象**：`http://localhost:8001/`（NetBox 4.6 + `lab_manager` 插件，本地部署）
- **代码版本**：`743c618`（与 GitHub `giaoLRL/Laboratory-Management-Platform` main 完全一致）
- **测试时间**：2026-09-10
- **测试账号**：`admin`（超管）、临时成员账号 `qa_member*`（测后已删除）
- **数据库**：PostgreSQL（Docker `netbox-postgres`），测试期间数据未被污染（临时对象均已清理）
- **报告原则**：**只写我亲自复现过的结论**。每条都带「现象 + 复现方式 + 代码位置」。实测推翻了若干代码审计推断，单列一节说明。

---

## 一、测试方法

| 手段 | 说明 | 产物 |
|---|---|---|
| 路由枚举 | 用 Django resolver 导出插件全部端点 | `plugin_urls.json`（121 条） |
| 全站 HTTP 扫描 | 96 个 URL × 管理员/匿名两态 + 页面链接爬取 | `sweep_results.json` |
| 500 栈追溯 | 解析 DEBUG 技术页 + 服务端日志 | `errors/*.html` |
| 权限/安全实测 | 令牌冒充、媒体文件匿名访问、越权 POST | `security_probe.py` |
| 业务逻辑验证 | 事务内回滚式 ORM 验证（信号/库存/文件清理） | `logic_probe.py` |
| 定点输入测试 | 非法 JSON、非法日期、非法 year 参数 | `final_probes.py` / `probe_final3.py` |
| 浏览器实测 | Playwright + 本机 Chrome，含移动端视口 | `browser_test.js` / `mobile_*.js` + 截图 |
| 代码审计 | 3 个子代理并行只读审计（后端/前端/业务流程） | 结论已逐条抽验 |

---

## 二、结论概览

| 级别 | 数量 | 说明 |
|---|---|---|
| **P0 严重** | 12 | 功能崩溃、数据错误、可直接利用的越权 |
| **P1 中等** | 12 | 特定场景出错、体验/性能/维护性问题 |
| **P2 轻微** | 6 | 健壮性、可维护性、文档 |

**好消息**：桌面端 8 个主要页面全部 200，**浏览器控制台 0 个 JS 错误**；CSRF POST 防护、超管专属页面拦截、移动端汉堡按钮、静态资源加载均正常。

---

## 三、P0 严重问题

### P0-1 借出归还功能整体崩溃（`AttributeError`）
- **现象/复现**：建一条借出记录后访问借出详情页 → **500**；访问归还页 → **500**；访问该借用人的成员详情页 → **500**。模型层直接调用：`rec.is_overdue` / `rec.mark_returned()` 均抛 `AttributeError`。
- **证据**：
  - `lab_manager/models/borrow.py:83` → `if self.status != self.BorrowStatusChoices.BORROWED:`
  - `lab_manager/models/borrow.py:91` → `self.status = self.BorrowStatusChoices.RETURNED`
  - `BorrowStatusChoices` 是**模块级类**（`borrow.py:11`），实例属性查找不会回溯模块全局 → 必然 `AttributeError`
  - 实测栈：`views.py:289 (get_extra_context)` / `views.py:1112 (MemberDetailView)` → `borrow.py:83 AttributeError`；日志另有 `views.py:348 → mark_returned`
  - 实测结果：`GET /borrow-records/6/` → **500**；`/members/3/` → **500**；`mark_returned()` → `AttributeError`；同一时刻 `/borrow-records/`（列表）与 `/edit/` → 200（列表不调用该属性，所以"创建能成功、之后全崩"）
- **影响**：硬件**永远无法归还**；只要库里存在任何借出记录，借出详情页与借用人成员页就 500。当前数据库借出记录为 0 条，属**潜伏缺陷**，一产生第一条数据即全面暴露。
- **修复**：`borrow.py` 顶部的模块级名直接用（`from .borrow import BorrowStatusChoices` 已在 views 使用）；建议补 `is_overdue` 单测。

### P0-2 全部站内通知失效，且附件物理文件永不清理
- **现象/复现**：在事务内创建 `Task`（指派给某人）、`Hardware`、`HardwareBorrowRecord` 后，`Notification` 数量始终为 **0**；创建附件 → 删除附件 → 物理文件仍在磁盘。
- **证据**：
  - `lab_manager/__init__.py:13-14` 的 `ready()` 只有 `super().ready()`，**没有 `from . import signals`**
  - `signals.py` 中 4 个接收器（`cleanup_attachment_file` / `notify_task_assigned` / `notify_hardware_approved` / `notify_borrow_created`）从未注册
  - 对照 NetBox 自身的写法：`users/apps.py:10` 明确写了 `from . import signals  # noqa: F401`
  - 实测：通知 0 条；删除 `TaskAttachment` 后探针文件仍存在
  - `views.py:801-803` 的注释断言"信号会清理文件"是错的（它同时手工删了一次，掩盖了症状）
- **影响**：任务分配、审批结果、借出通知全链路空转（通知页/未读计数永久为空）；附件留下孤儿文件。
- **修复**：`ready()` 中 `from . import signals  # noqa: F401`。**注意**：`signals.py:31-51` 的 `notify_hardware_approved` 没有 `created`/状态变化判断，一旦注册，每次 `Hardware.save()` 都会重复发通知（批量导入 N 条 = N 条通知），修复时需一并加状态比对。

### P0-3 借出不扣减库存，且无超借/并发约束
- **现象/复现**：硬件 `quantity=20`，登记借出后仍为 `20`；同一硬件+同一人可并存多条 `borrowed` 记录（实测 2 条）。
- **证据**：全插件无任何 `quantity` 写路径（grep 仅命中创建与聚合）；`HardwareBorrowRecord` 无唯一约束/条件约束；借出视图 `views.py:299-311` 无 `select_for_update`、无"未归还数 < quantity"校验。
- **影响**：已借出设备仍计入可用量，**低库存告警与硬件缺口分析系统性高估库存**；同一设备可被多人重复借出。
- **修复**：借出/归还时原子扣减，或改为"可用量 = quantity − 未归还数"的计算属性；加 `select_for_update`。

### P0-4 Agent API 可冒充任意用户（含超管）
- **现象/复现**：匿名（无任何会话）请求：
  ```
  POST /plugins/lab-manager/api/agent/members/search/
  X-Agent-Token: lab-manager-internal-token-change-me
  X-User-ID: 1          ← 超管 pk
  → 200 {"total":3, "items":[{...admin..., "email":"admin@lab.local"}, {huhan, 536098779@qq.com}...]}
  ```
  同一方式请求超管专属端点 `member-open-records/search/` → **200**。
- **证据**：`lab_manager/agent_api.py:130-142`（token 相等即信任 `X-User-ID`，不校验 `is_active`，也不回写 `request.user`）；`agent_api.py:179-182` `ensure_admin()` 只检查被断言的用户；token 值来自 `configuration.py` / `configuration_docker.py:27`，默认是 `lab-manager-internal-token-change-me`；11 个端点全部 `@csrf_exempt`（`:116`）且基类是裸 `View`，不受 `LOGIN_REQUIRED` 约束。
- **影响**：任何拿到该 token 的人（**默认值就写在仓库里**）可读全量成员邮箱、打卡记录，并以超管身份建任务、提交导入批次。
- **修复**：换成强随机 token 并只在服务端持有；`X-User-ID` 不应作为身份断言来源；限制 token 可用端点；`is_active` 校验。

### P0-5 媒体文件零鉴权：打卡照片、硬件发票、任务附件匿名可下载
- **现象/复现**：**匿名**（不带 cookie）GET 以下 URL 全部 **200**：
  ```
  /media/checkins/photos/DSC_0000085.jpg
  /media/task_attachments/DSC_0000387.jpg
  /media/hardware/physical/屏幕截图_2025-03-25_122026.png
  /media/hardware/invoice/屏幕截图_2025-07-01_133435.png
  ```
- **证据**：NetBox 的 `netbox/netbox/views/misc.py` `MediaView` 只对 `image-attachments/` 做对象级权限校验，注释明确写着插件上传目录"fall through"到直接 `serve(document_root=MEDIA_ROOT)`。
- **影响**：员工打卡照片（含位置语义）、财务发票、任务附件对**未登录用户**公开，只要路径泄露即可下载。
- **修复**：为插件上传目录加鉴权视图；文件名改为不可枚举（uuid）；生产环境对 `/media/` 关闭目录列举并加 `X-Content-Type-Options: nosniff`。

### P0-6 LLM 工具参数名与执行层不匹配 → 静默返回**未过滤**的数据
- **现象/复现**（直连工具层实测）：
  ```
  platform_query + filters={"status":"scrapped"}       → total=1（正确）
  platform_query + filters_json='{"status":"scrapped"}' → total=3（过滤被静默忽略！）
  get_record_detail + id=3        → 正常返回该记录
  get_record_detail + record_id=3 → 报错「get_record_detail 需要 id」
  ```
- **证据**：数据库 `AgentTool.parameters_schema` 用的是 `filters_json` / `fields_json` / `record_id`（实测 8 条工具记录），而执行层 `services/platform_data_service.py` 读的是 `filters` / `fields` / `id`；`services/tool_registry.py` 直接透传，无键名归一化。
- **影响**：LLM 按 schema 传参 → **所有筛选条件失效**，模型把"前 20 条全量数据"当成筛选结果总结（例如问"待审核硬件"返回在用/报废项），**答案错误但没有任何报错**；追问详情类工具永久失败。
- **修复**：在 `tool_registry` 里归一化 `filters_json→filters`、`fields_json→fields`、`record_id→id`（并 `json.loads` 失败给出明确错误），或统一改 DB schema。

### P0-7 Agent API 遇到非法输入直接 500
- **现象/复现**：
  ```
  POST /api/agent/hardware/search/   body=[]      → 500
                                     body=1       → 500
                                     body="x"     → 500
                                     body={}      → 200
  POST /api/agent/hardware/gap-analysis/ {"requirements":["开发板"]} → 500 (AttributeError)
  POST /api/agent/platform/query/ {"filters":{"created__gte":"abc"}}  → 500 (ValidationError)
  ```
- **证据**：`agent_api.py:144-149` `parse_json_body` 不校验顶层是 dict；`platform_data_service.py` 的日期过滤不做类型转换即 `filter(...__gte='abc')`，只捕获 `PlatformDataError`。
- **修复**：非 dict 直接返回 400；日期/数字解析失败抛业务异常；`requirements` 元素加类型判断。

### P0-8 带 `<int:pk>` 的操作页对不存在对象返回 500 而非 404（匿名也能触发）
- **现象/复现**：
  ```
  GET /borrow-records/1/return/     （记录不存在）→ 500 DoesNotExist   ← 匿名请求同样 500
  GET /notifications/1/read/        → 500 DoesNotExist
  GET /tasks/1/comment/             → 500 ImproperlyConfigured（缺 template_name）
  ```
- **证据**：`views.py:329`（`dispatch` 内先查库再校验权限，故匿名也能触发）、`views.py:893`、`views.py:346`、`views.py:760` 等多处 `Model.objects.get(pk=...)` 未走 `get_object_or_404`。
- **影响**：任意用户（含未登录）可用一条 URL 打出 500 错误页与日志噪声；健康检查/爬虫会大量触发。
- **修复**：统一改 `get_object_or_404`；`TaskCommentView` 补 `template_name` 或只允许 POST（GET 应 405）。

### P0-9 智能体工具管理页的批量操作完全不可用
- **现象/复现**：`/plugins/lab-manager/agent-tools/` 列表页的 **Edit Selected / Delete Selected** 按钮 HTML 为 `formaction="None"`（URL 反解失败），点击会提交到非法地址；直接访问批量路由：
  ```
  GET /plugins/lab-manager/agent-tools/1/bulk_delete/ → 500 TypeError
  GET /plugins/lab-manager/agent-tools/1/bulk_edit/   → 500 TypeError
  reverse('plugins:lab_manager:agenttool_bulk_delete') → NoReverseMatch
  ```
  报错：`BulkDeleteView.get() got an unexpected keyword argument 'pk'`
- **证据**：`views.py:1437,1447` 的 `@register_model_view(AgentTool, 'bulk_delete'/'bulk_edit')` 未传 `detail=False`（NetBox 默认 `detail=True`），被注册成详情视图。对照框架惯例：`netbox/core/views.py:158,174` 用 `detail=False` + `path='edit'`。
- **影响**：AGENTS.md 宣称的"支持批量操作"徒有其名；两个路由是必然 500 的坏路由。
- **修复**：改为 `@register_model_view(AgentTool, 'bulk_delete', path='bulk-delete', detail=False)`（bulk_edit 同理）。

### P0-10 全站 17 个"导入"页面全部 500
- **现象/复现**：以下页面全部 500（`NoReverseMatch: 'core-api' is not a registered namespace`）：
  `/users/users/import/`、`/users/groups/import/`、`/users/tokens/import/`、`/users/owners/import/`、`/users/owner-groups/import/`、`/extras/tags/import/`、`/extras/custom-fields/import/`、`/extras/custom-links/import/`、`/extras/webhooks/import/`、`/extras/event-rules/import/`、`/extras/config-context-profiles/import/`、`/extras/export-templates/import/`、`/extras/saved-filters/import/`、`/extras/notification-groups/import/`、`/extras/journal-entries/import/`、`/extras/custom-field-choices/import/`、`/core/data-sources/import/`
- **证据**：栈为 `utilities/forms/fields/dynamic.py:177 get_bound_field` → `utilities/views.py:338 get_action_url` → `reverse('core-api:...')`。根因：`netbox/netbox/urls.py` 只挂了 `api/extras/`、`api/users/`，**没有挂 NetBox 核心 API 路由**（`/api/` 根也 404），而导入表单的动态字段要反解 `core-api` 命名空间。这些入口是每个页面顶部下拉菜单里的「Import」图标（已确认在渲染出的 HTML 中）。
- **说明**：裁剪 NetBox 核心可能是**有意为之**，但结果是这些菜单入口全部报错。
- **修复**：挂回核心 API 路由，或在模板/字段层去掉对 `core-api` 的反解（把 Import 入口一并隐藏）。

### P0-11 `GET /notifications/read-all/` 即可清空全部未读（无 CSRF 保护的状态变更）
- **现象/复现**：登录状态下 `GET /plugins/lab-manager/notifications/read-all/` → **200 且全部通知被标记已读**；同路径 POST 不带 CSRF token → 403（POST 防护正常）。
- **证据**：`views.py:883` `NotificationMarkReadView` 的 GET/POST 都执行写操作。
- **影响**：一个 `<img src="...read-all/">` 即可让受害者的通知全部丢失。
- **修复**：状态变更只允许 POST，GET 返回 405 或仅渲染确认页。

### P0-12 日历等页面对 GET 参数直接 `int()` → 500
- **现象/复现**：
  ```
  /plugins/lab-manager/calendar/?year=abc   → 500
  /plugins/lab-manager/calendar/?year=99999 → 500
  /plugins/lab-manager/calendar/?year=      → 500
  /plugins/lab-manager/members/3/?cal_year=abc → 500
  ```
- **证据**：`views.py:967-968`、`views.py:1136-1137` 直接 `int(request.GET.get(...))`，无 try/except，且 year 无范围夹取（`month` 有）。
- **修复**：包 try/except 回退当前年月并夹取合理范围。

---

## 四、P1 中等问题

### P1-1 打卡重复提交无幂等；且"打开打卡页"也被计为一条打卡类记录
- **实测**：同一份 payload 连发 2 次 POST → 落库 **2 条 `CheckInRecord`**，同时产生 **4 条 `MemberOpenRecord(target_type='checkin')`**（2 次 GET 打开页面各记 1 条 + 2 次 POST 各记 1 条）。
- **证据**：`views.py:559-590` 无幂等键/时间窗；`views.py:550` 在 GET 时也调用 `record_member_open(..., target_type='checkin')`；`views.py:477` 的统计正是按 `target_type='checkin'` 计数。
- **影响**：连点/刷新即产生重复打卡；**统计口径把"打开页面"算成打卡**，报表数据不可信。
- **修复**：POST 幂等（同用户+时间窗去重）、GET 不计入打卡类记录。

### P1-2 打卡表单缺 `tags` 字段，且提交按钮启用条件不含照片
- **实测**：表单字段为 `latitude/longitude/accuracy/address/note/photo`（**无 `tags`**）；`photo` 有 `required`；JS 条件为 `submitButton.disabled = !(latitude.value && longitude.value)`（`checkin_form.html`），**不检查照片**。
- **说明**：`CheckInForm` 的 `fields` 含 `tags` 但模板未渲染 → 标签被静默丢弃。实测注入经纬度后按钮仍为 disabled（事件绑定方式不同），故"未选照片即可提交"未能复现，需真机 GPS 流程确认。

### P1-3 智能体控制台"删除会话"按钮必然 404
- **实测**：页面 JS 中硬编码 `fetch('/plugins/lab-manager/agent-conversation/' + pk + '/delete/')`；`POST /plugins/lab-manager/agent-conversation/1/delete/` → **404**；`reverse('...agent_conversation_delete')` → NoReverseMatch（路由不存在）。
- **影响**：点击"⋯ → 删除 → 确认"必然弹"删除失败，请重试"，功能静默坏死。
- **修复**：补视图+路由，或先隐藏该按钮。

### P1-4 屏蔽 `animations.js` 后首页统计卡全部显示 `0`
- **实测**（Playwright 拦截 `**/animations.js`）：5 张统计卡仍可见（opacity=1），但数值全部为 **0**（正常时应为 3/2/0/12/1）。
- **说明**：数字由 JS 计数动画写入，HTML 初始值即 0 → 脚本被拦截/未加载时展示**误导性数据**（比"不可见"更糟）。前端审计称"永久不可见"与实测不符，以实测为准。
- **修复**：服务端渲染真实数值，JS 只做动画增强。

### P1-5 导出页可选模型与管理命令不一致
- **实测**：`templates/lab_manager/export.html` 提供 `hardware/tasks/checkins/borrow_records/projects` 五个选项；`management/commands/export_lab_data.py` 的 `choices` 只有 `hardware/tasks/checkins` → 选后两者必然 "invalid choice"。且 `ExportDataView` 本身不产出文件，只回显命令。

### P1-6 文件类型校验器是死代码（潜在存储型 XSS）
- **证据**：`validators.py:38,48` 定义 `validate_image_type` / `validate_attachment_type`，全仓库**无任何引用**；`TaskAttachment.file` 只挂 `validate_file_size`；`MemberOpenRecord.photo` 连大小校验都没挂。
- **影响**：附件可上传 `.html/.svg/.js`，配合 P0-5 的匿名可访问 `/media/`，构成存储型 XSS 素材。
- **修复**：挂上类型校验；对 `/media/` 加 `Content-Disposition: attachment` + `nosniff`。

### P1-7 项目没有任何自动化测试，且测试命令根本跑不起来
- **实测**：`lab_manager/tests/` 目录不存在 → `python manage.py test lab_manager --keepdb` 输出 **"Found 0 test(s)"**；并且直接 `SystemCheckError: (debug_toolbar.E001) The Django Debug Toolbar can't be used with tests`（因为 DEBUG=True）。
- **影响**：根 `AGENTS.md:54-55` 推荐的测试命令**不可用**（双重原因：无测试 + debug_toolbar 冲突）；本次发现的 P0-1 这类回归无法被自动化拦下。
- **修复**：建 `tests/` 包；测试时设 `ENABLE_DEBUG_TOOLBAR=False` 或 `DEBUG_TOOLBAR_CONFIG['IS_RUNNING_TESTS']=False`；至少补借出/审批/打卡的核心用例。

### P1-8 明显 N+1 与无上限加载
- `views.py:1027-1056` `MemberListView` 每个用户约 11 次 `count()`（50 人 ≈ 550 次查询）
- `services/platform_data_service.py` 的 `user` 模型每行 4 次 `count()`（limit 上限 100 → 400 次）
- `agent_api.py:712-713` `SearchTaskVideosAPIView` 不处理 limit，全量载入任务及其附件
- `views.py:1246` 智能体会话 `messages.all()` 无分页，长会话全量渲染
- **修复**：`annotate(Count(...))` 聚合、加分页与 limit 上限。

### P1-9 移动端 390px 下登录表单控件被其它元素遮挡
- **实测**：390×844 视口下对登录按钮中心点做 `elementFromPoint` → 命中 **`A.AlertsPanel`**（元素位于 x=170,y=608,w=220,h=39，与按钮 45..345×590..636 重叠）；Playwright **真实点击超时失败**，`force:true` 才成功。用户名输入框中心命中 `SMALL`、密码框命中 `A.StaticFilesPanel`。
- **说明**：这些类名不在仓库源码中（来自收集的静态资源），需在真机 DevTools 复核归属；但"窄屏点击被遮挡"有两条独立证据。
- **修复**：定位覆盖元素，加 `pointer-events:none` 或调整层级/定位。

### P1-10 智能体工具链的权限与参数语义缺陷
- `requires_superuser` 只在 LangChain 路径生效（`langchain_agent_service.py:200`），降级路径 `agent_tool_orchestrator.py` 直接调 `execute_tool`，不读该标志；其中 `find_members` 无任何权限校验且返回停用账号邮箱。
- `AgentTool.effective_execution_key` 为空时回退为 `name`，但内置工具名（`list_records` 等）**都不等于** `TOOL_REGISTRY` 的键（`platform_query` 等）→ 管理员照帮助文本留空必然报"未知工具执行标识"。
- LLM 调用无最大迭代/总超时/限流；前端 30s 就中断，服务端仍在跑并继续消耗额度。

### P1-11 借出记录对象的查看/编辑缺少归属校验（视图层）
- **实测**：临时成员账号能打开**他人**借出记录的编辑页（GET → 200）与详情页；列表页对非超管有 `filter(borrower=self.request.user)`，但详情/编辑视图没有对应判断。
- **但我未能复现写入**：同一账号 POST 后 `notes` 未改变（返回 200 无可见报错），而超管同样的 POST → 302 且写入成功。**结论：读取侧确认开放，写入侧未证实**，建议人工确认设计意图后再定级。

### P1-12 文档与实现大面积不一致（误导后续开发）
- `AGENTS.md`：模型数写"9 个文件/9 个模型"（实际 11 个 .py / **13 个模型**）、工具处理器"6 个"（实际 **7 个**，且名单里漏 `image_search`、多写不存在的默认工具 `find_members`）、`lab_manager.css` "~290 行"（实际 **662~720 行**）、称模板继承 `generic/*.html`（实际继承 `lab_manager/base.html`）、测试命令不可用（见 P1-7）。
- `docs/` 下 12 个文档描述了 6 个**根本不存在**的模型（`LabDeviceType`/`LabDevice`/`TaskType`/`TaskLog`/`Video`/`VideoTag`）、看板拖拽、二维码、dashboard widget、Coze/Dify 网关；`Dify配置信息.py` 里还带着真实 API Key。
- **建议**：以代码为准重写 AGENTS.md 的关键数字与命令，归档 `docs/` 中已作废的方案文档。

---

## 五、P2 轻微 / 优化点

1. **任务评论的标签被静默丢弃**：`views.py:765-770` 用 `form.save(commit=False)` 后直接 `comment.save()`，未调用 `form.save_m2m()`（对照 `views.py:566` 打卡视图有正确调用）。
2. **同一张照片被两条记录共享**：`views.py:576` 把 `checkin.photo` 原样赋给 `MemberOpenRecord.photo`，删任一记录/文件会影响另一条。
3. **`_()` 包裹运行时 f-string 无法翻译**：`views.py:938,948`；且通知群发无事务、无 `bulk_create`，中途失败会留下部分已发送。
4. **API 响应缺少 `url` 自链接字段**（NetBox API 约定要求），且 `TaskComment/Notification/AgentConversation/AgentMessage/HardwareImportBatch` 没有 FilterSet → API 的 `?q=`/字段过滤静默无效。
5. **CSS 维护性问题**：`terminal_pixel.css` 2982 行含 401 处 `!important`；存在重复规则与死规则（如 `.agent-debug-panel` 无对应 DOM）；`member_detail.html` 内联样式与主题表互相覆盖；`.tp-page{overflow-x:hidden}` + 表格 `min-width:480px` 的组合依赖 `.table-responsive` 才能滚动（实测 390px 下页面无横向溢出、表格容器可滚动，未复现"列被切掉"）。
6. **死代码**：`views.py:1381-1385` `_is_write_operation` 从未被调用；`services/web_search.py` 整个类无引用（其中 `read_page()` 把用户可控 URL 拼到 `https://r.jina.ai/`，**接入工具链前必须加白名单**，否则是 SSRF 点）；`__pycache__` 里残留 `coze_gateway`/`dify_gateway` 字节码但无源码。

---

## 六、实测确认「没问题」的项（避免误伤）

- 桌面端 8 个页面（首页/硬件/任务/成员/打卡/签到/日历/智能体）**全部 200，控制台 0 错误**。
- **智能体历史消息的 Markdown 渲染正常**：`conversation=66` 页面实测 `hasStrong=true, hasTable=true, rawMarkdownLeft=false`（前端审计称"刷新后退化为裸文本"，**被实测推翻**）。
- 移动端 390px：**汉堡按钮正常可见可点**（38×44，`d-lg-none`），侧边栏为 240px off-canvas 抽屉（`translateX(-240px)`），页面无横向溢出。
- 打卡页在 390px 下输入框位于首屏之下（y=894–1047），但页面可纵向滚动（`scrollHeight=1626 > 844`），**可以滚动到达**，不属于"不可达"。
- 静态资源（`netbox.css` 565KB 等）全部 200；登录/跳转 `LOGIN_REDIRECT_URL` 正常。
- **CSRF POST 保护有效**（无 token → 403）；超管专属页面（成员浏览记录/工具管理/硬件删除）对普通成员返回 403 或重定向。

## 七、被实测推翻或未能复现的审计推断（供参考，避免按其修改代码）

| 推断 | 实测结果 |
|---|---|
| 刷新后历史消息 Markdown 退化 | ❌ 渲染正常 |
| `CreateTaskAPIView` 的 deadline 解析会抛 TypeError（500） | ❌ 代码有 `if parsed_date else None` 守卫，不会崩 |
| `AgentTool` 表为空/未播种 → 一直走 fallback 工具集 | ❌ 库里实有 8 条启用工具 |
| 屏蔽 JS 后统计卡永久不可见 | ⚠️ 可见，但数值显示为 0 |
| 打卡页只填经纬度即可提交（绕过照片） | ⚠️ 实测按钮仍 disabled，未复现 |
| 普通成员可改写他人借出记录 | ⚠️ 编辑页可见（200），但 POST 未生效，未复现 |
| 移动端无法打开导航菜单 | ❌ 我最初选择器取错元素，汉堡按钮正常 |
| 移动端聊天输入框"被裁掉不可达" | ⚠️ 需下滑，但可达 |
| 借出列表页会因 `is_overdue` 500 | ❌ 列表页不调用该属性，200 正常 |

## 八、修复优先级建议

1. **今天就能改、影响最大**：P0-1（`self.BorrowStatusChoices` → 模块级名）、P0-2（`ready()` 里 import signals，同时加状态判断）、P0-11（read-all 改 POST）、P0-12（year 参数 try/except）、P0-8（`get_object_or_404`）。
2. **安全类，尽快**：P0-4（换 token、不信任 `X-User-ID`）、P0-5（媒体鉴权）。
3. **智能体正确性**：P0-6（工具参数名归一化）、P0-7（输入校验）。
4. **框架级**：P0-9（`detail=False`）、P0-10（核心 API 命名空间或隐藏 Import 入口）。
5. **数据正确性**：P0-3（库存扣减）、P1-1（打卡幂等与统计口径）。
6. **工程化**：P1-7（补测试与修测试命令）、P1-12（文档校准）。

## 九、本次测试产物

| 文件 | 说明 |
|---|---|
| `reports/qa/plugin_urls.json` | 121 条插件端点清单 |
| `reports/qa/sweep_results.json` | 全站扫描原始结果（含状态码/耗时） |
| `reports/qa/errors/*.html` | 12 个 500 技术页快照（含栈） |
| `reports/qa/*.py` | 权限/逻辑/定点测试脚本（可重复执行） |
| `reports/qa/*.js` | Playwright 浏览器测试脚本 |
| `reports/qa/shot-*.png`、`mobile-*.png` | 桌面/移动端截图 |
| `reports/qa/testsuite.log` | 测试套件运行输出（Found 0 test(s)） |
| `reports/runserver-8001.err.log` | 服务端日志（全部 traceback 来源） |

> 所有临时数据库对象（测试借出记录、`qa_member*` 账号、重复打卡记录及其图片文件）均已清理；`qa_member` 系列账号已删除。
