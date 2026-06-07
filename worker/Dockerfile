FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libssl-dev \
    xvfb x11vnc novnc websockify \
    chromium chromium-driver \
    fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libcups2 libdbus-1-3 libgdk-pixbuf-xlib-2.0-0 libnspr4 libnss3 \
    libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 xdg-utils \
    && rm -rf /var/lib/apt/lists/*

COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código do backend necessário para o worker
COPY backend/crud/ ./crud/
COPY backend/database/ ./database/
COPY backend/core/ ./core/
COPY backend/utils/ ./utils/
COPY backend/workers/ ./workers/

# Arquivos do worker
COPY worker/ .

ENV DESKTOP_PROJECT_PATH=/app
ENV PYTHONPATH=/app
ENV DISPLAY=:99
ENV VNC_PORT=5900
ENV NOVNC_PORT=6080

# Inicia Xvfb + x11vnc + noVNC websockify + uvicorn
CMD ["sh", "-c", "\
    Xvfb :99 -screen 0 1920x1080x24 -ac & \
    sleep 1 && \
    x11vnc -display :99 -nopw -listen localhost -xkb -forever -shared & \
    websockify --web /usr/share/novnc 6080 localhost:5900 & \
    sleep 1 && \
    uvicorn main:app --host 0.0.0.0 --port 8001 --workers 1 \
"]

EXPOSE 8001 6080
