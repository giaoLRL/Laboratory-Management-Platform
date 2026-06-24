import mimetypes

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# Allowed MIME types per file category
ALLOWED_IMAGE_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp',
}
ALLOWED_DOCUMENT_TYPES = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain',
    'text/csv',
    'application/zip',
    'application/x-zip-compressed',
}
ALLOWED_VIDEO_TYPES = {
    'video/mp4', 'video/webm', 'video/quicktime', 'video/x-msvideo',
    'video/x-matroska',
}
ALLOWED_ATTACHMENT_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_DOCUMENT_TYPES | ALLOWED_VIDEO_TYPES


def validate_file_size(value, limit_mb=10):
    """Validate file size does not exceed limit (default 10MB)."""
    limit_bytes = limit_mb * 1024 * 1024
    if value.size > limit_bytes:
        raise ValidationError(
            _('文件大小不能超过 %(limit)dMB，当前文件大小为 %(size).1fMB'),
            params={'limit': limit_mb, 'size': value.size / (1024 * 1024)},
        )


def validate_image_type(value):
    """Validate uploaded file is an allowed image type."""
    mime_type, _ = mimetypes.guess_type(value.name)
    if mime_type and mime_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError(
            _('不支持的文件类型：%(type)s。支持的图片格式：JPEG, PNG, GIF, WebP, BMP'),
            params={'type': mime_type or '未知'},
        )


def validate_attachment_type(value):
    """Validate uploaded file is an allowed attachment type."""
    mime_type, _ = mimetypes.guess_type(value.name)
    if mime_type and mime_type not in ALLOWED_ATTACHMENT_TYPES:
        raise ValidationError(
            _('不支持的文件类型：%(type)s。支持图片、文档、视频和压缩包。'),
            params={'type': mime_type or '未知'},
        )
