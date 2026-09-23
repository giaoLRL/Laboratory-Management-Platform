from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """同源 SPA 部署：会话 Cookie 设 SameSite=Lax 已阻断跨站携带，
    API 层豁免 DRF 默认的 CSRF 强制校验（详见 settings 注释）。"""

    def enforce_csrf(self, request):
        return None

    def authenticate_header(self, request):
        """未认证时让 DRF 返回 401（NotAuthenticated）而不是默认的 403。

        DRF 规则：认证器未定义 authenticate_header 时，未认证请求抛
        PermissionDenied(403)；定义后抛 NotAuthenticated(401)。
        SPA 的 API.load() 以 401 判定"未登录 → 渲染登录页"，
        返回 403 会导致启动抛错、页面空白/报错屏。
        """
        return 'Session'
