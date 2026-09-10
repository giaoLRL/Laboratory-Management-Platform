"""检查/清理：用户级分页偏好会覆盖 PAGINATE_COUNT"""
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

User = get_user_model()
found = False
for u in User.objects.all():
    cfg = u.config
    if not isinstance(cfg, dict):
        continue
    pp = cfg.get('pagination', {}).get('per_page') if isinstance(cfg.get('pagination'), dict) else cfg.get('pagination.per_page')
    if pp:
        found = True
        print(f'用户 {u.username} 保存了分页偏好 per_page={pp}')
if not found:
    print('没有用户保存过分页偏好，PAGINATE_COUNT=10 会直接生效')

from netbox.config import get_config  # noqa: E402

c = get_config()
print('PAGINATE_COUNT =', c.PAGINATE_COUNT, '| MAX_PAGE_SIZE =', c.MAX_PAGE_SIZE)
