FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json ./
RUN npm install --silent
COPY . .
ARG VITE_API_URL=https://api.seudominio.com/api
ARG VITE_WS_URL=wss://api.seudominio.com
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
RUN printf 'server{\nlisten 80;\nroot /usr/share/nginx/html;\nindex index.html;\nlocation / { try_files $uri $uri/ /index.html; }\nlocation ~* \\.(js|css|png|jpg|ico|svg|woff2?)$ { expires 1y; add_header Cache-Control "public, immutable"; }\ngzip on;\ngzip_types text/plain text/css application/javascript application/json image/svg+xml;\n}' > /etc/nginx/conf.d/default.conf
EXPOSE 80
