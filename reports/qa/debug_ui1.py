"""定位 member-open-records?per_page=1 的 500。"""
import os
import sys
import traceback

import django

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.test import Client  # noqa: E402

admin = get_user_model().objects.get(username='admin')
c = Client()
c.force_login(admin)
for url in ['/plugins/lab-manager/member-open-records/?per_page=1',
            '/plugins/lab-manager/member-open-records/',
            '/plugins/lab-manager/checkins/?per_page=1']:
    try:
        r = c.get(url)
        print('OK  ', r.status_code, url)
    except Exception:
        print('EXC ', url)
        traceback.print_exc()
        print('-' * 70)
