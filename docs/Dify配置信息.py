# ============================================================
# 实验室管理平台 - Dify 集成配置 (最终版)
# 日期: 2026-06-22
# ============================================================
# 
# 将以下内容合并到 netbox/netbox/configuration.py 的 PLUGINS_CONFIG 中
#
# DeepSeek v4 Pro 模型配置:
#   - deepseek-chat:   日常对话/工具调用 (已配置)
#   - deepseek-reasoner: 深度推理 (已配置)
#   - API Key: sk-e734158e9b3f43f89e4c5605912a0d19
#   - Endpoint: https://api.deepseek.com/v1
# ============================================================

PLUGINS_CONFIG = {
    "lab_manager": {
        # 内部 Agent API 令牌（Dify 工作流回调平台时使用）
        "agent_api_token": "lab-manager-internal-token-change-me",

        # ── Dify 配置 ──
        "dify_api_base_url": "http://localhost",        # Dify 服务地址
        "dify_api_key": "app-3MP70Yo0PXdBfkgFGTak7CIO", # Chat 应用: 实验室智能助手
        "dify_timeout": 60,

        # 工作流别名 → API Key 映射
        "dify_workflow_api_keys": {
            "hardware_query":           "app-pAOJCev656faqp44EfJDj5y1",
            "hardware_gap_analysis":    "app-bclnk6wmYINXHKDixYmyn0Gl",
            "task_video_search":        "app-nCGgvYelAjyCFjuX2CPUrO36",
            "hardware_import_validate": "app-kSQKC46fRyl1EiChDZqrLsT5",
            "hardware_import_commit":   "app-qP8KbsY6wlcp8BP6ZR8KPEyG",
        },
    }
}

# ============================================================
# Dify 应用信息速查
# ============================================================
# 
# Dify 访问: http://localhost
# 登录: 536098779@qq.com / LabAdmin123!
#
# Chat 应用:
#   名称: 实验室智能助手
#   ID:   b2836cff-f601-4032-b85b-056d554ec0d1
#   Key:  app-3MP70Yo0PXdBfkgFGTak7CIO
#
# 工作流应用 (均已使用 deepseek-chat 模型):
#   hardware_query (硬件库存查询):
#     ID: 86741986-46dd-4b83-98f2-ac020da02d11
#     Key: app-pAOJCev656faqp44EfJDj5y1
#
#   hardware_gap_analysis (产品硬件缺口分析):
#     ID: e0840703-f1f3-4a4b-b5a2-44579534f357
#     Key: app-bclnk6wmYINXHKDixYmyn0Gl
#
#   task_video_search (任务视频检索):
#     ID: fd027f1b-4759-41f7-b579-9a85620ab896
#     Key: app-nCGgvYelAjyCFjuX2CPUrO36
#
#   hardware_import_validate (硬件导入预校验):
#     ID: 816555f2-ec7d-49ab-b256-93f395397bff
#     Key: app-kSQKC46fRyl1EiChDZqrLsT5
#
#   hardware_import_commit (硬件导入正式提交):
#     ID: 7b88d3a9-e7d5-46c5-b7e9-792db6e37fb2
#     Key: app-qP8KbsY6wlcp8BP6ZR8KPEyG
#
# ============================================================
# 模型供应商配置
# ============================================================
# 
# 插件: langgenius/openai_api_compatible v0.0.53
# 供应商: OpenAI-API-compatible
# 模型:
#   - deepseek-chat (LLM, chat模式, 支持function_calling, 上下文65536)
#   - deepseek-reasoner (LLM, chat模式, 上下文65536)
# API Key: sk-e734158e9b3f43f89e4c5605912a0d19
# Endpoint: https://api.deepseek.com/v1
#
# ============================================================
# 代码架构
# ============================================================
# 
# services/dify_gateway.py: Dify API 封装（兼容原 CozeGateway 接口）
# services/coze_gateway.py: 原扣子网关（保留，可移除）
# views.py: AgentProxyAPIView 已切换为 DifyGateway()
# agent_api.py: Dify 工作流回调 Netbox 的 Agent API 端点
#
# ============================================================
