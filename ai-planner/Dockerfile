FROM python:3.13-slim

WORKDIR /app

COPY shared/ /app/shared/
COPY ai-planner/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ai-planner/ .

ENV PYTHONPATH=/app:/app/shared

EXPOSE 8082
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8082"]
