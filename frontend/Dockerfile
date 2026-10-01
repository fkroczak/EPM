# EPM Web: baut das Frontend und liefert es mit Nginx aus.
# Die Nginx-Konfiguration (TLS, API-Weiterleitung, Sicherheitsköpfe) kommt aus /srv/epm/nginx/epm.conf.
#   docker build -t epm-web:0.2.0 frontend
FROM node:22-alpine AS bau
WORKDIR /bau
ENV npm_config_fund=false npm_config_audit=false npm_config_update_notifier=false
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:stable-alpine
COPY --from=bau /bau/dist /srv/web
