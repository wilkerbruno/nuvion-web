#!/bin/bash
# deploy/setup_vps.sh
# Deploy completo do Nuvion Web no VPS Linux (Ubuntu 22.04+)
# Uso: bash setup_vps.sh

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[!!]${NC} $1"; }
err()  { echo -e "${RED}[ERRO]${NC} $1"; exit 1; }

# ── Configurações — EDITE ANTES DE EXECUTAR ───────────────────────────────────
DOMAIN="app.nuvionbrowser.com"          # Domínio do frontend (com SSL)
API_DOMAIN="api.nuvionbrowser.com"      # Domínio da API
DESKTOP_PATH="/opt/nuvion-desktop"      # Onde está o projeto desktop (com o código Python)
WEB_PATH="/opt/nuvion-web"             # Onde será instalado o projeto web
SECRET_KEY="$(openssl rand -hex 32)"    # Gerado automaticamente
FRONTEND_URL="https://${DOMAIN}"

echo ""
echo "=================================================="
echo "  Nuvion Browser — Deploy VPS"
echo "  Domínio frontend: $DOMAIN"
echo "  Domínio API:      $API_DOMAIN"
echo "  Projeto desktop:  $DESKTOP_PATH"
echo "=================================================="
echo ""

# ── 1. Dependências do sistema ────────────────────────────────────────────────
log "Instalando dependências do sistema..."
apt-get update -qq
apt-get install -y -qq \
    python3 python3-pip python3-venv \
    nodejs npm \
    redis-server \
    nginx certbot python3-certbot-nginx \
    git curl wget \
    chromium-browser chromium-chromedriver \
    xvfb \
    build-essential

# Ativar Redis
systemctl enable redis-server
systemctl start redis-server
log "Redis iniciado"

# ── 2. Clonar / atualizar projeto web ─────────────────────────────────────────
log "Preparando diretório do projeto web..."
mkdir -p "$WEB_PATH"
cp -r ./backend "$WEB_PATH/backend" 2>/dev/null || true
cp -r ./frontend "$WEB_PATH/frontend" 2>/dev/null || true
cp -r ./deploy "$WEB_PATH/deploy" 2>/dev/null || true

# ── 3. Backend Python ─────────────────────────────────────────────────────────
log "Configurando backend Python..."
cd "$WEB_PATH/backend"

python3 -m venv .venv
source .venv/bin/activate

pip install -q --upgrade pip
pip install -q -r requirements.txt

# Instalar dependências do projeto desktop (compartilhadas)
if [ -f "$DESKTOP_PATH/requirements.txt" ]; then
    pip install -q -r "$DESKTOP_PATH/requirements.txt" 2>/dev/null || true
fi

# Arquivo .env
cat > .env << EOF
DEBUG=false
SECRET_KEY=${SECRET_KEY}
DESKTOP_PROJECT_PATH=${DESKTOP_PATH}
FRONTEND_URL=${FRONTEND_URL}
REDIS_URL=redis://localhost:6379/0
DB_HOST=2.25.131.174
DB_PORT=33060
DB_NAME=browser
DB_USER=admin
DB_PASSWORD=V71C2Fd1eqJ8p0Pn0x4aO5mW
CORS_ORIGINS=["${FRONTEND_URL}","http://localhost:5173"]
EOF

log "Backend configurado"

# ── 4. Frontend React ─────────────────────────────────────────────────────────
log "Construindo frontend React..."
cd "$WEB_PATH/frontend"

# .env.production
cat > .env.production << EOF
VITE_API_URL=https://${API_DOMAIN}/api
VITE_WS_URL=wss://${API_DOMAIN}
EOF

npm install --silent
npm run build

log "Frontend construído em dist/"

# ── 5. Systemd — API FastAPI ──────────────────────────────────────────────────
log "Criando serviço systemd para a API..."
cat > /etc/systemd/system/nuvion-api.service << EOF
[Unit]
Description=Nuvion Browser API (FastAPI)
After=network.target redis.service
Wants=redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=${WEB_PATH}/backend
Environment=PYTHONPATH=${DESKTOP_PATH}
EnvironmentFile=${WEB_PATH}/backend/.env
ExecStart=${WEB_PATH}/backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# ── 6. Systemd — Celery Worker ────────────────────────────────────────────────
log "Criando serviço systemd para o worker Celery..."
cat > /etc/systemd/system/nuvion-worker.service << EOF
[Unit]
Description=Nuvion Browser Chrome Worker (Celery)
After=network.target redis.service nuvion-api.service
Wants=redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=${WEB_PATH}/backend
Environment=PYTHONPATH=${DESKTOP_PATH}
Environment=DISPLAY=:99
EnvironmentFile=${WEB_PATH}/backend/.env
ExecStartPre=/usr/bin/Xvfb :99 -screen 0 1920x1080x24 &
ExecStart=${WEB_PATH}/backend/.venv/bin/celery -A workers.chrome_worker worker --concurrency=4 --loglevel=warning
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Xvfb para Chrome headless no VPS (sem display físico)
cat > /etc/systemd/system/xvfb.service << EOF
[Unit]
Description=Xvfb Virtual Display
Before=nuvion-worker.service

[Service]
ExecStart=/usr/bin/Xvfb :99 -screen 0 1920x1080x24
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# ── 7. Nginx ──────────────────────────────────────────────────────────────────
log "Configurando Nginx..."

cat > /etc/nginx/sites-available/nuvion-api << EOF
server {
    listen 80;
    server_name ${API_DOMAIN};

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade \$http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 120;
        client_max_body_size 10m;
    }
}
EOF

cat > /etc/nginx/sites-available/nuvion-frontend << EOF
server {
    listen 80;
    server_name ${DOMAIN};
    root ${WEB_PATH}/frontend/dist;
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location ~* \.(js|css|png|jpg|ico|svg|woff2?)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    gzip on;
    gzip_types text/plain text/css application/javascript application/json;
}
EOF

ln -sf /etc/nginx/sites-available/nuvion-api      /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/nuvion-frontend  /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

nginx -t && systemctl reload nginx
log "Nginx configurado"

# ── 8. SSL com Let's Encrypt ──────────────────────────────────────────────────
log "Gerando certificados SSL..."
certbot --nginx \
    -d "$DOMAIN" \
    -d "$API_DOMAIN" \
    --non-interactive \
    --agree-tos \
    --email admin@${DOMAIN} \
    --redirect 2>/dev/null || warn "SSL falhou — configure manualmente com: certbot --nginx -d $DOMAIN -d $API_DOMAIN"

# ── 9. Iniciar serviços ───────────────────────────────────────────────────────
log "Iniciando serviços..."
systemctl daemon-reload
systemctl enable  xvfb nuvion-api nuvion-worker
systemctl restart xvfb nuvion-api nuvion-worker nginx

sleep 3

# Verificar
if systemctl is-active --quiet nuvion-api; then
    log "API rodando"
else
    warn "API não iniciou — verifique: journalctl -u nuvion-api -n 50"
fi

if systemctl is-active --quiet nuvion-worker; then
    log "Worker rodando"
else
    warn "Worker não iniciou — verifique: journalctl -u nuvion-worker -n 50"
fi

# ── Resumo final ──────────────────────────────────────────────────────────────
echo ""
echo "=================================================="
echo -e "${GREEN}  Deploy concluído!${NC}"
echo ""
echo "  Frontend:  https://${DOMAIN}"
echo "  API docs:  (desabilitado em produção)"
echo "  API health: https://${API_DOMAIN}/api/health"
echo ""
echo "  Comandos úteis:"
echo "  systemctl status nuvion-api"
echo "  systemctl status nuvion-worker"
echo "  journalctl -u nuvion-api -f"
echo "  journalctl -u nuvion-worker -f"
echo ""
echo "  SECRET_KEY gerada: ${SECRET_KEY}"
echo "  (salva em ${WEB_PATH}/backend/.env)"
echo "=================================================="
