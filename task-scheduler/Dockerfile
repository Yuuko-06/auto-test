FROM python:3.13-slim

WORKDIR /app

# 安装依赖
COPY shared/ /app/shared/
COPY task-scheduler/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制服务代码（保持包目录结构，解决相对导入问题）
COPY task-scheduler/ /app/task_scheduler/

ENV PYTHONPATH=/app:/app/shared

EXPOSE 8080
CMD ["python", "-m", "task_scheduler.main"]
