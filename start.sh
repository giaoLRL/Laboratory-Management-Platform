#!/usr/bin/env bash
#
# 实验室管理平台 — 一键启动脚本
# 自动处理：Docker 容器检查 → 虚拟环境 → 依赖安装 → 数据库迁移 → 开发服务器
#
set -e

# ── 配置 ───────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/netbox-main"
MANAGE_DIR="$PROJECT_DIR/netbox"          # manage.py 所在目录
VENV_DIR="$PROJECT_DIR/venv"
REQUIREMENTS="$PROJECT_DIR/requirements.txt"

# Docker 容器名（与 configuration.py 中端口对应）
PG_CONTAINER="netbox-postgres"
REDIS_CONTAINER="netbox-redis"

# 颜色输出
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERR]${NC}   $*"; }

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║    实验室管理平台 — 启动中...           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── 1. 检查 Docker 容器 ─────────────────────────────────
info "检查 Docker 容器状态..."

if ! docker info >/dev/null 2>&1; then
    err "Docker 未运行，请先启动 Docker Desktop"
    exit 1
fi

for container in "$PG_CONTAINER" "$REDIS_CONTAINER"; do
    if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
        ok "容器 $container 运行中"
    else
        warn "容器 $container 未运行，正在启动..."
        # 尝试启动已停止的容器，或从 compose 启动
        if docker ps -a --format "{{.Names}}" | grep -q "^${container}$"; then
            docker start "$container" >/dev/null 2>&1
        else
            err "容器 $container 不存在，请检查 Docker Compose 配置"
            exit 1
        fi
        # 等待就绪
        sleep 2
        ok "容器 $container 已启动"
    fi
done

# ── 2. 虚拟环境 ─────────────────────────────────────────
info "检查 Python 虚拟环境..."

if [ ! -f "$VENV_DIR/Scripts/python.exe" ] && [ ! -f "$VENV_DIR/bin/python" ]; then
    warn "虚拟环境不存在，正在创建..."
    python -m venv "$VENV_DIR"
    ok "虚拟环境创建完成: $VENV_DIR"
else
    ok "虚拟环境已存在"
fi

# 激活虚拟环境
if [ -f "$VENV_DIR/Scripts/activate" ]; then
    source "$VENV_DIR/Scripts/activate"
else
    source "$VENV_DIR/bin/activate"
fi
ok "虚拟环境已激活"

# ── 3. 安装依赖 ─────────────────────────────────────────
info "检查 Python 依赖..."
# 通过检查关键包是否已安装来判断是否需要重新安装
if ! python -c "import django" 2>/dev/null; then
    warn "依赖未安装，正在安装 (这可能需要几分钟)..."
    pip install -r "$REQUIREMENTS" --quiet
    ok "依赖安装完成"
else
    ok "依赖已就绪"
fi

# ── 4. 数据库迁移 ────────────────────────────────────────
info "执行数据库迁移..."
cd "$MANAGE_DIR"
python manage.py migrate --noinput 2>&1 | while IFS= read -r line; do
    # 过滤掉 Django 的常规输出噪音
    case "$line" in
        *"OK"*|*"Applying"*|*"Running"*)
            echo "       $line"
            ;;
    esac
done
ok "数据库迁移完成"

# ── 5. 设置 LLM 环境变量 ─────────────────────────────────
export LAB_MANAGER_LANGCHAIN_API_KEY="sk-e734158e9b3f43f89e4c5605912a0d19"
export LAB_MANAGER_LANGCHAIN_BASE_URL="https://api.deepseek.com/v1"
export LAB_MANAGER_LANGCHAIN_MODEL="deepseek-chat"
ok "LLM 环境变量已设置 (DeepSeek)"

# ── 6. 启动开发服务器 ───────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  启动开发服务器                          ║${NC}"
echo -e "${GREEN}║  http://localhost:8000/                  ║${NC}"
echo -e "${GREEN}║  按 Ctrl+C 停止                          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""

python manage.py runserver 0.0.0.0:8000
