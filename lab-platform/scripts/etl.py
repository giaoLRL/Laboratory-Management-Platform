"""ETL 脚本：从 NetBox Postgres 迁移数据到新 lab-platform。

运行方式（在 lab-platform 目录下）：
  # 1. 先本地干跑（不写入）
  ..\\netbox-main\\venv\\Scripts\\python.exe manage.py shell < scripts/etl.py

  # 2. 服务器上：先停 NetBox web，然后：
  docker compose up -d postgres   # 确保 postgres 跑
  docker exec netbox-postgres psql -U netbox -c "CREATE DATABASE lab2;"
  LAB_DB_ENGINE=postgres LAB_DB_NAME=lab2 LAB_DB_HOST=localhost LAB_DB_PORT=5433 LAB_DB_USER=netbox LAB_DB_PASSWORD=netbox123 \
    python manage.py migrate
  python manage.py shell < scripts/etl.py

环境变量：
  SOURCE_DB_HOST/PORT/NAME/USER/PASSWORD  (NetBox Postgres)
"""
import os, sys, json, re
from pathlib import Path

# ── 源（NetBox Postgres）──
SRC_HOST = os.environ.get('SOURCE_DB_HOST', '127.0.0.1')
SRC_PORT = int(os.environ.get('SOURCE_DB_PORT', '5433'))
SRC_NAME = os.environ.get('SOURCE_DB_NAME', 'netbox')
SRC_USER = os.environ.get('SOURCE_DB_USER', 'netbox')
SRC_PASS = os.environ.get('SOURCE_DB_PASSWORD', 'netbox123')

DRY_RUN = os.environ.get('ETL_DRY_RUN', '0') == '1'

print(f"=== ETL START (dry_run={DRY_RUN}) ===")
print(f"Source: postgresql://{SRC_USER}@{SRC_HOST}:{SRC_PORT}/{SRC_NAME}")
print(f"Target: Django default DB ({os.environ.get('LAB_DB_ENGINE', 'sqlite')})")

import psycopg
from django.contrib.auth.models import User

# ── 连接源 DB ──
try:
    src = psycopg.connect(
        host=SRC_HOST, port=SRC_PORT, dbname=SRC_NAME,
        user=SRC_USER, password=SRC_PASS, connect_timeout=5
    )
except Exception as e:
    print(f"FATAL: 连不上 NetBox Postgres: {e}")
    sys.exit(1)
cur = src.cursor()

# ── 状态/分类映射 ──
STATUS_MAP = {
    'idle': '空闲',
    'in_use': '使用中',
    'maintenance': '维修中',
    'scrapped': '报废',
}
CATEGORY_MAP = {
    'mcu': '单板计算机',
    'module': '开发板',
    'sensor': '传感器',
    'tool': '调试工具',
    'other': '其他',
    'comm': '通信模块',
    'actuator': '执行器',
}
def cat_map(v):
    return CATEGORY_MAP.get(v.lower(), v or '')

# ── 用户迁移 ──
print("\n--- [1] USERS ---")
cur.execute("SELECT id, username, password, first_name, last_name, email, is_active, is_superuser, date_joined FROM users_user ORDER BY id")
src_users = cur.fetchall()
print(f"  source users_user: {len(src_users)} rows")
# 建立 pk 映射（保留源 pk）
user_pk_map = {}
for row in src_users:
    pk, username, password, first, last, email, active, superuser, joined = row
    try:
        u = User.objects.get(pk=pk)
        created = False
    except User.DoesNotExist:
        u = User(pk=pk)
        created = True
    u.username = username
    # 直接保留 NetBox 的 PBKDF2 hash 字符串：
    # set_password() 会把 hash 当明文再哈希一次，导致老用户全部无法登录！
    u.password = password if (password and '$' in password) else '!'
    u.first_name = first or ''
    u.last_name = last or ''
    u.email = email or ''
    u.is_active = active
    u.is_staff = superuser
    u.is_superuser = superuser
    if joined:
        u.date_joined = joined  # 保留 NetBox 注册时间（原来是 timezone.now()，bug）
    if DRY_RUN:
        print(f"  [DRY] {'CREATE' if created else 'UPDATE'} User pk={pk} username={username} superuser={superuser}")
    else:
        u.save()
    user_pk_map[pk] = u.pk  # 源 pk → 新 pk（通常相同）

# MemberProfile（新库独有，NetBox 没有此表）
from apps.accounts.models import MemberProfile
for src_pk, new_pk in user_pk_map.items():
    u = User.objects.get(pk=new_pk)
    name = (u.first_name or u.username) + (u.last_name or '')
    role = 'teacher' if u.is_superuser else 'member'
    number = f"NB-{src_pk:04d}"
    try:
        mp = MemberProfile.objects.get(user=u)
        mp.name = name[:32] or username
        mp.role = role
        if not mp.number or mp.number.startswith('NB-'):
            mp.number = number
        if DRY_RUN: print(f"  [DRY] UPDATE MemberProfile user={username} role={role}")
        else: mp.save()
    except MemberProfile.DoesNotExist:
        if DRY_RUN: print(f"  [DRY] CREATE MemberProfile user={username} role={role} number={number}")
        else:
            MemberProfile.objects.create(
                user=u, name=name[:32] or username,
                number=number, role=role, active=bool(u.is_active),
                joined=u.date_joined,
            )

print(f"  users migrated: {len(user_pk_map)}")

# ── 硬件迁移 ──
print("\n--- [2] HARDWARE → ASSET ---")
cur.execute("""
SELECT id, name, category, model_number, manufacturer, quantity, unit_price,
       storage_location, status, remarks, image, created
FROM lab_manager_hardware ORDER BY id
""")
src_hw = cur.fetchall()
print(f"  source hardware: {len(src_hw)} rows")

from apps.inventory.models import Asset
asset_id_map = {}  # 源 pk → 新 Asset id (EM-xxx)
new_em_start = len(Asset.objects.filter(id__startswith='EM-')) + 1
for src_pk, name, category, model, manufacturer, quantity, price, location, status, remarks, image, created in src_hw:
    asset_id = f"EM-{src_pk:03d}"  # 用源 pk 直接编号，稳定
    # 备注里可能有换行，新库 Asset.note 允许 512
    note = (remarks or '')[:512]
    mapped_status = STATUS_MAP.get((status or '').lower(), '空闲')
    a = Asset(
        id=asset_id,
        name=name or f"硬件-{src_pk}",
        model=model or '',
        category=cat_map(category),
        vendor=manufacturer or '',
        spec='',
        location=location or '',
        status=mapped_status,
        note=note,
        datasheet='',
    )
    try:
        a_db = Asset.objects.get(id=asset_id)
        # 合并（保留已存在的字段）
        a_db.name = a.name
        a_db.model = a.model
        a_db.category = a.category
        a_db.vendor = a.vendor
        a_db.location = a.location
        a_db.status = a.status
        a_db.note = a.note
        if DRY_RUN: print(f"  [DRY] UPDATE Asset {asset_id} {name} [{mapped_status}]"); changed = True
        else: a_db.save()
    except Asset.DoesNotExist:
        if DRY_RUN: print(f"  [DRY] CREATE Asset {asset_id} {name} [{mapped_status}]"); changed = True
        else: a.save()
    asset_id_map[src_pk] = asset_id

print(f"  assets migrated: {len(asset_id_map)}")

# ── 智能体迁移 ──
print("\n--- [3] AGENT CONVERSATIONS + MESSAGES ---")
cur.execute("""
SELECT c.id, c.title, c.user_id, c.created, c.last_updated
FROM lab_manager_agentconversation c ORDER BY c.id
""")
src_convs = cur.fetchall()
print(f"  source conversations: {len(src_convs)} rows")

from apps.agent.models import Conversation, AgentMessage
conv_id_map = {}
for src_pk, title, user_id, created, updated in src_convs:
    if user_id not in user_pk_map:
        print(f"  SKIP conv {src_pk} (user {user_id} not in users_user)")
        continue
    conv_id = f"CONV-{src_pk:03d}"
    django_user_id = user_pk_map[user_id]
    c = Conversation(
        id=conv_id,
        user_id=django_user_id,
        title=(title or '').strip()[:128] or '迁移自 NetBox',
    )
    try:
        c_db = Conversation.objects.get(id=conv_id)
        c_db.title = c.title
        c_db.user_id = django_user_id
        if DRY_RUN: print(f"  [DRY] UPDATE Conversation {conv_id}"); changed = True
        else: c_db.save()
    except Conversation.DoesNotExist:
        if DRY_RUN: print(f"  [DRY] CREATE Conversation {conv_id}"); changed = True
        else:
            c.save()
    conv_id_map[src_pk] = conv_id

# messages
cur.execute("""
SELECT m.id, m.conversation_id, m.role, m.content, m.created
FROM lab_manager_agentmessage m ORDER BY m.created
""")
src_msgs = cur.fetchall()
print(f"  source messages: {len(src_msgs)} rows")

msg_count = 0
for src_mid, src_cid, role, content, created in src_msgs:
    if src_cid not in conv_id_map:
        continue
    new_conv_id = conv_id_map[src_cid]
    role_v = (role or 'assistant')[:16]
    content_v = (content or '')[:20000]
    # AgentMessage 没显式 id 字段，靠 conversation + role + content 去重（created 可能为 NULL）
    if AgentMessage.objects.filter(conversation_id=new_conv_id, role=role_v, content=content_v).exists():
        continue
    if DRY_RUN: msg_count += 1; continue
    obj = AgentMessage.objects.create(
        conversation_id=new_conv_id,
        role=role_v,
        content=content_v,
    )
    if created:  # auto_now_add 会忽略 create() 传入的时间，用 update 覆盖回原时间
        AgentMessage.objects.filter(pk=obj.pk).update(created=created)
    msg_count += 1
if DRY_RUN: print(f"  [DRY] would create {msg_count} messages")
else: print(f"  messages migrated/skipped: {msg_count}")

# ── 结果 ──
print(f"""
=== ETL DONE ===
users:     {len(user_pk_map)} (source {len(src_users)})
assets:    {len(asset_id_map)} (source {len(src_hw)})
convs:     {len(conv_id_map)} (source {len(src_convs)})
messages:  {msg_count}

NetBox borrow/task/checkin ALL EMPTY — skipped.
{('DRY RUN, no writes made' if DRY_RUN else 'ACTUAL DATA WRITTEN')}
""")
src.close()
