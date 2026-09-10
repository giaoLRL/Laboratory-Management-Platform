"""安全 / 权限实测（走真实 HTTP）。

验证项：
 1. Agent API 令牌 + X-User-ID 冒充任意用户
 2. 媒体文件（打卡照片/发票/任务附件）是否可被匿名下载
 3. 普通成员能否查看他人隐私数据（成员详情 / 硬件详情 / 借出记录）
 4. 普通成员能否编辑他人借出记录
 5. 超管专属页面是否真的拦住普通成员
 6. CSRF 保护是否生效
 7. 打卡重复提交（幂等）

会临时创建一个 qa_member 账号与一条测试借出记录，结束时全部清理。
"""
import io
import os
import re
import sys

import django

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

import requests  # noqa: E402
from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402

from lab_manager.models import (  # noqa: E402
    CheckInRecord, Hardware, HardwareBorrowRecord, MemberOpenRecord, TaskAttachment,
)

BASE = 'http://127.0.0.1:8001'
U = get_user_model()
ADMIN_PK = U.objects.get(username='admin').pk
HUHAN = U.objects.get(username='huhan')
TOKEN = 'lab-manager-internal-token-change-me'
QA_PASS = 'Qa-Member@2026'
created = {'user': None, 'borrow': None, 'checkins': [], 'open_records': [], 'files': []}


def login(username, password):
    s = requests.Session()
    r = s.get(f'{BASE}/login/', timeout=20)
    tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text).group(1)
    s.post(f'{BASE}/login/', data={'username': username, 'password': password,
                                   'csrfmiddlewaretoken': tok, 'next': '/plugins/lab-manager/'},
           headers={'Referer': f'{BASE}/login/'}, timeout=30)
    r2 = s.get(f'{BASE}/plugins/lab-manager/', timeout=20)
    ok = '登录' not in r2.url
    print(f'   login {username}: final={r2.url} ok={ok}')
    return s


def head(n, t):
    print()
    print('=' * 92)
    print(f'== {n}. {t}')


try:
    # ── 准备测试账号与数据 ────────────────────────────────
    qa, _ = U.objects.get_or_create(username='qa_member', defaults={'email': 'qa@example.com'})
    qa.is_superuser = False
    qa.is_staff = False
    qa.is_active = True
    qa.set_password(QA_PASS)
    qa.save()
    created['user'] = qa.pk

    hw = Hardware.objects.first()
    rec = HardwareBorrowRecord.objects.create(
        hardware=hw, borrower=HUHAN, purpose='QA 测试借出（可删）', notes='QA-TEST',
    )
    created['borrow'] = rec.pk
    print(f'   准备：qa_member pk={qa.pk}, 测试借出记录 pk={rec.pk} (归属 huhan), 硬件 pk={hw.pk}')

    admin_s = login('admin', 'Lab-Manager@2026')
    qa_s = login('qa_member', QA_PASS)

    head(1, 'Agent API 令牌 + X-User-ID 冒充')
    anon = requests.Session()
    ep = f'{BASE}/plugins/lab-manager/api/agent/members/search/'
    r = anon.post(ep, json={'keyword': ''}, timeout=20)
    print(f'   匿名+无令牌          -> {r.status_code} {r.text[:140]}')
    r = anon.post(ep, json={'keyword': ''}, headers={'X-Agent-Token': 'wrong'}, timeout=20)
    print(f'   匿名+错误令牌        -> {r.status_code} {r.text[:140]}')
    r = anon.post(ep, json={'keyword': ''}, headers={'X-Agent-Token': TOKEN}, timeout=20)
    print(f'   匿名+配置令牌+无X-User-ID -> {r.status_code} {r.text[:140]}')
    r = anon.post(ep, json={'keyword': ''},
                  headers={'X-Agent-Token': TOKEN, 'X-User-ID': str(ADMIN_PK)}, timeout=20)
    print(f'   匿名+令牌+冒充超管   -> {r.status_code}')
    print('   响应片段:', r.text[:400])
    leaked = re.findall(r'"(?:email|username)":\s*"([^"]+)"', r.text)
    print(f'   泄露的账号/邮箱数量: {len(leaked)} 样例={leaked[:5]}')

    r = anon.post(f'{BASE}/plugins/lab-manager/api/agent/member-open-records/search/',
                  json={}, headers={'X-Agent-Token': TOKEN, 'X-User-ID': str(ADMIN_PK)}, timeout=20)
    print(f'   超管专属端点(member-open-records) -> {r.status_code}')

    head(2, '媒体文件匿名访问')
    media_paths = []
    for obj, field in [(CheckInRecord.objects.exclude(photo='').first(), 'photo'),
                       (TaskAttachment.objects.first(), 'file')]:
        if obj is not None:
            f = getattr(obj, field)
            if f:
                media_paths.append(('', f.name))
    for hwf in ('image', 'invoice_image'):
        h = Hardware.objects.exclude(**{hwf: ''}).exclude(**{f'{hwf}__isnull': True}).first()
        if h and getattr(h, hwf):
            media_paths.append(('', getattr(h, hwf).name))
    if not media_paths:
        print('   库里没有已上传文件，改为直接探测已知目录下的磁盘文件')
        root = str(settings.MEDIA_ROOT)
        for sub in ['checkins/photos', 'task_attachments', 'hardware/physical', 'hardware/invoice']:
            d = os.path.join(root, *sub.split('/'))
            if os.path.isdir(d):
                for fn in os.listdir(d)[:2]:
                    media_paths.append(('', f'{sub}/{fn}'))
    print(f'   测试媒体路径: {media_paths[:6]}')
    for _, mp in media_paths[:6]:
        url = f'{BASE}/media/{mp}'
        ra = requests.get(url, timeout=20)
        rq = qa_s.get(url, timeout=20)
        print(f'   anon={ra.status_code} qa_member={rq.status_code}  {url}')

    head(3, '普通成员访问他人数据')
    tests = [
        ('他人成员详情', f'/plugins/lab-manager/members/{HUHAN.pk}/'),
        ('他人用户资料', f'/plugins/lab-manager/members/{ADMIN_PK}/'),
        ('硬件详情', f'/plugins/lab-manager/hardware/{hw.pk}/'),
        ('他人借出记录详情', f'/plugins/lab-manager/borrow-records/{rec.pk}/'),
        ('他人借出记录编辑页', f'/plugins/lab-manager/borrow-records/{rec.pk}/edit/'),
        ('[应为超管专属] 成员浏览记录', '/plugins/lab-manager/member-open-records/'),
        ('[应为超管专属] 智能体工具管理', '/plugins/lab-manager/agent-tools/'),
        ('[应为超管专属] 通知发送', '/plugins/lab-manager/notifications/send/'),
        ('[应为超管专属] 硬件删除页', f'/plugins/lab-manager/hardware/{hw.pk}/delete/'),
    ]
    for name, path in tests:
        r = qa_s.get(BASE + path, timeout=25, allow_redirects=False)
        loc = r.headers.get('Location', '')
        print(f'   {r.status_code}  {name:26s} {path}  {("-> " + loc) if loc else ""}')

    head(4, '普通成员修改他人借出记录（POST 实测）')
    before = HardwareBorrowRecord.objects.get(pk=rec.pk).notes
    r = qa_s.get(f'{BASE}/plugins/lab-manager/borrow-records/{rec.pk}/edit/', timeout=20)
    html = r.text
    tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
    fields = dict(re.findall(r'<input[^>]*name="(\w+)"[^>]*value="([^"]*)"', html))
    payload = {k: v for k, v in fields.items() if k != 'csrfmiddlewaretoken'}
    payload.update({'csrfmiddlewaretoken': tok.group(1) if tok else '', 'notes': 'QA-TEST-HIJACKED',
                    'hardware': str(hw.pk), 'borrower': str(HUHAN.pk), 'status': 'borrowed'})
    r2 = qa_s.post(f'{BASE}/plugins/lab-manager/borrow-records/{rec.pk}/edit/', data=payload,
                   headers={'Referer': f'{BASE}/plugins/lab-manager/borrow-records/{rec.pk}/edit/'},
                   timeout=25)
    after = HardwareBorrowRecord.objects.get(pk=rec.pk).notes
    print(f'   POST 状态={r2.status_code}  编辑前 notes={before!r}  编辑后 notes={after!r}')
    print(f'   >>> 越权修改{"成功（漏洞）" if after != before else "未生效"}')
    print('   表单字段:', sorted(payload.keys()))

    head(5, 'CSRF 保护')
    r = qa_s.post(f'{BASE}/plugins/lab-manager/notifications/read-all/', timeout=20)
    print(f'   已登录、无 CSRF token POST read-all -> {r.status_code}')
    r = qa_s.get(f'{BASE}/plugins/lab-manager/notifications/read-all/', timeout=20)
    print(f'   GET read-all（GET 就改状态？）      -> {r.status_code}')

    head(7, '打卡重复提交（同一份 payload 连发 2 次）')
    png = bytes.fromhex(
        '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489'
        '0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082')
    dup_ids = []
    for i in range(2):
        r = qa_s.get(f'{BASE}/plugins/lab-manager/checkins/new/', timeout=25)
        tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text)
        data = {
            'csrfmiddlewaretoken': tok.group(1),
            'latitude': '39.9042000', 'longitude': '116.4074000', 'accuracy': '10',
            'address': 'QA 测试地址', 'note': 'QA-TEST-DUP',
        }
        files = {'photo': ('qa_test.png', io.BytesIO(png), 'image/png')}
        rr = qa_s.post(f'{BASE}/plugins/lab-manager/checkins/new/', data=data, files=files,
                       headers={'Referer': f'{BASE}/plugins/lab-manager/checkins/new/'}, timeout=40)
        print(f'   第{i + 1}次 POST -> {rr.status_code}')
    dup = list(CheckInRecord.objects.filter(note='QA-TEST-DUP').values_list('pk', flat=True))
    created['checkins'] = dup
    created['open_records'] = list(MemberOpenRecord.objects.filter(
        user=qa, target_type='checkin').values_list('pk', flat=True))
    print(f'   连发 2 次后落库的 CheckInRecord 条数 = {len(dup)} (pk={dup})')
    print(f'   同步产生的 MemberOpenRecord 条数 = {len(created["open_records"])}')
    for c in CheckInRecord.objects.filter(pk__in=dup):
        print(f'     pk={c.pk} lat={c.latitude} lng={c.longitude} note={c.note} photo={c.photo.name}')
        if c.photo:
            created['files'].append(c.photo.path)

finally:
    print()
    print('=' * 92)
    print('== 清理测试数据')
    try:
        if created['borrow']:
            HardwareBorrowRecord.objects.filter(pk=created['borrow']).delete()
            print('   已删除测试借出记录')
        for cid in created['checkins']:
            obj = CheckInRecord.objects.filter(pk=cid).first()
            if obj and obj.photo:
                try:
                    if os.path.exists(obj.photo.path):
                        os.remove(obj.photo.path)
                except Exception:  # noqa: BLE001
                    pass
            CheckInRecord.objects.filter(pk=cid).delete()
        print(f'   已删除测试打卡记录 {len(created["checkins"])} 条')
        MemberOpenRecord.objects.filter(pk__in=created['open_records']).delete()
        if created['user']:
            U.objects.filter(pk=created['user']).delete()
            print('   已删除 qa_member 账号')
    except Exception as e:  # noqa: BLE001
        print('   清理异常:', e)
