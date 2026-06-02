FROM python:3.13-slim

WORKDIR /app

COPY shared/ /app/shared/
COPY api-scanner/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制服务代码（保持包目录结构，解决相对导入问题）
COPY api-scanner/ /app/api_scanner/

ENV PYTHONPATH=/app:/app/shared

EXPOSE 8081
CMD ["python", "-m", "api_scanner.main"]
