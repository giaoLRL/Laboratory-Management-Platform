# 多阶段 Dockerfile：builder 装依赖 → runtime 仅拷贝
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install \
      -i https://mirrors.aliyun.com/pypi/simple/ \
      -r requirements.txt

FROM python:3.12-slim
ENV TZ=Asia/Shanghai \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 从 builder 拷贝 pip 包
COPY --from=builder /install /usr/local

# 设置时区 + 创建媒体目录
RUN ln -sf /usr/share/zoneinfo/$TZ /etc/localtime \
 && echo $TZ > /etc/timezone \
 && mkdir -p /app/media

WORKDIR /app
COPY . .

EXPOSE 8001

# 启动：migrate 后 gunicorn 起 1 worker（2GB 机器）
CMD python manage.py migrate --noinput && \
    gunicorn lab_api.wsgi:application \
      --bind 0.0.0.0:8001 \
      --workers 1 \
      --threads 4 \
      --timeout 120 \
      --access-logfile - \
      --error-logfile -
