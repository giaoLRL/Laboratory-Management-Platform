from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """同源 SPA 部署：会话 Cookie 设 SameSite=Lax 已阻断跨站携带，
    API 层豁免 DRF 默认的 CSRF 强制校验（详见 settings 注释）。"""

    def enforce_csrf(self, request):
        return None
