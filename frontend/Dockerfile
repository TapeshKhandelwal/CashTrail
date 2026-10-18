# CashTrail web app: Next.js production server (`next start`).
#   docker build -t cashtrail-frontend --build-arg NEXT_PUBLIC_API_URL=... .
# NEXT_PUBLIC_* values are compiled into the bundle, so they are build arguments.
# API_URL (the Django API as seen from this container) is read at runtime.

FROM node:24-alpine AS base
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app

# --- Dependencies ---------------------------------------------------------------------
FROM base AS deps
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# --- Build ----------------------------------------------------------------------------
FROM base AS builder
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api
ARG NEXT_PUBLIC_APP_URL=http://localhost:3000
ARG NEXT_PUBLIC_APP_VERSION=docker
ARG NEXT_PUBLIC_DEMO_MODE=true
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
    NEXT_PUBLIC_APP_URL=${NEXT_PUBLIC_APP_URL} \
    NEXT_PUBLIC_APP_VERSION=${NEXT_PUBLIC_APP_VERSION} \
    NEXT_PUBLIC_DEMO_MODE=${NEXT_PUBLIC_DEMO_MODE}
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# --- Runtime --------------------------------------------------------------------------
FROM base AS runner
ENV NODE_ENV=production \
    API_URL=http://backend:8000/api

# The whole build, not a standalone trace: the service worker route (/serwist/sw.js)
# bundles src/app/sw.ts with esbuild at request time, so it needs the sources and the full
# node_modules. Owned by the image's non-root "node" user so Next can write its cache.
COPY --from=builder --chown=node:node /app ./

USER node

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:3000/').then(r => process.exit(r.ok ? 0 : 1), () => process.exit(1))"]

CMD ["node_modules/.bin/next", "start", "-H", "0.0.0.0", "-p", "3000"]
