# ===== Stage 1: builder (Wolfi/Chainguard, musl) =====
FROM cgr.dev/chainguard/python:latest-dev AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# deps first (cache-friendly)
COPY requirements.txt .

# Install dependencies into an app-local path
RUN mkdir -p /app/site-packages && \
    python -m pip install --upgrade pip && \
    pip install --no-cache-dir --target /app/site-packages -r requirements.txt

# app code
COPY main.py /app/main.py

# ===== Stage 2: DEBUG runtime (with shell/tools) =====
FROM cgr.dev/chainguard/python:latest-dev AS debug

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/site-packages \
    PORT=8080

WORKDIR /app
# Optional: enable if you want extra tools inside the container
# RUN apk add --no-cache curl bind-tools iproute2 iputils busybox-extras procps

COPY --from=builder /app/site-packages /app/site-packages
COPY --from=builder /app/main.py       /app/main.py

USER nonroot
EXPOSE 8080
ENTRYPOINT ["python","-m","uvicorn","main:app","--host","0.0.0.0","--port","8080"]

# ===== Stage 3: PROD runtime (Wolfi/Chainguard, small & non-root) =====
FROM cgr.dev/chainguard/python:latest AS prod

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/site-packages \
    PORT=8080

WORKDIR /app
USER nonroot

COPY --from=builder /app/site-packages /app/site-packages
COPY --from=builder /app/main.py       /app/main.py

EXPOSE 8080
ENTRYPOINT ["python","-m","uvicorn","main:app","--host","0.0.0.0","--port","8080"]