FROM python:3.13-slim

WORKDIR /app

COPY shared/ /app/shared/
COPY api-scanner/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api-scanner/ .

ENV PYTHONPATH=/app:/app/shared

EXPOSE 8081
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081"]
