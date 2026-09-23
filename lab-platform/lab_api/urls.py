from django.conf import settings
from django.urls import include, path, re_path

from apps.common.media_views import protected_media

api_patterns = [
    path('', include('apps.accounts.urls')),
    path('', include('apps.inventory.urls')),
    path('', include('apps.leaves.urls')),
    path('', include('apps.competitions.urls')),
    path('', include('apps.tasksapp.urls')),
    path('', include('apps.checkins.urls')),
    path('', include('apps.agent.urls')),
]

urlpatterns = [
    # 所有 API 统一挂在 /api/ 前缀下（生产 nginx 不剥前缀，开发/生产行为一致）
    path('api/', include(api_patterns)),
    # 媒体文件（打卡照片/任务附件）：开发/生产统一走鉴权视图，
    # 必须放在 DEBUG 模式的 SPA catch-all 之前
    path('media/<path:filepath>', protected_media),
]

if settings.DEBUG:
    # 开发模式：由 Django 直接托管 SPA（lab-platform-web），保持同源 Cookie
    from django.views.static import serve as static_serve

    def spa_index(request):
        return static_serve(request, 'index.html', document_root=settings.LAB_WEB_DIR)

    urlpatterns += [
        path('', spa_index),
        re_path(r'^(?!api/)(?P<path>.*)$', static_serve, {'document_root': settings.LAB_WEB_DIR}),
    ]
