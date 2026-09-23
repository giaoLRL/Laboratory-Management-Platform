#!/bin/bash
# 服务器本地执行：清理残留 → 重建镜像（无 apt）→ 起容器 → ETL → 冒烟 → 部署 SPA → 切 nginx
set -euo pipefail
LAB=/opt/lab
NGINX=$(command -v nginx || echo /www/server/nginx/sbin/nginx)

echo "=== [1/9] 清理上次卡死的 build 残留 ==="
pkill -9 -f 'apt-get|dpkg' 2>/dev/null || true
pkill -9 -f 'docker build' 2>/dev/null || true
sleep 1
# 孤儿 build-step 容器（python:3.12-slim 里还在跑 apt-get）
docker ps -q --filter ancestor=python:3.12-slim | xargs -r docker kill 2>/dev/null || true
docker rm -f lab-lab-1 2>/dev/null || true
# 注意：不要 docker system prune —— 上次它把已停止的 NetBox 容器删了，还会清掉 build 缓存
echo "  cleaned"

echo ""
echo "=== [2/9] 确认 NetBox 备份 + 回滚资产完好 ==="
ls -la $LAB/backups/*.sql.gz | tail -2
docker images netbox-lab --format '  netbox image: {{.Repository}}:{{.Tag}} ({{.Size}})'
test -f $LAB/docker-compose.yml && echo "  compose file: OK"

echo ""
echo "=== [3/9] 确认 lab2 数据库 ==="
if ! docker exec lab-netbox-postgres-1 psql -U netbox -tAc "SELECT 1 FROM pg_database WHERE datname='lab2'" | grep -q 1; then
  docker exec lab-netbox-postgres-1 psql -U netbox -c "CREATE DATABASE lab2;"
fi
echo "  lab2: OK"

echo ""
echo "=== [4/9] 构建镜像（slim 自带 tzdata，无 apt 步骤）==="
cd $LAB
set -o pipefail
docker build -t lab-platform:latest -f lab-platform/Dockerfile lab-platform/ 2>&1 | tail -6
docker images lab-platform --format "  image: {{.Repository}}:{{.Tag}} {{.Size}}"

echo ""
echo "=== [5/9] 启动 lab 容器（自动 migrate）==="
docker run -d --name lab-lab-1 \
  --restart unless-stopped \
  --network lab-netbox_default \
  -p 8001:8001 \
  -e LAB_DEBUG=0 \
  -e LAB_SECRET_KEY=prod-$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n') \
  -e LAB_ALLOWED_HOSTS=wuyuan.me,www.wuyuan.me,127.0.0.1 \
  -e LAB_DB_ENGINE=postgres \
  -e LAB_DB_NAME=lab2 \
  -e LAB_DB_HOST=lab-netbox-postgres-1 \
  -e LAB_DB_PORT=5432 \
  -e LAB_DB_USER=netbox \
  -e LAB_DB_PASSWORD=netbox123 \
  -e LAB_LLM_API_KEY=sk-e734158e9b3f43f89e4c5605912a0d19 \
  -e LAB_LLM_BASE_URL=https://api.deepseek.com/v1 \
  -e LAB_LLM_MODEL=deepseek-chat \
  -v $LAB/data/media:/app/media \
  lab-platform:latest

echo "  等待 :8001 就绪（容器内先 migrate 再起 gunicorn）..."
ok=0
for i in $(seq 1 45); do
  sleep 2
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:8001/api/auth/me || true)
  echo "  [$i] /api/auth/me -> $code"
  if [ "$code" = "401" ] || [ "$code" = "403" ] || [ "$code" = "200" ]; then ok=1; break; fi
done
if [ "$ok" != "1" ]; then
  echo "!! lab 容器未就绪，最后日志："
  docker logs --tail 40 lab-lab-1 || true
  exit 1
fi
echo "  容器日志（migrate 尾巴）："
docker logs --tail 6 lab-lab-1

echo ""
echo "=== [6/9] ETL：NetBox → lab2 ==="
docker exec \
  -e SOURCE_DB_HOST=lab-netbox-postgres-1 \
  -e SOURCE_DB_PORT=5432 \
  -e SOURCE_DB_NAME=netbox \
  -e SOURCE_DB_USER=netbox \
  -e SOURCE_DB_PASSWORD=netbox123 \
  lab-lab-1 python manage.py shell -c "exec(open('/app/scripts/etl.py').read())"

echo ""
echo "  lab2 数据统计："
docker exec lab-netbox-postgres-1 psql -U netbox -d lab2 -c \
  "SELECT (SELECT count(*) FROM auth_user) AS users, (SELECT count(*) FROM accounts_memberprofile) AS profiles, (SELECT count(*) FROM inventory_asset) AS assets, (SELECT count(*) FROM agent_conversation) AS convs, (SELECT count(*) FROM agent_agentmessage) AS msgs" || true

echo ""
echo "=== [7/9] 冒烟测试 ==="
printf "  /api/auth/me      (expect 401/403): "
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8001/api/auth/me
printf "  /media/checkins/  (expect 401/403): "
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8001/media/checkins/nonexist.jpg
printf "  /api/workspace    (expect 401/403): "
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8001/api/workspace

echo ""
echo "=== [8/9] 部署 SPA 静态 ==="
mkdir -p $LAB/spa
cp -a $LAB/lab-platform-web/. $LAB/spa/
ls -la $LAB/spa/index.html

echo ""
echo "=== [9/9] 切 nginx ==="
cp /www/server/panel/vhost/nginx/netbox_ssl.conf $LAB/backups/netbox_ssl.conf.bak.$(date +%Y%m%d_%H%M)
cat > /www/server/panel/vhost/nginx/netbox_ssl.conf << 'NGINX_EOF'
server {
    listen 443 ssl;
    http2 on;
    server_name wuyuan.me www.wuyuan.me;

    ssl_certificate     /opt/lab/certs/fullchain.cer;
    ssl_certificate_key /opt/lab/certs/wuyuan.me.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 10m;

    client_max_body_size 50m;
    access_log /www/wwwlogs/netbox.access.log;
    error_log  /www/wwwlogs/netbox.error.log;

    # 后端 API（lab-platform Django）
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }

    # 媒体文件（Django 鉴权后返回）
    location /media/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 营销首页（原样保留）
    location = / {
        root /opt/lab/homepage;
        try_files /index.html =404;
        add_header Cache-Control "no-cache";
    }

    location /assets/ {
        alias /opt/lab/homepage/assets/;
        expires 30d;
        add_header Cache-Control "public";
    }

    # SPA 管理平台（hash 路由，其余路径回退 index.html）
    location / {
        root /opt/lab/spa;
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache";
    }
}

server {
    listen 80;
    server_name wuyuan.me www.wuyuan.me;
    location / { return 301 https://$host$request_uri; }
    location ^~ /.well-known/acme-challenge/ { root /opt/lab/homepage; }
}
NGINX_EOF

$NGINX -t && $NGINX -s reload

echo ""
echo "================== 切换完成 =================="
docker ps --filter name=lab-lab-1 --format 'lab-lab-1: {{.Status}}'
free -h | head -2
echo ""
echo "验证清单："
echo "  https://wuyuan.me/            → 营销首页（不变）"
echo "  https://wuyuan.me/#dashboard  → SPA 管理平台（用原 NetBox 密码登录）"
echo "  https://wuyuan.me/api/auth/me → 401/403 JSON"
echo ""
echo "回滚预案（三步）："
echo "  1) docker rm -f lab-lab-1"
echo "  2) cd /opt/lab && docker compose up -d netbox"
echo "  3) cp /opt/lab/backups/netbox_ssl.conf.bak.* /www/server/panel/vhost/nginx/netbox_ssl.conf && $NGINX -t && $NGINX -s reload"
