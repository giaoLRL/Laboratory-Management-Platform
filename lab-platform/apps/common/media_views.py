"""媒体文件鉴权视图。

生产环境 nginx 把 /media/ 反代到 Django（与开发行为一致）：
打卡照片、任务附件均要求登录后才能访问，未登录返回 403。

生产模式鉴权通过后返回 X-Accel-Redirect，由 nginx 直接从磁盘发文件，
避免大视频/大图流式转发占用 gunicorn 单 worker 线程拖慢全站 API。
"""
import mimetypes
import os

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
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
    ctype, _ = mimetypes.guess_type(full)
    if settings.DEBUG:
        # 本地开发：runserver 直接以 FileResponse 提供文件
        resp = FileResponse(open(full, 'rb'))
        if ctype:
            resp['Content-Type'] = ctype
        return resp
    # 生产：鉴权后交给 nginx X-Accel-Redirect 直发（对应 /internal-media/ 内部 location）。
    # 必须对路径做 percent-encode：header 含中文时 Django 会按 RFC 2047 编码成
    # "=?utf-8?b?..."，nginx 无法匹配内部 location 而 404。
    from urllib.parse import quote
    accel = quote('/internal-media/' + filepath, safe='/')
    resp = HttpResponse('')
    resp['X-Accel-Redirect'] = accel
    if ctype:
        resp['Content-Type'] = ctype
    return resp
