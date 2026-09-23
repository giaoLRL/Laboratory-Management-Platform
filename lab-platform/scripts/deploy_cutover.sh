#!/bin/bash
# ──────────────────────────────────────────────────────────
#  具身智能实验室 · 独立管理平台一键切换部署
#  ⚠️ 2GB 内存机器，采用快速切：停 NetBox → 迁移 → 启动 lab → 切 nginx
#  运行：ssh lab-gz "sudo bash -s" < deploy_cutover.sh
# ──────────────────────────────────────────────────────────
set -e

LAB_DIR=/opt/lab
BACKUP_DIR=/opt/lab/backups
DATE=$(date +%Y%m%d_%H%M%S)

echo "================== 一键切换部署 START ($DATE) =================="

# ── 0. 备份（NetBox DB 已在备份目录，这里只确保 docker-compose 和 media 在）──
echo "[0/8] 二次确认备份..."
ls -la $BACKUP_DIR 2>/dev/null | head -5 || echo "WARNING: 备份目录不存在"

# ── 1. 创建 lab2 DB（如果不存在）──
echo "[1/8] 创建 lab2 Postgres database..."
docker exec lab-netbox-postgres-1 psql -U netbox -c "SELECT 1 FROM pg_database WHERE datname='lab2'" | grep -q 1 || {
    docker exec lab-netbox-postgres-1 psql -U netbox -c "CREATE DATABASE lab2;"
    echo "  lab2 created"
}

# ── 2. 构建 lab 镜像 ──
echo "[2/8] 构建新 lab 镜像..."
cd $LAB_DIR
# 本地代码目录（scp 过来的 lab-platform/）
if [ ! -d lab-platform ]; then
    echo "ERROR: lab-platform/ 目录不存在于 $LAB_DIR"
    echo "  请先 scp lab-platform/ 到服务器 /opt/lab/"
    exit 1
fi
docker build -t lab-platform:latest -f lab-platform/Dockerfile lab-platform/
echo "  image built: lab-platform:latest"

# ── 3. 停 NetBox web（保留 postgres + redis）──
echo "[3/8] 停 NetBox web（保留 postgres/redis）..."
cd $LAB_DIR
# docker-compose stop netbox 会停掉 netbox service，但保留 postgres/redis
docker compose stop netbox 2>/dev/null || true
# 或者直接 stop netbox container
docker stop lab-netbox-netbox-1 2>/dev/null || true
echo "  NetBox web stopped"

# 此时内存压力解除，启动新服务
free -h | head -2

# ── 4. 启新 lab 容器（自动 migrate）──
echo "[4/8] 启动 lab-platform 容器..."
docker rm -f lab-lab-1 2>/dev/null || true

docker run -d --name lab-lab-1 \
  --network lab-netbox_default \
  -p 8001:8001 \
  -e LAB_DEBUG=0 \
  -e LAB_SECRET_KEY=prod-secret-$(date +%s)-CHANGE-THIS-IN-PRODUCTION \
  -e LAB_ALLOWED_HOSTS=wuyuan.me,www.wuyuan.me,127.0.0.1 \
  -e LAB_DB_ENGINE=postgres \
  -e LAB_DB_NAME=lab2 \
  -e LAB_DB_HOST=lab-netbox-postgres-1 \
  -e LAB_DB_PORT=5432 \
  -e LAB_DB_USER=netbox \
  -e LAB_DB_PASSWORD=netbox123 \
  -v $LAB_DIR/media:/app/media \
  lab-platform:latest
echo "  lab-lab-1 started"

# ── 5. 等 lab 起来 + 跑 ETL ──
echo "[5/8] 等 lab 启动 + 运行 ETL..."
for i in $(seq 1 30); do
    if docker logs lab-lab-1 2>&1 | grep -q "Watching for file changes\|Starting gunicorn\|Applying migrations\|System check"; then
        break
    fi
    sleep 2
done
# 更靠谱的方式：等端口监听
for i in $(seq 1 30); do
    if docker exec lab-lab-1 bash -c "echo > /dev/tcp/127.0.0.1/8001" 2>/dev/null; then break; fi
    sleep 2
done

echo "  等 gunicorn 就绪后跑 ETL..."
docker exec lab-lab-1 python manage.py shell -c "
import os
os.environ['SOURCE_DB_HOST']='lab-netbox-postgres-1'
os.environ['SOURCE_DB_PORT']='5432'
os.environ['SOURCE_DB_NAME']='netbox'
os.environ['SOURCE_DB_USER']='netbox'
os.environ['SOURCE_DB_PASSWORD']='netbox123'
exec(open('/app/scripts/etl.py').read())
" 2>&1 | tee /tmp/etl_output_$DATE.log

echo "  ETL done"

# ── 6. 冒烟测试（lab 容器内部）──
echo "[6/8] 后端冒烟测试..."
docker exec lab-lab-1 python -c "
import urllib.request, json
try:
    r = urllib.request.urlopen('http://127.0.0.1:8001/api/auth/me')
except urllib.error.HTTPError as e:
    # 401 是未登录，预期行为
    if e.code == 401:
        print('  [OK] 401 未登录拦截（预期行为）')
    else:
        print(f'  [FAIL] auth/me HTTP {e.code}')
        raise
except Exception as e:
    print(f'  [FAIL] 8001 端口不可达: {e}')
    raise
print('  [OK] lab gunicorn 响应正常')
"

# ── 7. 部署 SPA 静态 + nginx 切换 ──
echo "[7/8] 部署 SPA + 切 nginx..."
# SPA 静态目录（scp 过来的 lab-platform-web/）
SPA_SRC=$LAB_DIR/lab-platform-web
SPA_DEST=$LAB_DIR/spa
mkdir -p $SPA_DEST
# 用 rsync 或 cp
rsync -av --delete $SPA_SRC/ $SPA_DEST/ --exclude .git --exclude node_modules 2>/dev/null || \
  cp -a $SPA_SRC/. $SPA_DEST/ 2>/dev/null

# nginx 配置（修改 netbox_ssl.conf）
NGINX_VHOST=/www/server/panel/vhost/nginx/netbox_ssl.conf
if [ -f $NGINX_VHOST ]; then
    cp $NGINX_VHOST ${NGINX_VHOST}.bak.$DATE
    echo "  备份 nginx conf → ${NGINX_VHOST}.bak.$DATE"
    # 替换 proxy_pass 从 127.0.0.1:8000 到 127.0.0.1:8001 for /api/
    # 把根路径改为 SPA static
fi

# 临时：启动新 lab 容器，保留 nginx 指向 8000（NetBox 停了）
# 手动切 nginx：把原来的 netbox_ssl.conf 里
#   1) /api/ 反代到 127.0.0.1:8001
#   2) 根 location / 指向 /opt/lab/spa
# 然后 nginx -t && nginx -s reload

# ── 8. 状态汇总 ──
echo ""
echo "================== 切换完成 =================="
echo "lab-lab-1 运行中: $(docker ps --filter name=lab-lab-1 --format '{{.Status}}')"
echo "NetBox 已停:      $(docker ps --filter name=lab-netbox-netbox-1 --format '{{.Status}}')"
echo "Postgres:         $(docker ps --filter name=lab-netbox-postgres-1 --format '{{.Status}}')"
echo ""
echo "⚠️ 还需手动切 nginx："
echo "  vi $NGINX_VHOST"
echo "    proxy_pass 127.0.0.1:8001;  # /api/"
echo "    root /opt/lab/spa;          # 根路径"
echo "  nginx -t && nginx -s reload"
echo ""
echo "回滚（如果失败）："
echo "  docker stop lab-lab-1 && docker rm lab-lab-1"
echo "  docker start lab-netbox-netbox-1"
echo "  # 还原 nginx conf 并 reload"
