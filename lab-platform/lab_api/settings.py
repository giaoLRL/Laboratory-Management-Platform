"""具身智能实验室 · 管理平台后端配置

环境变量（生产部署时由 docker-compose / systemd 注入）：
  LAB_SECRET_KEY      生产密钥（本地开发有默认值，生产必须显式设置）
  LAB_DEBUG           '1' 开启调试（默认），生产设为 '0'
  LAB_ALLOWED_HOSTS   逗号分隔
  LAB_DB_ENGINE       'sqlite'（默认，本地开发） / 'postgres'（生产）
  LAB_DB_NAME/HOST/PORT/USER/PASSWORD
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('LAB_SECRET_KEY', 'dev-only-secret-key-change-in-production')
DEBUG = os.environ.get('LAB_DEBUG', '1') == '1'
ALLOWED_HOSTS = [h.strip() for h in os.environ.get(
    'LAB_ALLOWED_HOSTS', '127.0.0.1,localhost,wuyuan.me,www.wuyuan.me').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'rest_framework',
    'apps.common',
    'apps.accounts',
    'apps.inventory',
    'apps.leaves',
    'apps.competitions',
    'apps.tasksapp',
    'apps.checkins',
    'apps.agent',
    'apps.notify',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
]

# CSRF 策略：同源 SPA + SameSite=Lax 会话 Cookie 阻断跨站携带会话；
# DRF 层使用 apps.common.auth.CsrfExemptSessionAuthentication 豁免强制校验。
ROOT_URLCONF = 'lab_api.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {'context_processors': []},
    },
]

WSGI_APPLICATION = 'lab_api.wsgi.application'

# ── 数据库：本地开发默认 SQLite，生产切 Postgres ──
if os.environ.get('LAB_DB_ENGINE', 'sqlite') == 'postgres':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('LAB_DB_NAME', 'lab2'),
            'HOST': os.environ.get('LAB_DB_HOST', 'postgres'),
            'PORT': os.environ.get('LAB_DB_PORT', '5432'),
            'USER': os.environ.get('LAB_DB_USER', 'lab2'),
            'PASSWORD': os.environ.get('LAB_DB_PASSWORD', ''),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = []  # 密码规则在 API 层自校验：8-64 位，至少一个字母一个数字

LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
MEDIA_URL = 'media/'
MEDIA_ROOT = Path(os.environ.get('LAB_MEDIA_ROOT', BASE_DIR / 'media'))
# 开发模式托管的 SPA 目录
LAB_WEB_DIR = os.environ.get('LAB_WEB_DIR', str(BASE_DIR.parent / 'lab-platform-web'))
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB，打卡照片上传

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── LLM 智能体（DeepSeek OpenAI 兼容协议） ──
LAB_LLM_API_KEY = os.environ.get('LAB_LLM_API_KEY', '')
LAB_LLM_BASE_URL = os.environ.get('LAB_LLM_BASE_URL', 'https://api.deepseek.com')
LAB_LLM_MODEL = os.environ.get('LAB_LLM_MODEL', 'deepseek-chat')

# ── 会话与安全 ──
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # 7 天
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_CONTENT_TYPE_NOSNIFF = True

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ('apps.common.auth.CsrfExemptSessionAuthentication',),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'DEFAULT_RENDERER_CLASSES': ('rest_framework.renderers.JSONRenderer',),
    'DEFAULT_PARSER_CLASSES': ('rest_framework.parsers.JSONParser',
                               'rest_framework.parsers.MultiPartParser',
                               'rest_framework.parsers.FormParser',),
}
