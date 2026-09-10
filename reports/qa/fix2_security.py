"""批次2 安全修复补丁：媒体鉴权 / Agent API 鉴权与 CSRF / 文件类型校验 / SSRF 防护。

每条替换断言"恰好命中一次"；模型字段改动会生成迁移（下一步单独执行）。
"""
import io
import os
import re
import secrets
import sys

BASE = r'C:\Users\PC\Documents\实验室\netbox-main\netbox'
PLUGIN = os.path.join(BASE, 'lab_manager')
APPLY = '--apply' in sys.argv
NEW_TOKEN = 'labmgr_' + secrets.token_urlsafe(32)
report, failures = [], []


def patch(path, pairs, expect=1, regex=False):
    full = os.path.join(BASE, path)
    src = io.open(full, encoding='utf-8').read()
    orig = src
    for old, new in pairs:
        n = len(re.findall(old, src)) if regex else src.count(old)
        if n != expect:
            failures.append(f'{path}: 期望 {expect} 次，实际 {n} 次 -> {old[:70]!r}')
            continue
        src = re.sub(old, new, src) if regex else src.replace(old, new)
        report.append(f'  ok {path}: {(old.strip().splitlines() or [""])[0][:70]}')
    if src != orig and APPLY:
        io.open(full, 'w', encoding='utf-8', newline='').write(src)
    return src != orig


# ── 1. MediaView：插件上传目录加鉴权（P0-5）────────────────────
patch('netbox/views/misc.py', [(
    "        if path.startswith('image-attachments/'):\n"
    "            if not ImageAttachment.objects.restrict(request.user, 'view').filter(image=path).exists():\n"
    "                raise Http404\n"
    "        elif path.startswith('devicetype-images/'):\n"
    "            pass  # DCIM removed — permission check skipped\n",
    "        if path.startswith('image-attachments/'):\n"
    "            if not ImageAttachment.objects.restrict(request.user, 'view').filter(image=path).exists():\n"
    "                raise Http404\n"
    "        elif path.startswith('devicetype-images/'):\n"
    "            pass  # DCIM removed — permission check skipped\n"
    "        elif path.startswith(('checkins/', 'task_attachments/', 'hardware/')):\n"
    "            # lab_manager 插件上传目录：必须登录，且按归属做对象级校验\n"
    "            self._check_plugin_upload_permission(request.user, path)\n",
)])

patch('netbox/views/misc.py', [(
    "        response = serve(request, path, document_root=settings.MEDIA_ROOT)\n"
    "        response['Content-Security-Policy'] = \"sandbox; default-src 'none'\"\n"
    "        response['X-Content-Type-Options'] = \"nosniff\"\n"
    "        return response\n",
    "        response = serve(request, path, document_root=settings.MEDIA_ROOT)\n"
    "        response['Content-Security-Policy'] = \"sandbox; default-src 'none'\"\n"
    "        response['X-Content-Type-Options'] = \"nosniff\"\n"
    "        # 附件类文件强制下载，避免 SVG/HTML 之类被浏览器当作页面执行（存储型 XSS）\n"
    "        if path.startswith(('task_attachments/', 'hardware/invoice/')):\n"
    "            response['Content-Disposition'] = 'attachment'\n"
    "        return response\n"
    "\n"
    "    @staticmethod\n"
    "    def _check_plugin_upload_permission(user, path):\n"
    "        \"\"\"lab_manager 上传目录的对象级鉴权；任何异常一律按 404 处理（fail closed）。\"\"\"\n"
    "        if not user.is_authenticated:\n"
    "            raise Http404\n"
    "        if user.is_superuser:\n"
    "            return\n"
    "        try:\n"
    "            from lab_manager.models import CheckInRecord, Hardware, TaskAttachment\n"
    "            if path.startswith('checkins/'):\n"
    "                if not CheckInRecord.objects.filter(photo=path, user=user).exists():\n"
    "                    raise Http404\n"
    "            elif path.startswith('task_attachments/'):\n"
    "                if not TaskAttachment.objects.filter(file=path).filter(\n"
    "                    Q(task__created_by=user) | Q(task__assigned_to=user)\n"
    "                ).exists():\n"
    "                    raise Http404\n"
    "            else:  # hardware/\n"
    "                if not Hardware.objects.filter(\n"
    "                    Q(image=path) | Q(invoice_image=path)\n"
    "                ).filter(\n"
    "                    Q(submitted_by=user) | Q(custodian=user) | Q(approval_status='approved')\n"
    "                ).exists():\n"
    "                    raise Http404\n"
    "        except Http404:\n"
    "            raise\n"
    "        except Exception:\n"
    "            raise Http404\n",
)])

# ── 2. Agent API：会话请求必须过 CSRF；令牌不能冒充超管（P0-4 / CSRF）──
patch('lab_manager/agent_api.py', [(
    "import json\n",
    "import hmac\nimport json\n"
    "from django.middleware.csrf import CsrfViewMiddleware\n\n"
    "from .logging_config import logger\n",
)])

patch('lab_manager/agent_api.py', [(
    "    def dispatch(self, request, *args, **kwargs):\n"
    "        self.acting_user = self._resolve_user(request)\n"
    "        if isinstance(self.acting_user, JsonResponse):\n"
    "            return self.acting_user\n"
    "        return super().dispatch(request, *args, **kwargs)\n",
    "    def dispatch(self, request, *args, **kwargs):\n"
    "        resolved = self._resolve_user(request)\n"
    "        if isinstance(resolved, JsonResponse):\n"
    "            return resolved\n"
    "        self.acting_user, self.authenticated_by_token = resolved\n"
    "        # 本视图整体 csrf_exempt（网关调用无浏览器会话）。\n"
    "        # 但如果是靠浏览器会话鉴权的请求，必须补做 CSRF 校验，\n"
    "        # 否则恶意页面可以用 text/plain 跨站 POST 代替登录用户执行写操作。\n"
    "        if not self.authenticated_by_token:\n"
    "            failure = CsrfViewMiddleware(lambda r: None).process_view(request, None, (), {})\n"
    "            if failure is not None:\n"
    "                return self.error_response('CSRF 校验失败', code='40301', status=403)\n"
    "        return super().dispatch(request, *args, **kwargs)\n",
)])

patch('lab_manager/agent_api.py', [(
    "    def _resolve_user(self, request):\n"
    "        if request.user.is_authenticated:\n"
    "            return request.user\n"
    "\n"
    "        expected_token = get_plugin_config('lab_manager', 'agent_api_token', None)\n"
    "        provided_token = request.headers.get('X-Agent-Token')\n"
    "        if not expected_token or provided_token != expected_token:\n"
    "            return self.error_response('网关鉴权失败', code='40101', status=401)\n"
    "\n"
    "        user_id = request.headers.get('X-User-ID')\n"
    "        if not user_id:\n"
    "            return self.error_response('缺少 X-User-ID', code='40002', status=400)\n"
    "\n"
    "        try:\n"
    "            return User.objects.get(pk=user_id, is_active=True)\n"
    "        except (User.DoesNotExist, ValueError):\n"
    "            return self.error_response('用户不存在', code='40401', status=404)\n",
    "    def _resolve_user(self, request):\n"
    "        \"\"\"返回 (user, authenticated_by_token) 或 JsonResponse（鉴权失败）。\"\"\"\n"
    "        if request.user.is_authenticated:\n"
    "            return request.user, False\n"
    "\n"
    "        expected_token = get_plugin_config('lab_manager', 'agent_api_token', None)\n"
    "        provided_token = request.headers.get('X-Agent-Token') or ''\n"
    "        # 常量时间比较，避免计时侧信道\n"
    "        if not expected_token or not hmac.compare_digest(str(provided_token), str(expected_token)):\n"
    "            return self.error_response('网关鉴权失败', code='40101', status=401)\n"
    "\n"
    "        allow_impersonation = get_plugin_config(\n"
    "            'lab_manager', 'agent_api_allow_user_impersonation', True\n"
    "        )\n"
    "        if not allow_impersonation:\n"
    "            return self.error_response('未启用网关代调用（X-User-ID）', code='40302', status=403)\n"
    "\n"
    "        user_id = request.headers.get('X-User-ID')\n"
    "        if not user_id:\n"
    "            return self.error_response('缺少 X-User-ID', code='40002', status=400)\n"
    "\n"
    "        try:\n"
    "            acting_user = User.objects.get(pk=user_id, is_active=True)\n"
    "        except (User.DoesNotExist, ValueError):\n"
    "            return self.error_response('用户不存在', code='40401', status=404)\n"
    "\n"
    "        # 默认不允许通过网关令牌取得超级管理员权限（避免令牌泄露即等于超管）\n"
    "        allow_superuser = get_plugin_config(\n"
    "            'lab_manager', 'agent_api_allow_superuser_impersonation', False\n"
    "        )\n"
    "        if acting_user.is_superuser and not allow_superuser:\n"
    "            return self.error_response(\n"
    "                '网关令牌不允许冒充超级管理员', code='40303', status=403\n"
    "            )\n"
    "        logger.warning(\n"
    "            'Agent API 网关代调用: token 持有者以用户 %s(id=%s) 身份请求 %s',\n"
    "            acting_user.username, acting_user.pk, request.path,\n"
    "        )\n"
    "        return acting_user, True\n",
)])

# logger 导入（已并入上面的 import json 替换）

# ── 3. 配置文件：轮换令牌 + 新增开关（P0-4）────────────────────
for cfg in ['netbox/configuration.py', 'netbox/configuration_docker.py']:
    src = io.open(os.path.join(BASE, cfg), encoding='utf-8').read()
    new_src, n = re.subn(r'([ \t]*)"agent_api_token": "[^"]*",\n',
                         ('\\1# 网关令牌：必须替换为随机值（仓库内不要保留示例值）\n'
                          '\\1"agent_api_token": "' + NEW_TOKEN + '",\n'
                          '\\1# 是否允许网关用 X-User-ID 代任意成员调用 Agent API\n'
                          '\\1"agent_api_allow_user_impersonation": True,\n'
                          '\\1# 是否允许网关冒充超级管理员（默认关闭）\n'
                          '\\1"agent_api_allow_superuser_impersonation": False,\n'),
                         src)
    if n == 1 and APPLY:
        io.open(os.path.join(BASE, cfg), 'w', encoding='utf-8', newline='').write(new_src)
    (report if n == 1 else failures).append(
        f'  {"ok" if n == 1 else "!!"} {cfg}: agent_api_token 轮换 + 开关 ({n} 处)')

# ── 4. 文件类型校验器挂载（P1-6）────────────────────────────────
patch('lab_manager/models/hardware.py', [
    ("from ..validators import validate_file_size\n",
     "from ..validators import validate_file_size, validate_image_type\n"),
])
patch('lab_manager/models/hardware.py', [
    ("validators=[validate_file_size],", "validators=[validate_file_size, validate_image_type],"),
], expect=2)

patch('lab_manager/models/checkin.py', [
    ("from ..validators import validate_file_size\n",
     "from ..validators import validate_file_size, validate_image_type\n"),
    ("validators=[validate_file_size],", "validators=[validate_file_size, validate_image_type],"),
])

patch('lab_manager/models/task.py', [
    ("from ..validators import validate_file_size\n",
     "from ..validators import validate_file_size, validate_attachment_type\n"),
    ("validators=[validate_file_size],", "validators=[validate_file_size, validate_attachment_type],"),
])

# open_record.photo：补上大小 + 类型校验
oro = os.path.join(BASE, 'lab_manager/models/open_record.py')
src = io.open(oro, encoding='utf-8').read()
src2 = src.replace("from ..validators import validate_file_size\n",
                   "from ..validators import validate_file_size, validate_image_type\n")
m = re.search(r"(    photo = models\.ImageField\(\n)(?P<body>(?:        .*\n)*?)(    \)\n)", src2)
if m and 'validators=' not in m.group('body'):
    src2 = (src2[:m.end('body')] + "        validators=[validate_file_size, validate_image_type],\n"
            + src2[m.end('body'):])
    report.append('  ok lab_manager/models/open_record.py: photo 补挂校验器')
elif m:
    report.append('  -- lab_manager/models/open_record.py: photo 已有 validators，跳过')
else:
    failures.append('lab_manager/models/open_record.py: 未匹配到 photo 字段')
if src2 != src and APPLY:
    io.open(oro, 'w', encoding='utf-8', newline='').write(src2)

# ── 5. web_search SSRF 防护（P2）───────────────────────────────
patch('lab_manager/services/web_search.py', [(
    '    def read_page(self, url: str) -> str:\n'
    '        """读取网页内容为纯文本"""\n'
    '        try:\n',
    '    @staticmethod\n'
    '    def is_safe_public_url(url: str) -> bool:\n'
    '        """只允许 http/https 且解析后为公网地址，避免 SSRF/内网探测。"""\n'
    '        import ipaddress\n'
    '        import socket\n'
    '        from urllib.parse import urlparse\n'
    '\n'
    '        try:\n'
    '            parsed = urlparse(url)\n'
    '        except ValueError:\n'
    '            return False\n'
    '        if parsed.scheme not in ("http", "https") or not parsed.hostname:\n'
    '            return False\n'
    '        try:\n'
    '            infos = socket.getaddrinfo(parsed.hostname, None)\n'
    '        except OSError:\n'
    '            return False\n'
    '        for info in infos:\n'
    '            try:\n'
    '                ip = ipaddress.ip_address(info[4][0])\n'
    '            except ValueError:\n'
    '                return False\n'
    '            if (ip.is_private or ip.is_loopback or ip.is_link_local\n'
    '                    or ip.is_reserved or ip.is_multicast or ip.is_unspecified):\n'
    '                return False\n'
    '        return True\n'
    '\n'
    '    def read_page(self, url: str) -> str:\n'
    '        """读取网页内容为纯文本（仅允许公网 http/https）"""\n'
    '        if not self.is_safe_public_url(url):\n'
    '            import logging\n'
    '            logging.getLogger(__name__).warning("已拒绝非公网 URL: %s", url)\n'
    '            return ""\n'
    '        try:\n',
)])

print('\n'.join(report))
print()
if failures:
    print('失败:')
    for f in failures:
        print('  !!', f)
print(('已应用' if APPLY else 'DRY-RUN') + f'，失败 {len(failures)} 条')
if APPLY:
    print('新 agent_api_token =', NEW_TOKEN)
sys.exit(1 if failures else 0)
