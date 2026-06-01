#!/bin/bash
# deploy/update.sh — Atualizar app sem refazer setup completo
set -e
WEB_PATH="/opt/nuvion-web"
DESKTOP_PATH="/opt/nuvion-desktop"

echo "[1/4] Copiando arquivos..."
cp -r ./backend "$WEB_PATH/" 2>/dev/null || true
cp -r ./frontend "$WEB_PATH/" 2>/dev/null || true

echo "[2/4] Atualizando dependências do backend..."
cd "$WEB_PATH/backend"
source .venv/bin/activate
pip install -q -r requirements.txt

echo "[3/4] Rebuilding frontend..."
cd "$WEB_PATH/frontend"
npm install --silent
npm run build

echo "[4/4] Reiniciando serviços..."
systemctl restart nuvion-api nuvion-worker
sleep 2
systemctl is-active nuvion-api && echo "API OK" || echo "API com problema"
systemctl is-active nuvion-worker && echo "Worker OK" || echo "Worker com problema"
echo "Atualização concluída!"
