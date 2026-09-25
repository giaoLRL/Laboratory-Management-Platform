"""关卡系统模拟数据（本地演示）：技能线关卡 + 任务 + 通关记录 + 审核人。"""

import os
import sys
import django

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lab_api.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.accounts.models import MemberProfile
from apps.common.ids import next_code
from apps.levels.models import Level, LevelTask, PassRecord, LevelReviewer
from apps.tasksapp.models import Task

User = get_user_model()

# 清空旧数据（演示可重跑）
LevelTask.objects.all().delete()
PassRecord.objects.all().delete()
LevelReviewer.objects.all().delete()
Level.objects.all().delete()
Task.objects.filter(title__startswith='【关】').delete()

active = list(MemberProfile.objects.filter(active=True).select_related('user'))
by_name = {}
for p in active:
    by_name[p.name] = p


def user_of(name):
    p = by_name.get(name)
    return p.user if p else active[0].user


LEVELS = [
    # (title, chain, chapter, order, score_limit, stars_rule, require_title, desc)
    ('点亮一颗LED', '51单片机', '基础', 1, 100, '60,80', None, '掌握 GPIO 输出，点亮第一颗灯。'),
    ('按键与中断', '51单片机', '基础', 2, 100, '60,80', None, '用按键触发外部中断。'),
    ('串口通信', '51单片机', '进阶', 3, 120, '70,90', '点亮一颗LED', '与上位机完成串口收发。'),
    ('智能传感融合', '51单片机', '大师', 4, 150, '80,100', '按键与中断', '多传感器融合应用。'),
    ('局域网组网', '物联网', '基础', 1, 100, '60,80', None, '完成 ESP 局域网通信。'),
    ('MQTT 云接入', '物联网', '进阶', 2, 120, '70,90', '局域网组网', '设备上云并完成双向控制。'),
    ('电源设计', '电赛', '基础', 1, 100, '60,80', None, '完成低压差稳压电源。'),
    ('信号调理', '电赛', '进阶', 2, 120, '70,90', '电源设计', '放大与滤波信号调理。'),
    ('飞控调参', '无人机', '进阶', 1, 120, '70,90', None, '完成飞控稳定悬停调参。'),
]

level_map = {}
teacher = User.objects.filter(username='teacher').first() or active[0].user
manager = User.objects.filter(username='manager').first() or active[0].user

for title, chain, chapter, order, sl, sr, pre, desc in LEVELS:
    require = level_map.get(pre) if pre else None
    lv = Level.objects.create(id=next_code(Level, 'LV'), title=title, chain=chain, chapter=chapter,
                              order=order, score_limit=sl, stars_rule=sr, require_pass=require,
                              description=desc, creator=teacher)
    if pre:
        lv.require_pass = require
        lv.save(update_fields=['require_pass', 'updated'])
    level_map[title] = lv

# 任务：每关挂 1-2 个任务
task_specs = [
    ('点亮一颗LED', '【关】LED 呼吸灯', 'led', '编写代码点亮 LED 并实现呼吸效果'),
    ('点亮一颗LED', '【关】LED 流水灯', 'led2', '实现 8 颗灯流水循环'),
    ('串口通信', '【关】串口回显', 'uart', '上位机发指令回显并点亮指定灯'),
    ('MQTT 云接入', '【关】MQTT 双向控制', 'mqtt', '云端下发命令控制本机 LED'),
    ('电源设计', '【关】5V 稳压电源', 'psu', '完成 AMS1117 稳压电路并测试'),
]
for lv_title, ttitle, tid, tdesc in task_specs:
    task = Task.objects.create(id=next_code(Task, 'TASK'), title=ttitle, description=tdesc,
                               creator=teacher, status='todo', priority='normal')
    LevelTask.objects.create(level=level_map[lv_title], task=task)

# 通关记录：不同成员分布通关/待审
def add_pass(lv_title, member_name, status, score, stars, featured=False, first=False, note=''):
    lv = level_map[lv_title]
    u = user_of(member_name)
    rec = PassRecord.objects.create(id=next_code(PassRecord, 'PR'), level=lv, member=u, status=status,
                                    score=score, stars=stars, featured=featured, first_pass=first,
                                    best_score=score, best_at=None, note=note,
                                    reviewer=teacher if status in ('passed', 'rejected') else None,
                                    opinion='完成质量不错，继续加油。' if status == 'passed' else
                                    ('请补充实验照片后重新提交。' if status == 'rejected' else ''))
    return rec

add_pass('点亮一颗LED', '张子涵', 'passed', 92, 3, featured=True, first=True, note='呼吸平滑，波形稳定。')
add_pass('点亮一颗LED', '成员甲', 'passed', 78, 2)
add_pass('按键与中断', '张子涵', 'passed', 85, 2, first=True)
add_pass('串口通信', '张子涵', 'pending', 0, 0, note='已提交串口回显代码与录屏。')
add_pass('局域网组网', '成员甲', 'passed', 66, 1)
add_pass('电源设计', '成员甲', 'rejected', 0, 0, note='输出电压纹波偏大。')

# 审核人：teacher + manager
for uname in ('teacher', 'manager'):
    u = User.objects.filter(username=uname).first()
    if u:
        LevelReviewer.objects.get_or_create(level=level_map['点亮一颗LED'], member=u, defaults={'added_by': teacher})

print(f'已生成关卡 {Level.objects.count()} 个、任务 {Task.objects.filter(title__startswith="【关】").count()} 个、'
      f'通关记录 {PassRecord.objects.count()} 条、审核人 {LevelReviewer.objects.count()} 个')