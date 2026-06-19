from django.conf import settings
from django.conf.urls import include
from django.urls import path

from account.views import LoginView, LogoutView
from netbox.plugins.urls import plugin_patterns
from netbox.views import HomeView, MediaView, SearchView, StaticMediaFailureView, htmx

_patterns = [

    # Base views
    path('', HomeView.as_view(), name='home'),
    path('search/', SearchView.as_view(), name='search'),

    # Login/logout
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('oauth/', include('social_django.urls', namespace='social')),

    # Apps
    path('core/', include('core.urls')),
    path('extras/', include('extras.urls')),
    path('api/extras/', include('extras.api.urls')),
    path('api/users/', include('users.api.urls')),
    path('users/', include('users.urls')),

    # Current user views
    path('user/', include('account.urls')),

    # HTMX views
    path('htmx/object-selector/', htmx.ObjectSelectorView.as_view(), name='htmx_object_selector'),

    # Serving static media in Django to pipe it through LoginRequiredMiddleware
    path('media/<path:path>', MediaView.as_view(), name='media'),
    path('media-failure/', StaticMediaFailureView.as_view(), name='media_failure'),

    # Plugins
    path('plugins/', include((plugin_patterns, 'plugins'))),
]

# django-debug-toolbar
if settings.DEBUG and getattr(settings, 'ENABLE_DEBUG_TOOLBAR', True):
    import debug_toolbar
    _patterns.append(path('__debug__/', include(debug_toolbar.urls)))

# Prometheus metrics
if settings.METRICS_ENABLED:
    _patterns.append(path('', include('django_prometheus.urls')))

# Prepend BASE_PATH
urlpatterns = [
    path(settings.BASE_PATH, include(_patterns))
]

handler404 = 'netbox.views.errors.handler_404'
handler500 = 'netbox.views.errors.handler_500'
