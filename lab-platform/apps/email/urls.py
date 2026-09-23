from django.urls import path

from apps.email import api

urlpatterns = [
    path('email/config', api.email_config_get),
    path('email/config/save', api.email_config_save),
    path('email/rules', api.email_rules_get),
    path('email/rules/save', api.email_rules_save),
    path('email/logs', api.email_logs),
]