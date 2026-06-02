FROM python:3.13-slim

WORKDIR /app

COPY shared/ /app/shared/
COPY test-executor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制服务代码（保持包目录结构，解决相对导入问题）
COPY test-executor/ /app/test_executor/

ENV PYTHONPATH=/app:/app/shared

EXPOSE 8083
CMD ["python", "-m", "test_executor.main"]
