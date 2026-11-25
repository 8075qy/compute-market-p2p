FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖声明与包源码（editable 安装需要 app/ 包与 README.md）
COPY pyproject.toml README.md ./
COPY app/ app/

# 安装 Python 依赖
RUN pip install --no-cache-dir -e ".[dev]"

# 复制其余代码（迁移、测试等）
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]