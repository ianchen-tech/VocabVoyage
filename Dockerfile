# 使用官方Python 3.11映像作為基礎
FROM python:3.11-slim

# 設置工作目錄
WORKDIR /app

# 安裝Poetry
RUN pip install poetry

# 複製pyproject.toml和poetry.lock文件（如果存在）
COPY pyproject.toml poetry.lock* ./

# 安裝項目依賴
RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi

# 複製項目文件
COPY . .

# 設置環境變量
ENV PORT 8080

# 運行應用
CMD streamlit run --server.port $PORT app.py