#!/usr/bin/env bash
#
# 实验室管理平台 — 停止脚本
# 停止开发服务器，可选停止 Docker 容器
#
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }

echo ""
echo -e "${RED}╔══════════════════════════════════════════╗${NC}"
echo -e "${RED}║    停止实验室管理平台                    ║${NC}"
echo -e "${RED}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── 1. 杀掉 Django runserver ────────────────────────────
# 查找占用 8000 端口的进程并终止
RUNSERVER_PID=$(netstat -ano 2>/dev/null | grep ":8000" | grep "LISTENING" | awk '{print $NF}' | head -1)

if [ -n "$RUNSERVER_PID" ] && [ "$RUNSERVER_PID" != "0" ]; then
    info "终止 Django runserver (PID: $RUNSERVER_PID)..."
    taskkill -PID "$RUNSERVER_PID" -F 2>/dev/null || true
    ok "runserver 已停止"
else
    info "未检测到 runserver 进程"
fi

# ── 2. 可选：停止 Docker 容器 ────────────────────────────
echo ""
read -p "是否同时停止 PostgreSQL 和 Redis 容器？(y/N): " STOP_DOCKER
if [ "${STOP_DOCKER,,}" = "y" ] || [ "${STOP_DOCKER,,}" = "yes" ]; then
    info "停止 Docker 容器..."
    docker stop netbox-postgres netbox-redis 2>/dev/null || true
    ok "容器已停止"
else
    info "容器保持运行"
fi

echo ""
ok "完成"
