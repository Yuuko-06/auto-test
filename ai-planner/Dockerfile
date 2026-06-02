FROM python:3.13-slim

WORKDIR /app

COPY shared/ /app/shared/
COPY ai-planner/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制服务代码（保持包目录结构，解决相对导入问题）
COPY ai-planner/ /app/ai_planner/

ENV PYTHONPATH=/app:/app/shared

EXPOSE 8082
CMD ["python", "-m", "ai_planner.main"]
