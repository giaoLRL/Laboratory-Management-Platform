"""具身智能实验室 · 管理平台后端配置

环境变量（生产部署时由 docker-compose / systemd 注入）：
  LAB_SECRET_KEY      生产密钥（本地开发有默认值，生产必须显式设置）
  LAB_DEBUG           '1' 开启调试（本地开发默认开，生产的默认是关）
  LAB_ALLOWED_HOSTS   逗号分隔
  LAB_DB_ENGINE       'sqlite'（默认，本地开发） / 'postgres'（生产）
  LAB_DB_NAME/HOST/PORT/USER/PASSWORD
"""

from pathlib import Path
import os

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# 生产环境（LAB_ENV=production）必须显式注入 LAB_SECRET_KEY，缺失即拒绝启动；
# 本地开发（LAB_ENV 未设置）允许默认值，避免本地 runserver 无法启动。
LAB_ENV = os.environ.get('LAB_ENV')
SECRET_KEY = os.environ.get('LAB_SECRET_KEY')
if not SECRET_KEY:
    if LAB_ENV == 'production':
        raise ImproperlyConfigured('生产环境必须设置 LAB_SECRET_KEY 环境变量')
    SECRET_KEY = 'dev-only-secret-key-change-in-production'

# 本地开发默认开调试：urls.py 里 SPA 的托管路由写在 `if settings.DEBUG` 之内，
# 关掉调试后 Django 只提供 /api/ 与 /media/，访问 / 会返回 404（SPA 交由 nginx 托管）。
# 生产的 deploy_server.sh 已同时注入 LAB_ENV=production 与 LAB_DEBUG=0，这里再兜一道：
# 生产只要出现调试开启就直接拒绝启动，避免默认值改动被误带到线上。
DEBUG = os.environ.get('LAB_DEBUG', '0' if LAB_ENV == 'production' else '1') == '1'
if LAB_ENV == 'production' and DEBUG:
    raise ImproperlyConfigured('生产环境不允许开启调试（请设置 LAB_DEBUG=0）')
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
    'apps.points',
    'apps.levels',
    'apps.email',
    'apps.homepage',
    'apps.seats',
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
# 必须以 / 开头：打卡照片/任务附件的 .url 会拼进 JSON 返回给 SPA，
# 相对路径在 /login/ 等非根文档路径下会解析错误（404 → 图片全挂）
MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.environ.get('LAB_MEDIA_ROOT', BASE_DIR / 'media'))
# 开发模式托管的 SPA 目录
LAB_WEB_DIR = os.environ.get('LAB_WEB_DIR', str(BASE_DIR.parent / 'lab-platform-web'))
# 上传体积上限：打卡照片 / 任务附件共用。视频材料较大，按环境可配（默认 60MB，nginx client_max_body_size 需同步放开）
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get('LAB_MAX_UPLOAD_BYTES', 60 * 1024 * 1024))

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

# HTTPS 纵深防御：nginx 已传 X-Forwarded-Proto（deploy_server.sh 的 proxy_set_header）。
# LAB_SECURE=1 时（生产部署脚本注入）启用 Secure Cookie 与 HSTS。
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
_secure_cookies = os.environ.get('LAB_SECURE', '0') == '1'
SESSION_COOKIE_SECURE = _secure_cookies
CSRF_COOKIE_SECURE = _secure_cookies
SECURE_HSTS_SECONDS = int(os.environ.get('LAB_HSTS', '31536000' if _secure_cookies else '0'))

# 错误/请求日志：统一走 console（gunicorn 捕获），生产容器日志可查
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': os.environ.get('LAB_LOG_LEVEL', 'INFO')},
    'loggers': {
        'django.request': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False},
        'django.security': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
    },
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'apps.common.auth.TokenAuthentication',
        'apps.common.auth.CsrfExemptSessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'DEFAULT_RENDERER_CLASSES': ('rest_framework.renderers.JSONRenderer',),
    'DEFAULT_PARSER_CLASSES': ('rest_framework.parsers.JSONParser',
                               'rest_framework.parsers.MultiPartParser',
                               'rest_framework.parsers.FormParser',),
}
