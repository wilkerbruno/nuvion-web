# Build multi-stage do painel (Next.js) — pensado para deploy no EasyPanel
# (ver ../docs/DEPLOY_EASYPANEL.md).
#
# Contexto de build = raiz do repositório inteiro (o EasyPanel, num
# monorepo, aponta o Dockerfile pra `frontend/Dockerfile` mas passa o
# CONTEXTO como a raiz do repo, não a subpasta — confirmado por um build
# real). Por isso todo COPY abaixo é relativo à raiz do repo
# (`frontend/...`), não à pasta onde este arquivo está.
#
# IMPORTANTE: NEXT_PUBLIC_API_URL é embutida no bundle JavaScript em tempo
# de BUILD (Next.js troca process.env.NEXT_PUBLIC_* pelo valor literal
# durante `next build`) — não é lida em tempo de execução como as outras
# variáveis de ambiente deste projeto. Por isso ela entra aqui como build
# arg, não só como variável de ambiente do container em runtime. Se você
# mudar a URL do backend depois, precisa reconstruir a imagem (novo deploy
# no EasyPanel), não só reiniciar o container.

FROM node:20-slim AS deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ .

ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
