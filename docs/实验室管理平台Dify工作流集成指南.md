# 实验室管理平台 Dify 工作流集成指南

> 用途：替代原扣子(Coze)空间工作流，使用 Dify 社区版实现 AI 智能体能力。
>
> 版本：v2.0（Dify 迁移版）
>
> Dify 服务地址：http://localhost

---

## 一、`configuration.py` 配置块

在 `netbox/netbox/configuration.py` 中补充（替换原 Coze 配置）：

```python
PLUGINS_CONFIG = {
    "lab_manager": {
        # 内部 Agent API 令牌（Dify 工作流回调平台时使用）
        "agent_api_token": "replace-with-internal-agent-token",

        # ── Dify 配置 ──
        "dify_api_base_url": "http://localhost",
        "dify_api_key": "app-xxxxxxxxxxxxxxxxx",     # Dify Chat 应用 API Key
        "dify_timeout": 60,

        # 工作流别名 → API Key 映射（每个工作流在 Dify 中发布后获取独立 API Key）
        "dify_workflow_api_keys": {
            "hardware_query":           "app-xxxxxxxxxxxx1",
            "hardware_gap_analysis":    "app-xxxxxxxxxxxx2",
            "task_video_search":        "app-xxxxxxxxxxxx3",
            "hardware_import_validate": "app-xxxxxxxxxxxx4",
            "hardware_import_commit":   "app-xxxxxxxxxxxx5",
        },
    }
}
```

> 如果你原来有 `PLUGINS_CONFIG`，只把 `lab_manager` 部分合进去，不要整段覆盖。

---

## 二、工作流别名说明

当前项目中，前后端和文档使用以下别名，与原扣子一致：

| 工作流别名 | 用途 |
|---|---|
| `hardware_query` | 硬件库存查询 |
| `hardware_gap_analysis` | 产品硬件缺口分析 |
| `task_video_search` | 已完成任务视频检索 |
| `hardware_import_validate` | 导入预校验 |
| `hardware_import_commit` | 导入正式提交 |

---

## 三、在 Dify 中创建工作流

### 3.1 访问 Dify

打开浏览器访问 `http://localhost`，首次使用需创建管理员账号。

### 3.2 创建 Chat 应用（用于对话模式）

1. 进入 Dify 首页 → 创建应用 → 选择 **"聊天助手"**
2. 配置 LLM 模型（建议使用 OpenAI 兼容接口或本地模型）
3. 添加知识库（可选，可上传实验室相关文档）
4. 编写系统提示词，让 LLM 理解如何调用平台 API
5. 发布 → 获取 API Key → 填入 `dify_api_key`

### 3.3 创建工作流应用（用于 5 个功能工作流）

对每个工作流别名，创建独立的工作流应用：

1. 进入 Dify → 创建应用 → 选择 **"工作流"**
2. 编排工作流节点（详见下方模板）
3. 发布 → 获取 API Key → 填入 `dify_workflow_api_keys`

---

## 四、工作流模板一：硬件库存查询（`hardware_query`）

### 4.1 工作流节点

```
开始（接收 user_query）
  → LLM 提取搜索参数
  → HTTP 请求（调用平台 search_hardware API）
  → LLM 整理结果
  → 结束
```

### 4.2 HTTP 节点配置

```json
{
  "method": "POST",
  "url": "{{base_url}}/plugins/lab-manager/api/agent/hardware/search/",
  "headers": {
    "Content-Type": "application/json",
    "X-Agent-Source": "dify-workflow",
    "X-Agent-Token": "{{agent_api_token}}",
    "X-Request-ID": "{{request_id}}",
    "X-User-ID": "{{user_id}}"
  },
  "body": {
    "keywords": "{{keywords}}",
    "category": "{{category}}",
    "status": "{{status}}",
    "approval_status": "approved",
    "limit": 10,
    "offset": 0
  }
}
```

---

## 五、工作流模板二：产品硬件缺口分析（`hardware_gap_analysis`）

### 5.1 工作流节点

```
开始（接收 user_query, project_name）
  → LLM 提取产品需求清单
  → HTTP 请求（调用平台 gap-analysis API）
  → LLM 生成采购建议
  → 结束
```

### 5.2 HTTP 节点配置

```json
{
  "method": "POST",
  "url": "{{base_url}}/plugins/lab-manager/api/agent/hardware/gap-analysis/",
  "headers": {
    "Content-Type": "application/json",
    "X-Agent-Source": "dify-workflow",
    "X-Agent-Token": "{{agent_api_token}}",
    "X-Request-ID": "{{request_id}}",
    "X-User-ID": "{{user_id}}"
  },
  "body": {
    "project_name": "{{project_name}}",
    "requirements": "{{requirements}}"
  }
}
```

---

## 六、工作流模板三：任务视频检索（`task_video_search`）

### 6.1 工作流节点

```
开始（接收 user_query）
  → LLM 提取搜索条件
  → HTTP 请求（调用平台 tasks/search API）
  → 提取任务 ID 列表
  → HTTP 请求（调用平台 tasks/videos API）
  → LLM 汇总输出
  → 结束
```

---

## 七、工作流模板四/五：两段式硬件导入

### 7.1 第一阶段：预校验

```
开始（接收 items 数组）
  → HTTP 请求（调用 validate API）
  → LLM 展示校验结果
  → 结束
```

### 7.2 第二阶段：确认提交

```
开始（接收 batch_id + confirm）
  → HTTP 请求（调用 commit API）
  → LLM 展示导入结果
  → 结束
```

---

## 八、平台 API 接口不变

以下接口从扣子切换到 Dify 后完全保持不变，Dify 工作流调用方式与扣子相同：

| 接口 | 用途 |
|---|---|
| `POST /plugins/lab-manager/api/agent/hardware/search/` | 硬件查询 |
| `POST /plugins/lab-manager/api/agent/hardware/gap-analysis/` | 缺口分析 |
| `POST /plugins/lab-manager/api/agent/tasks/search/` | 任务查询 |
| `POST /plugins/lab-manager/api/agent/tasks/videos/` | 视频检索 |
| `POST /plugins/lab-manager/api/agent/hardware/import/validate/` | 导入预校验 |
| `POST /plugins/lab-manager/api/agent/hardware/import/commit/` | 导入提交 |

### 通用请求头

```http
Content-Type: application/json
X-Agent-Source: dify-workflow
X-Agent-Token: {internal_service_token}
X-Request-ID: {request_id}
X-User-ID: {current_user_id}
```

> 注意：`X-Agent-Source` 从 `coze-workflow` 改为 `dify-workflow`。

---

## 九、从扣子迁移到 Dify 的对照表

| 扣子概念 | Dify 对应概念 |
|---|---|
| 扣子空间(Bot) | Dify Chat 应用 |
| 扣子工作流 | Dify 工作流应用 |
| PAT Token | API Key（app-xxx） |
| Bot ID | 不需要（一个应用一个 Key） |
| coze.site 直连 | Dify HTTP API |
| `coze_workflow_ids` | `dify_workflow_api_keys` |

---

## 十、推荐上线顺序

1. 在 Dify 中创建管理员账号，配置 LLM 模型
2. 创建 **Chat 应用**，获取 `dify_api_key` 填入配置
3. 创建 `hardware_query` 工作流，联调测试
4. 创建 `hardware_gap_analysis` 工作流
5. 创建 `task_video_search` 工作流
6. 最后创建两段式导入工作流

---

> 文档版本：v2.0（Dify 迁移版）
>
> 创建日期：2026-06-22
>
> 替代文档：`实验室管理平台扣子工作流映射模板.md`
