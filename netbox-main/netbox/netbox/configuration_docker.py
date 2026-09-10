import os
from netbox.configuration import *

ALLOWED_HOSTS = ["*"]
DEBUG = True

# 关闭 Django Debug Toolbar：它会遮挡窄屏页面控件，且导致 manage.py test 无法运行
ENABLE_DEBUG_TOOLBAR = False
SECRET_KEY = "JI-wq1y%gBCSorighg9CIf!EGfKCtPOoMd4(Oq@2kanNo@KR1X"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "netbox",
        "USER": "netbox",
        "PASSWORD": "netbox123",
        "HOST": "netbox-postgres",
        "PORT": "5432",
    }
}

REDIS = {
    "tasks": {"HOST": "netbox-redis", "PORT": 6379, "DATABASE": 0, "SSL": False},
    "caching": {"HOST": "netbox-redis", "PORT": 6379, "DATABASE": 1, "SSL": False},
}

PLUGINS = ["lab_manager"]
PLUGINS_CONFIG = {
    "lab_manager": {
        # 网关令牌：必须替换为随机值（仓库内不要保留示例值）
        "agent_api_token": "labmgr_kCwTO11gxUU2sKUUbe2TX9bRJbrUN5pmfW7afQ4K-gU",
        # 是否允许网关用 X-User-ID 代任意成员调用 Agent API
        "agent_api_allow_user_impersonation": True,
        # 是否允许网关冒充超级管理员（默认关闭）
        "agent_api_allow_superuser_impersonation": False,
        # LangChain 智能体 (支持任意 OpenAI 兼容端点)
        "langchain_api_key": os.getenv("LAB_MANAGER_LANGCHAIN_API_KEY", ""),
        "langchain_base_url": os.getenv("LAB_MANAGER_LANGCHAIN_BASE_URL", ""),
        "langchain_model": os.getenv("LAB_MANAGER_LANGCHAIN_MODEL", "gpt-4o-mini"),
        "langchain_temperature": 0.1,
        "langchain_timeout": 60,
    }
}

MEDIA_ROOT = os.path.join(os.path.dirname(__file__), "media")
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
