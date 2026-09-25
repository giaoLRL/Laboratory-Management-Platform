"""种子化默认实验室布局（B 区 13×11），让座位图开箱即用。

之后管理员可以在「地图编辑」界面改动，此迁移只在没有任何布局时生效，
不会覆盖已被编辑过的地图。
"""

from django.db import migrations

# . 通道空地  w 工位  s 储物柜  t 测试台  d 门口  # 墙体
DEFAULT_GRID = [
    '#############',
    '#d..........#',
    '#.ss...ss...#',
    '#.ww...ww...#',
    '#.ww...ww...#',
    '#...ttttt...#',
    '#.ww...ww...#',
    '#.ww...ww...#',
    '#.ss...ss...#',
    '#...........#',
    '#############',
]


def _seat_labels(grid):
    """按行优先顺序给工位编号 B-01…（与前端展示顺序一致）。"""
    labels, n = {}, 0
    for r, row in enumerate(grid):
        for c, kind in enumerate(row):
            if kind == 'w':
                n += 1
                labels[f'{r}-{c}'] = f'B-{n:02d}'
    return labels


def apply(apps, schema_editor):
    SeatLayout = apps.get_model('seats', 'SeatLayout')
    if SeatLayout.objects.exists():
        return
    SeatLayout.objects.create(
        id='main', name='B 区 · 实验室平面',
        rows=len(DEFAULT_GRID), cols=len(DEFAULT_GRID[0]),
        grid=DEFAULT_GRID, labels=_seat_labels(DEFAULT_GRID), owners={}, active=True)


def rollback(apps, schema_editor):
    SeatLayout = apps.get_model('seats', 'SeatLayout')
    SeatLayout.objects.filter(id='main').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('seats', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(apply, rollback),
    ]