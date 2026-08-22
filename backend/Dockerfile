# Build pensado para o EasyPanel apontando o "Build Path"/caminho do
# Dockerfile para `backend/Dockerfile` num monorepo. Na prática, o
# EasyPanel monta o build com o CONTEXTO sendo a raiz do repositório
# inteiro (confirmado por um build real: `docker buildx build -f
# .../code/backend/Dockerfile .../code/` — o contexto passado é a raiz
# `code/`, não `code/backend/`), mesmo apontando o Dockerfile para dentro
# de `backend/`. Por isso todo COPY abaixo é relativo à raiz do repo
# (`backend/...`), não à pasta onde este arquivo está. Ver
# ../docs/DEPLOY_EASYPANEL.md e o `.dockerignore` na raiz do repo.

FROM python:3.11-slim

WORKDIR /app

# Dependências de sistema para mysqlclient/cryptography/bcrypt
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
