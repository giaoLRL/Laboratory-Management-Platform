"""媒体文件鉴权视图。

生产环境 nginx 把 /media/ 反代到 Django（与开发行为一致）：
打卡照片、任务附件均要求登录后才能访问，未登录返回 403。
"""
import mimetypes
import os

from django.conf import settings
from django.http import FileResponse, Http404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def protected_media(request, filepath):
    root = os.path.realpath(str(settings.MEDIA_ROOT))
    full = os.path.realpath(os.path.join(root, filepath))
    # 防目录穿越：解析后的绝对路径必须仍在 MEDIA_ROOT 内
    if os.path.commonpath([root, full]) != root or not os.path.isfile(full):
        raise Http404
    resp = FileResponse(open(full, 'rb'))
    ctype, _ = mimetypes.guess_type(full)
    if ctype:
        resp['Content-Type'] = ctype
    return resp
