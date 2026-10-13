# Free Schoolrun 后端镜像
# 构建上下文 = backend/（见 docker-compose.yml 的 context: ..）
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 依赖单独一层，改代码不用重装依赖
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY main.py manage.py ./

# 运行期目录（compose 里用卷挂载，保证升级不丢数据）
RUN mkdir -p /app/releases /app/app_logs

EXPOSE 8000

# 生产建议：uvicorn + 代理头（前置 Caddy/Nginx）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
