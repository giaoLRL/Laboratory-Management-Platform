from django.conf import settings
from django.urls import include, path, re_path

from apps.common.media_views import protected_media
from apps.homepage.api import public_media

api_patterns = [
    path('', include('apps.accounts.urls')),
    path('', include('apps.inventory.urls')),
    path('', include('apps.leaves.urls')),
    path('', include('apps.competitions.urls')),
    path('', include('apps.tasksapp.urls')),
    path('', include('apps.checkins.urls')),
    path('', include('apps.agent.urls')),
    path('', include('apps.notify.urls')),
    path('', include('apps.points.urls')),
    path('', include('apps.levels.urls')),
    path('', include('apps.email.urls')),
    path('', include('apps.homepage.urls')),
    path('', include('apps.seats.urls')),
]

urlpatterns = [
    # 所有 API 统一挂在 /api/ 前缀下（生产 nginx 不剥前缀，开发/生产行为一致）
    path('api/', include(api_patterns)),
    # 公开媒体（营销首页上传图）：仅放行 homepage/ 目录，先于鉴权媒体注册，
    # 否则会被 protected_media 拦截成 401/403
    path('media/public/<path:filepath>', public_media),
    # 媒体文件（打卡照片/任务附件）：开发/生产统一走鉴权视图，
    # 必须放在 DEBUG 模式的 SPA catch-all 之前
    path('media/<path:filepath>', protected_media),
]

if settings.DEBUG:
    # 开发模式：由 Django 直接托管 SPA（lab-platform-web），保持同源 Cookie
    from django.views.static import serve as static_serve

    def _no_store(response):
        """开发期禁止缓存 index.html。

        浏览器若按启发式缓存把旧的 index.html 留着，页面里那些
        `/src/xxx.js?v=N` 的新版本号压根不会被请求 —— 表现就是「改了代码但页面毫无变化」。
        这个坑已经踩过两次，所以入口 HTML 一律强制不缓存（生产由 nginx 的 no-cache 负责）。
        """
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        response['Pragma'] = 'no-cache'
        return response

    def spa_index(request):
        return _no_store(static_serve(request, 'index.html', document_root=settings.LAB_WEB_DIR))

    def spa_asset(request, path):
        # 静态资源带 ?v= 版本号，可以正常缓存；回退到 index.html 时同样不许缓存
        response = static_serve(request, path, document_root=settings.LAB_WEB_DIR)
        if str(path).endswith('index.html'):
            _no_store(response)
        return response

    urlpatterns += [
        path('', spa_index),
        re_path(r'^(?!api/)(?P<path>.*)$', spa_asset),
    ]
