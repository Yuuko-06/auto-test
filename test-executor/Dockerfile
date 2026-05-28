FROM python:3.13-slim

WORKDIR /app

COPY shared/ /app/shared/
COPY test-executor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY test-executor/ .

ENV PYTHONPATH=/app:/app/shared

EXPOSE 8083
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8083"]
