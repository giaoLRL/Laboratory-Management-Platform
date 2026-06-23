import os
from netbox.configuration import *

ALLOWED_HOSTS = ["*"]
DEBUG = True
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
        "agent_api_token": "lab-manager-internal-token-change-me",
        "dify_api_base_url": "http://nginx",
        "dify_api_key": "app-4a0955a232d44ddc985e4aaa",
        "dify_timeout": 60,
        # Optional: enable LangChain tool-calling agent with any OpenAI-compatible endpoint.
        # Keep langchain_api_key empty to use the local deterministic tool orchestrator fallback.
        "langchain_api_key": os.getenv("LAB_MANAGER_LANGCHAIN_API_KEY", ""),
        "langchain_base_url": os.getenv("LAB_MANAGER_LANGCHAIN_BASE_URL", ""),
        "langchain_model": os.getenv("LAB_MANAGER_LANGCHAIN_MODEL", "gpt-4o-mini"),
        "langchain_temperature": 0.1,
        "langchain_timeout": 60,
        "dify_workflow_api_keys": {
            "hardware_query": "app-f4e774d913fa4ec5ac61c3fe",
            "hardware_gap_analysis": "app-70591b3157f74127b181f15f",
            "task_video_search": "app-50e71c28d140437e9c14af6f",
            "hardware_import_validate": "app-7db5adb2c5c74a5097b9f954",
            "hardware_import_commit": "app-f1e0db7f4d9241d1baed90b0",
        },
    }
}

MEDIA_ROOT = os.path.join(os.path.dirname(__file__), "media")
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
