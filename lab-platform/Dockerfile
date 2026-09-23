# 具身智能实验室 · 独立管理平台后端
# 多阶段构建：先装依赖，再复制代码，最终镜像极小
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── 运行时 ──
FROM python:3.12-slim

# 时区 + 基础工具
ENV TZ=Asia/Shanghai \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends tzdata curl && \
    ln -sf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone && \
    rm -rf /var/lib/apt/lists/*

# 从 builder 拿已装依赖
COPY --from=builder /install /usr/local

# 应用代码
WORKDIR /app
COPY . /app/

# 媒体目录挂载点
RUN mkdir -p /app/media/checkins /app/media/tasks

EXPOSE 8001

# 生产入口：gunicorn 2 worker（2GB 机器 1 worker 足够，留余给 Postgres/Redis）
# 注意：启动时先 migrate
CMD ["bash", "-c", "python manage.py migrate --run-syncdb --noinput && gunicorn lab_api.wsgi:application --bind 0.0.0.0:8001 --workers 1 --timeout 30 --access-logfile -"]
