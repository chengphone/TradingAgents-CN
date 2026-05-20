FROM python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制项目配置
COPY pyproject.toml README.md VERSION ./

# 安装 Python 依赖
RUN pip install --upgrade pip && \
    pip install --prefer-binary . && \
    pip install httpx PyJWT

# 复制应用代码
COPY app ./app
COPY tradingagents ./tradingagents
COPY config ./config

# 创建数据目录
RUN mkdir -p /app/data/progress /app/data/logs

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
