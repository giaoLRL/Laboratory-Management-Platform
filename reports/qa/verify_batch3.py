"""批次3 回归验证：打卡幂等/统计口径、借出归属与创建约束、评论 tags、库存回补。"""
import io
import os
import re
import sys

import django

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

import requests  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402

from lab_manager.models import (  # noqa: E402
    CheckInRecord, Hardware, HardwareBorrowRecord, MemberOpenRecord, Notification,
    Task, TaskComment,
)

BASE = 'http://127.0.0.1:8001'
U = get_user_model()
admin = U.objects.get(username='admin')
huhan = U.objects.get(username='huhan')
results = []


def check(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('  PASS ' if ok else '  FAIL ') + name + (f'  {detail}' if detail else ''))


def login(u, p):
    s = requests.Session()
    r = s.get(f'{BASE}/login/', timeout=20)
    tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text).group(1)
    s.post(f'{BASE}/login/', data={'username': u, 'password': p, 'csrfmiddlewaretoken': tok,
                                   'next': '/plugins/lab-manager/'},
           headers={'Referer': f'{BASE}/login/'}, timeout=30)
    return s


def tok_of(s, path):
    r = s.get(BASE + path, timeout=20)
    m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text)
    return m.group(1) if m else s.cookies.get('csrftoken')


PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489'
    '0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082')

qa, _ = U.objects.get_or_create(username='qa_b3', defaults={'email': 'qb3@example.com'})
qa.set_password('Qa-B3@2026'); qa.is_superuser = False; qa.is_active = True; qa.save()
from users.models import Group  # noqa: E402

_member_group = Group.objects.filter(name='实验室成员').first()
if _member_group:
    qa.groups.add(_member_group)
    print(f'   已把 qa_b3 加入「实验室成员」组（权限裁剪下才能选到硬件）')
s_qa = login('qa_b3', 'Qa-B3@2026')
s_admin = login('admin', 'Lab-Manager@2026')
hw = Hardware.objects.filter(quantity__gte=3).first()
q0 = hw.quantity
created = {'checkins': [], 'borrows': []}

try:
    print('== 1. 打卡幂等（P1-1）==')
    for i in range(2):
        t = tok_of(s_qa, '/plugins/lab-manager/checkins/new/')
        r = s_qa.post(f'{BASE}/plugins/lab-manager/checkins/new/',
                      data={'csrfmiddlewaretoken': t, 'latitude': '39.9042', 'longitude': '116.4074',
                            'accuracy': '10', 'address': 'QA', 'note': 'QA-B3'},
                      files={'photo': ('qa_b3.png', io.BytesIO(PNG), 'image/png')},
                      headers={'Referer': BASE + '/plugins/lab-manager/checkins/new/'}, timeout=30)
        print(f'   第{i + 1}次 POST -> {r.status_code} {r.url.replace(BASE, "")}')
    n = CheckInRecord.objects.filter(user=qa, note='QA-B3').count()
    check('连发 2 次只落库 1 条', n == 1, f'实际 {n} 条')
    created['checkins'] = list(CheckInRecord.objects.filter(user=qa).values_list('pk', flat=True))

    print('== 2. 统计口径：浏览打卡详情不再计入 checkin（P1-1）==')
    if created['checkins']:
        pk = created['checkins'][0]
        s_qa.get(f'{BASE}/plugins/lab-manager/checkins/{pk}/', timeout=20)
        via_checkin = MemberOpenRecord.objects.filter(user=qa, target_type='checkin').count()
        via_detail = MemberOpenRecord.objects.filter(user=qa, target_type='checkin_detail').count()
        check('target_type=checkin 只来自真实打卡', via_checkin == 1, f'实际 {via_checkin}')
        check('浏览详情记为 checkin_detail', via_detail >= 1, f'实际 {via_detail}')

    print('== 3. 借出记录归属（P1-11）==')
    rec = HardwareBorrowRecord.objects.create(hardware=hw, borrower=huhan, purpose='QA-B3-IDOR', notes='ORIG')
    created['borrows'].append(rec.pk)
    hw.refresh_from_db()
    check('借出扣减库存', hw.quantity == q0 - 1, f'{q0} -> {hw.quantity}')
    st = s_qa.get(f'{BASE}/plugins/lab-manager/borrow-records/{rec.pk}/', timeout=20, allow_redirects=False).status_code
    check('非归属成员看详情 -> 302', st == 302, f'实际 {st}')
    st = s_qa.get(f'{BASE}/plugins/lab-manager/borrow-records/{rec.pk}/edit/', timeout=20, allow_redirects=False).status_code
    check('非归属成员进编辑页 -> 302', st == 302, f'实际 {st}')
    check('超管看详情 -> 200',
          s_admin.get(f'{BASE}/plugins/lab-manager/borrow-records/{rec.pk}/', timeout=20).status_code == 200)

    print('== 4. 成员登记借出不能指定他人（P1-11）==')
    t = tok_of(s_qa, '/plugins/lab-manager/borrow-records/add/')
    r = s_qa.post(f'{BASE}/plugins/lab-manager/borrow-records/add/',
                  data={'csrfmiddlewaretoken': t, 'hardware': str(hw.pk), 'borrower': str(huhan.pk),
                        'purpose': 'QA-B3-FORGE', 'notes': ''},
                  headers={'Referer': BASE + '/plugins/lab-manager/borrow-records/add/'},
                  timeout=30, allow_redirects=False)
    forged = HardwareBorrowRecord.objects.filter(purpose='QA-B3-FORGE').first()
    if forged:
        created['borrows'].append(forged.pk)
        check('借用人被强制为本人', forged.borrower_id == qa.pk,
              f'实际 borrower={forged.borrower.username}')
    else:
        check('借用人被强制为本人', False, f'未创建（POST {r.status_code}）')

    print('== 5. 评论 tags 不再丢失（P2）==')
    task = Task.objects.first()
    t = tok_of(s_admin, f'/plugins/lab-manager/tasks/{task.pk}/')
    before = TaskComment.objects.filter(task=task).count()
    r = s_admin.post(f'{BASE}/plugins/lab-manager/tasks/{task.pk}/comment/',
                     data={'csrfmiddlewaretoken': t, 'content': 'QA-B3 评论'},
                     headers={'Referer': BASE + f'/plugins/lab-manager/tasks/{task.pk}/'}, timeout=30)
    after = TaskComment.objects.filter(task=task).count()
    check('评论提交成功', after == before + 1, f'{before} -> {after} (HTTP {r.status_code})')

    print('== 6. 删除借出记录归还库存（P0-3 完整性）==')
    pk = created['borrows'][0]
    HardwareBorrowRecord.objects.filter(pk=pk).delete()
    created['borrows'].remove(pk)
    hw.refresh_from_db()
    outstanding = HardwareBorrowRecord.objects.filter(hardware=hw, status='borrowed').count()
    check('删除后库存回补（= 总量 - 未归还数）',
          hw.quantity == q0 - outstanding, f'可用={hw.quantity} 期望={q0}-{outstanding}')

finally:
    print()
    print('== 清理 ==')
    for cid in created['checkins']:
        obj = CheckInRecord.objects.filter(pk=cid).first()
        if obj and obj.photo:
            try:
                if os.path.exists(obj.photo.path):
                    os.remove(obj.photo.path)
            except OSError:
                pass
        CheckInRecord.objects.filter(pk=cid).delete()
    HardwareBorrowRecord.objects.filter(pk__in=created['borrows']).delete()
    HardwareBorrowRecord.objects.filter(purpose__startswith='QA-B3').delete()
    MemberOpenRecord.objects.filter(user=qa).delete()
    TaskComment.objects.filter(content='QA-B3 评论').delete()
    Notification.objects.filter(user__username='qa_b3').delete()
    U.objects.filter(username='qa_b3').delete()
    hw.refresh_from_db()
    print(f'   清理完成；硬件库存={hw.quantity}（初始 {q0}）')

print()
bad = [r for r in results if not r[1]]
print(f'总计 {len(results)} 项，通过 {len(results) - len(bad)}，失败 {len(bad)}')
for n, _, d in bad:
    print('   FAIL:', n, d)
sys.exit(1 if bad else 0)
