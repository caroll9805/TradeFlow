# --- build: installs npm dependencies, type-checks (tsc) and builds the SPA (vite)
FROM node:22-alpine AS build
ARG NPM_REGISTRY=https://registry.npmjs.org/
WORKDIR /app
ENV npm_config_registry=${NPM_REGISTRY} npm_config_fetch_retries=10 npm_config_fetch_retry_mintimeout=20000 \
    npm_config_fetch_retry_maxtimeout=180000 npm_config_fetch_timeout=900000 npm_config_audit=false \
    npm_config_fund=false npm_config_update_notifier=false npm_config_maxsockets=4
COPY package.json package-lock.json* ./
# The cache mount keeps downloaded tarballs if a slow connection interrupts the install; retries resume from it.
RUN --mount=type=cache,target=/root/.npm \
    for i in 1 2 3; do \
      if [ -f package-lock.json ]; then npm ci --prefer-offline && break; else npm install --prefer-offline && break; fi; \
      echo "npm install failed (attempt $i), retrying in 15s"; sleep 15; \
    done && test -d node_modules/vite && echo "frontend dependencies OK"
COPY . .
RUN npm run build

# --- serve (static files + reverse proxy to the API)
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
