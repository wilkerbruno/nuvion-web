ARG BUILD_TARGET=api

# ── API ───────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS api
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libssl-dev curl && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
ARG CACHEBUST=2
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# ── Worker ────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS worker
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libssl-dev xvfb chromium chromium-driver \
    fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libcups2 libdbus-1-3 libgdk-pixbuf2.0-0 libnspr4 libnss3 \
    libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 xdg-utils && \
    rm -rf /var/lib/apt/lists/*
COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY worker/ .
CMD ["sh", "-c", "Xvfb :99 -screen 0 1920x1080x24 & sleep 1 && DISPLAY=:99 celery -A workers.chrome_worker worker --concurrency=2 --loglevel=warning"]

# ── Frontend ──────────────────────────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package.json ./
RUN npm install --silent
COPY frontend/ .
ARG VITE_API_URL=https://divisions-nuvion-web-api.lcgx8u.easypanel.host/api
ARG VITE_WS_URL=wss://divisions-nuvion-web-api.lcgx8u.easypanel.host
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL
RUN npm run build

FROM nginx:alpine AS frontend
COPY --from=frontend-builder /app/dist /usr/share/nginx/html
RUN printf 'server{\nlisten 80;\nroot /usr/share/nginx/html;\nindex index.html;\nlocation / { try_files $uri $uri/ /index.html; }\nlocation ~* \\.(js|css|png|jpg|ico|svg|woff2?)$ { expires 1y; add_header Cache-Control "public,immutable"; }\ngzip on;\ngzip_types text/plain text/css application/javascript application/json;\n}' > /etc/nginx/conf.d/default.conf
EXPOSE 80

# ── Target final ──────────────────────────────────────────────────────────────
FROM ${BUILD_TARGET}