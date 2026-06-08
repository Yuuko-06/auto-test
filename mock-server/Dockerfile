FROM python:3.13-slim
WORKDIR /app
RUN pip install fastapi uvicorn
COPY mock-server/main.py /app/main.py
EXPOSE 8084
CMD ["python", "main.py"]
