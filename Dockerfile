FROM python:3.12-slim AS frontend-builder

# Node 阶段:构建前端
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && rm -rf /var/lib/apt/lists/*

WORKDIR /app/frontend
COPY src/frontend/package.json src/frontend/package-lock.json* ./
RUN npm ci || npm install
COPY src/frontend/ .
RUN npm run build


FROM python:3.12-slim AS runtime

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 依赖(单独 layer 缓存)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 后端代码
COPY src/backend ./src/backend
# 前端构建产物
COPY --from=frontend-builder /app/frontend/dist ./src/frontend/dist
# .env.example 留作模板
COPY .env.example ./.env.example

# 数据目录(运行时挂卷)
RUN mkdir -p data/textbooks data/parsed data/graphs data/integrated data/chroma data/sessions

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8000

EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "src.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
