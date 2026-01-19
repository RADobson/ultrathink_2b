FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

RUN mkdir -p /vault && useradd -m ultrathink && chown -R ultrathink:ultrathink /vault

USER ultrathink

CMD ["python", "-u", "-m", "app.main"]
