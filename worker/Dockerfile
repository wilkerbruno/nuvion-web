FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libssl-dev xvfb chromium chromium-driver \
    fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libcups2 libdbus-1-3 libgdk-pixbuf-xlib-2.0-0 libnspr4 libnss3 \
    libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 xdg-utils && \
    rm -rf /var/lib/apt/lists/*

# Instalar dependências do worker
COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código do projeto desktop (crud, database, core, utils)
# necessário para o worker acessar o banco e abrir Chrome
COPY crud/ ./crud/
COPY database/ ./database/
COPY core/ ./core/
COPY utils/ ./utils/
COPY config/ ./config/

# Copiar arquivos do worker por último
COPY worker/ .

ENV DESKTOP_PROJECT_PATH=/app
ENV PYTHONPATH=/app

CMD ["sh", "-c", "\
    Xvfb :99 -screen 0 1920x1080x24 -ac & \
    sleep 1 && \
    export DISPLAY=:99 && \
    uvicorn main:app --host 0.0.0.0 --port 8001 --workers 1 \
"]

EXPOSE 8001
