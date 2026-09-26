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
from apps.homepage.defaults import (
    FIT_CHOICES,
    FOCUS_MAX,
    FOCUS_MIN,
    IMAGE_DEFAULTS,
    TEXT_DEFAULTS,
    WORK_MAX,
    WORK_SPEC,
    ZOOM_MAX,
    ZOOM_MIN,
)
from apps.homepage.models import HomePageImage, HomePageText, HomePageWork

MAX_IMG = 10 * 1024 * 1024
MAX_VID = 40 * 1024 * 1024
MAX_SRC = 20 * 1024 * 1024   # 原图另存上限（超出就只留裁剪结果，不阻断上传）
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


def _work_url(row):
    """作品图公开访问 URL：上传图优先，否则回退 seed（可能为空 = 该条暂不上官网）。"""
    if row.image:
        return '/media/public/' + row.image.name
    return row.seed


def _keep_source(row, request):
    """把原图另存到 source 字段（后台裁剪层「重新裁剪」要用）。

    只有带 source 字段的模型（媒体位）才保留原图；作品集图不存原图、超限或非图片也静默跳过。
    """
    if not hasattr(row, 'source'):
        return
    src = request.FILES.get('source')
    if not src or src.size > MAX_SRC or not (src.content_type or '').lower().startswith('image/'):
        return
    _drop(row.source)
    row.source = src


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
    # 以 IMAGE_DEFAULTS 为准逐位输出（缺行说明该位还没被编辑过，按默认值回填，
    # 这样新增的媒体位无需数据迁移就会出现在后台编辑器里）
    rows = {i.key: i for i in HomePageImage.objects.all()}
    images = []
    for key, (label, seed, alt, spec) in IMAGE_DEFAULTS.items():
        row = rows.get(key)
        if row is None:
            images.append({
                'key': key, 'label': label, 'alt': alt, 'seed': seed,
                'type': 'image', 'url': seed, 'uploaded': False,
                'fit': spec['fit'], 'focus_x': spec['focus'][0], 'focus_y': spec['focus'][1],
                'zoom': 100, 'spec': spec, 'source_url': '',
            })
            continue
        images.append({
            'key': key, 'label': row.label or label, 'alt': row.alt or alt, 'seed': row.seed or seed,
            'type': row.kind, 'url': _media_url(row), 'uploaded': bool(row.image or row.video),
            'fit': row.fit, 'focus_x': row.focus_x, 'focus_y': row.focus_y, 'zoom': row.zoom,
            'spec': spec,
            'source_url': ('/media/public/' + row.source.name) if row.source else '',
        })
    works = [
        {'id': w.pk, 'title': w.title, 'tag': w.tag, 'alt': w.alt, 'seed': w.seed,
         'url': _work_url(w), 'uploaded': bool(w.image), 'visible': w.visible}
        for w in HomePageWork.objects.all()
    ]
    return ok({'texts': texts, 'images': images, 'works': works, 'workSpec': WORK_SPEC})


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
def homepage_frame_save(request):
    """保存媒体位构图参数：裁切方式 + 焦点 + 微缩放（后台预览与线上同一套变量）。"""
    if (err := require(request.user, 'action:homepage.edit', '没有编辑主页内容的权限')):
        return err
    d = request.data or {}
    key = str(d.get('key', '')).strip()
    if key not in IMAGE_DEFAULTS:
        return fail('媒体标识不合法')
    spec = IMAGE_DEFAULTS[key][3]
    fit = str(d.get('fit') or spec['fit']).strip().lower()
    if fit not in FIT_CHOICES:
        return fail('裁切方式仅支持 cover / contain')
    if spec.get('fitLocked'):
        fit = spec['fit']  # 裁切方式写死的位（如二维码）忽略入参，保证线上不会被越权裁掉
    try:
        fx = int(d.get('focus_x', spec['focus'][0]))
        fy = int(d.get('focus_y', spec['focus'][1]))
        zoom = int(d.get('zoom', 100))
    except (TypeError, ValueError):
        return fail('焦点与缩放必须为整数')
    if not (FOCUS_MIN <= fx <= FOCUS_MAX and FOCUS_MIN <= fy <= FOCUS_MAX):
        return fail(f'焦点范围需在 {FOCUS_MIN}%–{FOCUS_MAX}% 之间')
    if not (ZOOM_MIN <= zoom <= ZOOM_MAX):
        return fail(f'缩放范围需在 {ZOOM_MIN}%–{ZOOM_MAX}% 之间')
    HomePageImage.objects.update_or_create(
        pk=key,
        defaults={'label': IMAGE_DEFAULTS[key][0], 'seed': IMAGE_DEFAULTS[key][1],
                  'alt': IMAGE_DEFAULTS[key][2],
                  'fit': fit, 'focus_x': fx, 'focus_y': fy, 'zoom': zoom},
    )
    _log(request, f'设置主页{key}构图 · {fit} 焦点{fx}/{fy} 缩放{zoom}%')
    return ok({'fit': fit, 'focus_x': fx, 'focus_y': fy, 'zoom': zoom})


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
        _keep_source(row, request)  # 后台裁剪层会把原图一起带上，便于日后重新裁剪
    else:
        return fail('仅支持图片（jpg/png/webp）或视频（mp4/webm）')
    alt = str((request.data or {}).get('alt', '')).strip()
    if alt:
        row.alt = alt[:256]
    row.save()
    _log(request, f'更新主页{"视频" if row.kind == "video" else "图片"} · {key}')
    return ok({'url': _media_url(row), 'kind': row.kind,
               'source_url': ('/media/public/' + row.source.name) if row.source else ''})


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
        _drop(row.source)
        row.source = None
        spec = IMAGE_DEFAULTS[key][3]
        row.kind = 'image'
        row.scale = 100
        row.zoom = 100
        row.fit = spec['fit']
        row.focus_x, row.focus_y = spec['focus']
        row.alt = IMAGE_DEFAULTS[key][2]
        row.save()
    _log(request, f'重置主页媒体 · {key}')
    return ok({'url': IMAGE_DEFAULTS[key][1]})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def homepage_works_save(request):
    """整表保存作品集：按数组顺序重排，带 id 的更新、无 id 的新增、缺席的删除。

    一次请求覆盖增删/排序/改名/隐藏，避免多条小接口各自维护顺序（顺序天然由下标决定）。
    """
    if (err := require(request.user, 'action:homepage.edit', '没有编辑主页内容的权限')):
        return err
    items = (request.data or {}).get('works')
    if not isinstance(items, list):
        return fail('参数格式不正确')
    if len(items) > WORK_MAX:
        return fail(f'作品集最多 {WORK_MAX} 条')
    seen = []
    for idx, it in enumerate(items):
        if not isinstance(it, dict):
            return fail('参数格式不正确')
        raw = it.get('id')
        row = None
        if raw not in (None, '', 0):
            row = HomePageWork.objects.filter(pk=raw).first()
            if row is None:
                return fail('作品条目不存在，请刷新后重试')
        else:
            row = HomePageWork()
        row.title = str(it.get('title') or '')[:128]
        row.tag = str(it.get('tag') or '')[:64]
        row.alt = str(it.get('alt') or it.get('title') or '')[:256]
        row.visible = bool(it.get('visible', True))
        row.sort = idx  # 顺序即数组下标，前端拖动排序后整表提交
        row.save()
        seen.append(row.pk)
    removed = HomePageWork.objects.exclude(pk__in=seen)
    n_removed = removed.count()
    for row in removed:
        _drop(row.image)
        row.delete()
    _log(request, f'保存主页作品集 · {len(items)} 条（删除 {n_removed}）')
    works = [
        {'id': w.pk, 'title': w.title, 'tag': w.tag, 'alt': w.alt, 'seed': w.seed,
         'url': _work_url(w), 'uploaded': bool(w.image), 'visible': w.visible}
        for w in HomePageWork.objects.all()
    ]
    return ok({'works': works})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def homepage_work_image(request):
    """上传/替换某条作品的图片（作品图按 4:3 网格展示，前台一律 cover，故不设裁切参数）。"""
    if (err := require(request.user, 'action:homepage.edit', '没有编辑主页作品的权限')):
        return err
    d = request.data or {}
    try:
        wid = int(d.get('id'))
    except (TypeError, ValueError):
        return fail('作品标识不合法')
    row = HomePageWork.objects.filter(pk=wid).first()
    if row is None:
        return fail('作品条目不存在，请刷新后重试')
    media = request.FILES.get('media') or request.FILES.get('image')
    if not media:
        return fail('请选择图片文件')
    if media.size > MAX_IMG:
        return fail('图片不能超过 10MB')
    from PIL import Image
    try:
        Image.open(media).verify()
    except Exception:
        return fail('仅支持有效图片文件（jpg/png/webp 等）')
    _drop(row.image)
    row.image = media
    _keep_source(row, request)
    if not row.alt:
        row.alt = row.title or '实验室作品'
    row.save()
    _log(request, f'更新主页作品图 · #{wid}')
    return ok({'url': _work_url(row), 'id': row.pk})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def homepage_work_reset(request):
    """把某条作品的图片恢复为默认引用图（seed）。"""
    if (err := require(request.user, 'action:homepage.edit', '没有编辑主页作品的权限')):
        return err
    try:
        wid = int((request.data or {}).get('id'))
    except (TypeError, ValueError):
        return fail('作品标识不合法')
    row = HomePageWork.objects.filter(pk=wid).first()
    if row is None:
        return fail('作品条目不存在，请刷新后重试')
    _drop(row.image)
    row.image = None
    _drop(row.source)
    row.source = None
    row.save()
    _log(request, f'重置主页作品图 · #{wid}')
    return ok({'url': _work_url(row), 'id': row.pk})


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
    # 只发仍存在的位：作品集迁走后遗留的 work-01~04/demo-drone-nav/work-06~08 行要忽略
    for i in HomePageImage.objects.filter(key__in=list(IMAGE_DEFAULTS)):
        images[i.key] = {'type': i.kind, 'url': _media_url(i), 'alt': i.alt,
                         'fit': i.fit, 'focus_x': i.focus_x, 'focus_y': i.focus_y, 'zoom': i.zoom}
    for key, (_, seed, alt, spec) in IMAGE_DEFAULTS.items():
        images.setdefault(key, {'type': 'image', 'url': seed, 'alt': alt,
                                'fit': spec['fit'], 'focus_x': spec['focus'][0],
                                'focus_y': spec['focus'][1], 'zoom': 100})
    # 作品集：只发上官网的（visible），顺序即 sort；url 为空前台跳过该条
    works = [
        {'url': _work_url(w), 'title': w.title, 'tag': w.tag, 'alt': w.alt}
        for w in HomePageWork.objects.filter(visible=True)
    ]
    return ok({'text': texts, 'images': images, 'works': works})


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