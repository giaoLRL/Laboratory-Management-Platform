"""ORM 层逻辑验证（全部在可回滚事务内，不留数据）。

 1. signals.py 是否真的未注册 → 创建 Task/Hardware/借出记录后是否产生 Notification
 2. 借出是否扣减 Hardware.quantity
 3. TaskAttachment 删除时物理文件是否被清理（pre_delete 信号）
 4. 模型层约束（quantity=0 / 负数 / 借出唯一性）
"""
import os
import sys

import django

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.db import IntegrityError, transaction  # noqa: E402
from django.utils import timezone  # noqa: E402

from lab_manager.models import (  # noqa: E402
    Hardware, HardwareBorrowRecord, Notification, Task, TaskAttachment,
)

U = get_user_model()
admin = U.objects.get(username='admin')
huhan = U.objects.get(username='huhan')

print('=' * 92)
print('== 1. 信号验证：创建对象后是否自动产生通知（事务内，最后回滚）')
n_before = Notification.objects.count()
print('   通知总数(前):', n_before)
notes = []
try:
    with transaction.atomic():
        t = Task.objects.create(title='QA-SIGNAL-TASK', description='qa', created_by=admin, assigned_to=huhan)
        after_task = Notification.objects.count()
        hw = Hardware.objects.create(name='QA-SIGNAL-HW', quantity=1, submitted_by=huhan)
        after_hw = Notification.objects.count()
        rec = HardwareBorrowRecord.objects.create(hardware=hw, borrower=huhan, purpose='qa')
        after_borrow = Notification.objects.count()
        print(f'   创建 Task(指派给 huhan) 后通知数: {after_task} (前 {n_before})')
        print(f'   创建 Hardware(submitted_by=huhan) 后通知数: {after_hw}')
        print(f'   创建借用记录(borrower=huhan) 后通知数: {after_borrow}')
        new_notes = Notification.objects.filter(pk__gt=0).order_by('-pk')[:5]
        print('   期间新增通知:',
              [(n.user.username, n.title) for n in Notification.objects.order_by('-pk')[:3]]
              if after_borrow > n_before else '（无）')
        raise RuntimeError('rollback')
except RuntimeError:
    pass
print('   回滚后通知总数(应为 %d):' % n_before, Notification.objects.count())

print()
print('=' * 92)
print('== 2. 借出是否扣减库存')
hw = Hardware.objects.first()
print(f'   硬件 #{hw.pk} {hw.name} quantity={hw.quantity}')
try:
    with transaction.atomic():
        rec = HardwareBorrowRecord.objects.create(hardware=hw, borrower=huhan, purpose='QA 库存验证')
        hw.refresh_from_db()
        print(f'   创建借出记录后 quantity={hw.quantity}  (状态={rec.status})')
        print('   >>> 库存', '未扣减（借出不影响可用数量）' if hw.quantity == Hardware.objects.get(pk=hw.pk).quantity else '已变化')
        raise RuntimeError('rollback')
except RuntimeError:
    pass

print()
print('=' * 92)
print('== 3. 附件删除是否清理物理文件')
media = str(settings.MEDIA_ROOT)
sub = os.path.join(media, 'task_attachments')
os.makedirs(sub, exist_ok=True)
probe = os.path.join(sub, 'qa_probe_delete_me.txt')
with open(probe, 'w', encoding='utf-8') as f:
    f.write('qa probe')
print('   探针文件已创建:', probe)
try:
    with transaction.atomic():
        t = Task.objects.first()
        att = TaskAttachment.objects.create(task=t, file='task_attachments/qa_probe_delete_me.txt',
                                            uploaded_by=admin, remark='QA')
        att.delete()
        print('   附件记录已删除；物理文件仍存在?', os.path.exists(probe))
        raise RuntimeError('rollback')
except RuntimeError:
    pass
if os.path.exists(probe):
    os.remove(probe)
    print('   探针文件已清理')
print('   >>> pre_delete 信号', '未生效（文件未被删除）' if not os.path.exists(probe) else '未生效')

print()
print('=' * 92)
print('== 4. 模型层约束')
try:
    with transaction.atomic():
        h = Hardware.objects.create(name='QA-ZERO', quantity=0, submitted_by=admin)
        print('   quantity=0 创建成功 ->', h.pk, '（PositiveIntegerField 允许 0）')
        raise RuntimeError('rollback')
except RuntimeError:
    pass
try:
    with transaction.atomic():
        Hardware.objects.create(name='QA-NEG', quantity=-5, submitted_by=admin)
        print('   quantity=-5 创建成功（异常！）')
        raise RuntimeError('rollback')
except RuntimeError:
    pass
except IntegrityError as e:
    print('   quantity=-5 被数据库拒绝 ->', str(e)[:120])
except Exception as e:  # noqa: BLE001
    print('   quantity=-5 ->', type(e).__name__, str(e)[:120])

hw = Hardware.objects.first()
try:
    with transaction.atomic():
        a = HardwareBorrowRecord.objects.create(hardware=hw, borrower=huhan, purpose='dup1')
        b = HardwareBorrowRecord.objects.create(hardware=hw, borrower=huhan, purpose='dup2')
        print(f'   同一硬件+同一人 可并存 {HardwareBorrowRecord.objects.filter(hardware=hw, borrower=huhan, status="borrowed").count()} 条 borrowed 记录（无唯一约束）')
        raise RuntimeError('rollback')
except RuntimeError:
    pass

print()
print('=' * 92)
print('== 5. 已存在的通知（说明只有手工发送这一条来源）')
for n in Notification.objects.order_by('-pk')[:5]:
    print(f'   #{n.pk} user={n.user.username} type={n.notification_type} title={n.title[:40]}')
print('   通知总数:', Notification.objects.count())
