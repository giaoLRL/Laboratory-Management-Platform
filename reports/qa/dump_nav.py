import os, re, sys, django
sys.path.insert(0, os.getcwd()); os.environ.setdefault('DJANGO_SETTINGS_MODULE','netbox.settings'); django.setup()
import requests
BASE='http://127.0.0.1:8001'
s=requests.Session(); r=s.get(BASE+'/login/', timeout=20)
tok=re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text).group(1)
s.post(BASE+'/login/', data={'username':'admin','password':'Lab-Manager@2026','csrfmiddlewaretoken':tok,'next':'/plugins/lab-manager/'}, headers={'Referer':BASE+'/login/'}, timeout=30)
for path in ['/plugins/lab-manager/', '/plugins/lab-manager/tasks/']:
    t = s.get(BASE+path, timeout=30).text
    i = t.find('/plugins/lab-manager/tasks/')
    print('===', path, '===')
    print(re.sub(r'\s+', ' ', t[max(0,i-320):i+120]))
    print()
