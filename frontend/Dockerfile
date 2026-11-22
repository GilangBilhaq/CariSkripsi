# Tampilan web CariSkripsi (Next.js) untuk VPS. Dijalankan lewat deploy/docker-compose.yml.
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Folder public bisa kosong (dan tidak ikut terkirim); pastikan ada untuk tahap COPY di bawah.
RUN mkdir -p public
# Rewrite /api/* di next.config dibaca saat build; di VPS Caddy sudah meneruskan /api/* langsung ke backend,
# jadi ini hanya cadangan.
ARG BACKEND_URL=http://backend:8080
ENV BACKEND_URL=$BACKEND_URL NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
