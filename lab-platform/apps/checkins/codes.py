"""实验室扫码签到的动态签到码。

无状态方案：码 = HMAC(SECRET_KEY, 时间窗)，每 STEP_SECONDS 换一次；
校验时在容差窗口内逐窗比对，容纳手机时钟偏差和「扫码 → 拍照 → 提交」的耗时。

不落库：轮换由时间驱动，不需要定时任务与清理，也不存在并发写；
短 TTL 下"吊销"没有意义 —— 真正的在场证据是现场照片 + 每人每天一条。
"""

import hmac
import os
from hashlib import sha256

from django.conf import settings
from django.utils import timezone

STEP_SECONDS = int(os.environ.get('LAB_CHECKIN_CODE_STEP', '90'))
WINDOW_TOLERANCE = int(os.environ.get('LAB_CHECKIN_CODE_TOLERANCE', '2'))
CODE_LENGTH = 8
# 去掉 0/O/1/I/L：屏幕上要念得出、也允许手输
ALPHABET = '23456789ABCDEFGHJKMNPQRSTUVWXYZ'


def _window(ts):
    return int(ts) // STEP_SECONDS


def _code_for(window):
    digest = hmac.new(settings.SECRET_KEY.encode(), f'checkin:{window}'.encode(), sha256).digest()
    return ''.join(ALPHABET[b % len(ALPHABET)] for b in digest[:CODE_LENGTH])


def current(now=None):
    """当前窗口的签到码：secondsLeft 是距下次换码的秒数，validSeconds 是此刻仍可打卡的时长。"""
    ts = (now or timezone.now()).timestamp()
    window = _window(ts)
    expires = (window + WINDOW_TOLERANCE + 1) * STEP_SECONDS
    return {
        'code': _code_for(window),
        'step': STEP_SECONDS,
        'secondsLeft': int(STEP_SECONDS - ts % STEP_SECONDS),
        'validSeconds': int(expires - ts),
    }


def verify(raw, now=None):
    """校验成员提交的签到码：在容差窗口内逐窗比对，任一命中即通过。"""
    code = ''.join(ch for ch in str(raw or '').upper() if ch.isalnum())
    if len(code) != CODE_LENGTH:
        return False
    window = _window((now or timezone.now()).timestamp())
    return any(hmac.compare_digest(code, _code_for(window - i)) for i in range(WINDOW_TOLERANCE + 1))