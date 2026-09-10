"""用 MigrationAutodetector 生成 lab_manager 的模型迁移（NetBox 禁用了 makemigrations）。

用法: python fix2_migration.py [--apply]
"""
import os
import sys

import django

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

from django.apps import apps  # noqa: E402
from django.db.migrations.autodetector import MigrationAutodetector  # noqa: E402
from django.db.migrations.loader import MigrationLoader  # noqa: E402
from django.db.migrations.state import ProjectState  # noqa: E402
from django.db.migrations.writer import MigrationWriter  # noqa: E402

APPLY = '--apply' in sys.argv
loader = MigrationLoader(None, ignore_no_migrations=False)
from_state = loader.project_state()
target_state = ProjectState.from_apps(apps)
autodetector = MigrationAutodetector(from_state, target_state)
changes = autodetector.changes(graph=loader.graph)

print('检测到变更的应用:', {k: len(v) for k, v in changes.items()})

migs = changes.get('lab_manager', [])
if not migs:
    print('lab_manager 无需迁移')
    sys.exit(0)

for m in migs:
    print('=' * 80)
    print('name:', m.name)
    writer = MigrationWriter(m)
    code = writer.as_string()
    print(code)
    if APPLY:
        path = os.path.join(os.getcwd(), 'lab_manager', 'migrations', m.name + '.py')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(code)
        print('已写入', path)
