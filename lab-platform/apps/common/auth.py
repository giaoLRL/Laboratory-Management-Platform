from hashlib import sha256

from django.utils import timezone
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


class TokenAuthentication:
    """外部只读接口令牌认证：`Authorization: Bearer <token>`。

    只校验哈希一致 + active + 未过期；认证成功返回 (user, None)。
    """

    keyword = 'Bearer'

    def authenticate(self, request):
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth.startswith(self.keyword + ' '):
            return None
        token = auth[len(self.keyword) + 1:].strip()
        if not token:
            return None
        from apps.accounts.models import ApiToken
        digest = sha256(token.encode()).hexdigest()
        row = ApiToken.objects.select_related('user').filter(token_hash=digest, active=True).first()
        if not row:
            return None
        if row.expires_at and row.expires_at < timezone.now():
            return None
        ApiToken.objects.filter(pk=row.pk).update(last_used_at=timezone.now())
        return (row.user, row)

    def authenticate_header(self, request):
        return self.keyword
