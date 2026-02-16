FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apk add --no-cache iputils

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN addgroup -S appgroup && adduser -S appuser -G appgroup
RUN mkdir -p /data && chown -R appuser:appgroup /data /app

USER appuser

EXPOSE 7070

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-7070}"]
