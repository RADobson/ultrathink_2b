FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ultrathink.py .

RUN mkdir -p /vault && useradd -m ultrathink && chown -R ultrathink:ultrathink /vault

USER ultrathink

CMD ["python", "-u", "ultrathink.py"]
