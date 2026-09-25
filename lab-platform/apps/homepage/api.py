"""营销官网首页内容管理：后台读写 + 公开消费 + 公开媒体放行。

- 管理接口：GET /api/homepage（回填）、POST /api/homepage/texts、/images、/images/reset
- 公开接口：GET /api/homepage/public（首页 JS 消费，无鉴权，max-age=300）
- 公开媒体：GET /media/public/homepage/... 免登录直出上传图（生产走 X-Accel-Redirect）
"""
import mimetypes
import os

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.views.decorators.cache import cache_control
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import OperationLog
from apps.common.rbac import require
from apps.common.response import fail, ok
from apps.homepage.defaults import IMAGE_DEFAULTS, TEXT_DEFAULTS
from apps.homepage.models import HomePageImage, HomePageText

MAX_IMG = 10 * 1024 * 1024
MAX_VID = 40 * 1024 * 1024
VIDEO_EXTS = {'.mp4', '.webm'}
SCALE_MIN, SCALE_MAX = 80, 150


def _log(request, text):
    OperationLog.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        text=str(text)[:256],
    )


def _drop(field):
    """安全删除文件：文件被占用（如并发读取/Windows 锁）时仅剥离引用，不影响业务。"""
    if field:
        try:
            field.delete(save=False)
        except OSError:
            pass


def _media_url(row):
    """当前媒体公开访问 URL：按 kind 优先该类型文件，否则回退默认引用 seed。"""
    if row.kind == 'video':
        if row.video:
            return '/media/public/' + row.video.name
        if row.image:
            return '/media/public/' + row.image.name  # 容错：类型为视频但文件缺失
        return row.seed
    if row.image:
        return '/media/public/' + row.image.name
    return row.seed


def _is_video_file(photo):
    """视频校验：大小 + 后缀白名单 + MIME + 魔数嗅探（不依赖客户端自报的 content_type）。"""
    if photo.size > MAX_VID:
        return None, '视频不能超过 40MB'
    name = (photo.name or '').lower()
    if not any(name.endswith(ext) for ext in VIDEO_EXTS):
        return None, '视频仅支持 mp4 / webm'
    head = photo.file.read(12)
    photo.file.seek(0)
    if name.endswith('.mp4'):
        magic_ok = b'ftyp' in head[:12]
    else:  # webm / matroska
        magic_ok = head[:4] == b'\x1a\x45\xdf\xa3'
    if not magic_ok:
        return None, '视频文件内容不完整（仅支持 mp4 / webm）'
    return True, ''


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def homepage_get(request):
    if (err := require(request.user, 'page:homepage', '没有主页管理权限')):
        return err
    texts = [
        {'key': t.key, 'label': t.label, 'value': t.value}
        for t in HomePageText.objects.all()
    ]
    images = [
        {'key': i.key, 'label': i.label, 'alt': i.alt, 'seed': i.seed,
         'type': i.kind, 'scale': i.scale, 'url': _media_url(i),
         'uploaded': bool(i.image or i.video)}
        for i in HomePageImage.objects.all()
    ]
    return ok({'texts': texts, 'images': images})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def homepage_scale_save(request):
    if (err := require(request.user, 'action:homepage.edit', '没有编辑主页内容的权限')):
        return err
    d = request.data or {}
    key = str(d.get('key', '')).strip()
    if key not in IMAGE_DEFAULTS:
        return fail('媒体标识不合法')
    try:
        scale = int(d.get('scale'))
    except (TypeError, ValueError):
        return fail('缩放值必须为整数')
    if not (SCALE_MIN <= scale <= SCALE_MAX):
        return fail(f'缩放范围需在 {SCALE_MIN}%–{SCALE_MAX}% 之间')
    HomePageImage.objects.update_or_create(
        pk=key,
        defaults={'label': IMAGE_DEFAULTS[key][0], 'seed': IMAGE_DEFAULTS[key][1],
                  'alt': IMAGE_DEFAULTS[key][2], 'scale': scale},
    )
    _log(request, f'设置主页{key}缩放 · {scale}%')
    return ok({'scale': scale})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def homepage_texts_save(request):
    if (err := require(request.user, 'action:homepage.edit', '没有编辑主页文案的权限')):
        return err
    values = (request.data or {}).get('values') or {}
    if not isinstance(values, dict):
        return fail('参数格式不正确')
    allowed = set(TEXT_DEFAULTS)
    bad = set(values) - allowed
    if bad:
        return fail(f'含无权限字段：{", ".join(sorted(bad))[:120]}')
    for key, val in values.items():
        HomePageText.objects.filter(pk=key).update(value=str(val)[:4000])
    _log(request, f'更新主页文案 · {", ".join(values)[:200]}')
    return ok({'count': len(values)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def homepage_image_upload(request):
    if (err := require(request.user, 'action:homepage.edit', '没有编辑主页图片的权限')):
        return err
    key = str((request.data or {}).get('key', '')).strip()
    if key not in IMAGE_DEFAULTS:
        return fail('媒体标识不合法')
    media = request.FILES.get('media') or request.FILES.get('image')
    if not media:
        return fail('请选择图片或视频文件')
    row, _ = HomePageImage.objects.get_or_create(
        pk=key,
        defaults={'label': IMAGE_DEFAULTS[key][0], 'seed': IMAGE_DEFAULTS[key][1],
                  'alt': IMAGE_DEFAULTS[key][2]},
    )
    ctype = (media.content_type or '').lower()
    if ctype.startswith('video/'):
        ok_v, msg = _is_video_file(media)
        if not ok_v:
            return fail(msg)
        _drop(row.image)
        row.image = None
        _drop(row.video)
        row.video = media
        row.kind = 'video'
    elif ctype.startswith('image/'):
        if media.size > MAX_IMG:
            return fail('图片不能超过 10MB')
        from PIL import Image
        try:
            Image.open(media).verify()
        except Exception:
            return fail('仅支持有效图片文件（jpg/png/webp 等）')
        _drop(row.video)
        row.video = None
        _drop(row.image)
        row.image = media
        row.kind = 'image'
    else:
        return fail('仅支持图片（jpg/png/webp）或视频（mp4/webm）')
    alt = str((request.data or {}).get('alt', '')).strip()
    if alt:
        row.alt = alt[:256]
    row.save()
    _log(request, f'更新主页{"视频" if row.kind == "video" else "图片"} · {key}')
    return ok({'url': _media_url(row), 'kind': row.kind})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def homepage_image_reset(request):
    if (err := require(request.user, 'action:homepage.edit', '没有编辑主页图片的权限')):
        return err
    key = str((request.data or {}).get('key', '')).strip()
    if key not in IMAGE_DEFAULTS:
        return fail('媒体标识不合法')
    row = HomePageImage.objects.filter(pk=key).first()
    if row:
        if row.kind == 'video':
            _drop(row.video)
            row.video = None
        else:
            _drop(row.image)
            row.image = None
        row.kind = 'image'
        row.scale = 100
        row.alt = IMAGE_DEFAULTS[key][2]
        row.save()
    _log(request, f'重置主页媒体 · {key}')
    return ok({'url': IMAGE_DEFAULTS[key][1]})


@api_view(['GET'])
@permission_classes([])
@cache_control(no_store=True)
def homepage_public(request):
    """公开内容：首页 JS 按 data-hp 替换。缺行回退默认值。

    no-store：无条件不缓存（含边缘/CDN）。此前 max-age/no-cache 均无法
    阻止部分中间层按 path 缓存旧 JSON，导致官网偶发显示旧图片旧文案。
    """
    texts = {t.key: t.value for t in HomePageText.objects.all()}
    for key, (_, val) in TEXT_DEFAULTS.items():
        texts.setdefault(key, val)
    images = {}
    for i in HomePageImage.objects.all():
        images[i.key] = {'type': i.kind, 'scale': i.scale, 'url': _media_url(i), 'alt': i.alt}
    for key, (_, seed, alt) in IMAGE_DEFAULTS.items():
        images.setdefault(key, {'type': 'image', 'scale': 100, 'url': seed, 'alt': alt})
    return ok({'text': texts, 'images': images})


@api_view(['GET'])
@permission_classes([])
def public_media(request, filepath):
    """公开媒体：仅放行 homepage/ 目录（避免 /media/public/ 意外公开私有上传）。"""
    if not filepath.startswith('homepage/'):
        raise Http404
    root = os.path.realpath(str(settings.MEDIA_ROOT))
    full = os.path.realpath(os.path.join(root, filepath))
    if os.path.commonpath([root, full]) != root or not os.path.isfile(full):
        raise Http404
    ctype, _ = mimetypes.guess_type(full)
    if settings.DEBUG:
        resp = FileResponse(open(full, 'rb'))
        if ctype:
            resp['Content-Type'] = ctype
        resp['Cache-Control'] = 'no-store'
        return resp
    # 生产：交给 nginx X-Accel-Redirect 直发（对应 /internal-media/ 内部 location）。
    from urllib.parse import quote
    resp = HttpResponse('')
    resp['X-Accel-Redirect'] = quote('/internal-media/' + filepath, safe='/')
    if ctype:
        resp['Content-Type'] = ctype
    # 上传媒体必须无条件即时刷新：no-store 禁止浏览器/边缘任何缓存
    resp['Cache-Control'] = 'no-store'
    return resp