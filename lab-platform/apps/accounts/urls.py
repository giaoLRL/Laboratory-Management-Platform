from django.urls import path

from apps.accounts import api

urlpatterns = [
    path('auth/login', api.auth_login),
    path('auth/me', api.auth_me),
    path('auth/logout', api.auth_logout),
    path('workspace', api.workspace),
    path('members', api.members_create),
    path('members/me/update', api.me_update),
    path('members/me/status', api.me_status),
    path('members/me/password', api.me_password),
    path('members/<str:mid>/update', api.members_update),
    path('members/<str:mid>/reset-password', api.members_reset_password),
    path('members/<str:mid>/active', api.members_active),
    path('nav', api.nav_admin_get),
    path('nav/save', api.nav_admin_save),
    path('login-logs', api.login_logs),
    path('export/<str:kind>', api.export_csv),
    # API 令牌与只读 openapi
    path('tokens', api.tokens_list),
    path('tokens/create', api.tokens_create),
    path('tokens/<int:tid>/revoke', api.tokens_revoke),
    path('openapi/assets', api.openapi_assets),
    path('openapi/loans', api.openapi_loans),
    path('openapi/tasks', api.openapi_tasks),
    # 小组管理
    path('groups', api.groups_list),
    path('groups/create', api.groups_create),
    path('groups/<str:gid>/update', api.groups_update),
    path('groups/<str:gid>/delete', api.groups_delete),
    path('groups/<str:gid>/members', api.groups_members),
    # 权限管理（RBAC）
    path('permissions/meta', api.permissions_meta),
    path('permissions/roles', api.roles_create),
    path('permissions/roles/<str:code>/rename', api.roles_rename),
    path('permissions/roles/<str:code>', api.roles_delete),
    path('permissions/roles/<str:code>/grant', api.roles_grant),
    path('permissions/members/<str:mid>', api.member_override_get),
    path('permissions/members/<str:mid>/grant', api.member_override_set),
]
