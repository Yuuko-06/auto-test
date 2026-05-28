FROM python:3.13-slim

WORKDIR /app

# 安装依赖
COPY shared/ /app/shared/
COPY task-scheduler/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制服务代码
COPY task-scheduler/ .

ENV PYTHONPATH=/app:/app/shared

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
