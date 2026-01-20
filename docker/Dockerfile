FROM python:3.10-slim

WORKDIR /app
COPY server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY server /app/server
WORKDIR /app/server

CMD ["python", "server.py"]
