FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libssl-dev xvfb chromium chromium-driver \
    fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libcups2 libdbus-1-3 libgdk-pixbuf-xlib-2.0-0 libnspr4 libnss3 \
    libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 xdg-utils && \
    rm -rf /var/lib/apt/lists/*

# Copiar requirements da pasta worker/
COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo o conteúdo da pasta worker/
COPY worker/ .

CMD ["sh", "-c", "\
    Xvfb :99 -screen 0 1920x1080x24 -ac & \
    sleep 1 && \
    export DISPLAY=:99 && \
    uvicorn main:app --host 0.0.0.0 --port 8001 --workers 1 & \
    celery -A workers.chrome_worker worker --concurrency=2 --loglevel=warning \
"]

EXPOSE 8001
