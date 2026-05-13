# ---- Stage 1: build dependencies ----
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: runtime image ----
FROM python:3.12-slim
LABEL maintainer="helep-team"
LABEL service="notification-service"

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SERVICE_PORT=8004

COPY --from=builder /install /usr/local
COPY app ./app

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

EXPOSE 8004
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8004/healthz')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004", "--log-level", "info"]
