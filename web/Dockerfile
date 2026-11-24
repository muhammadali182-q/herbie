FROM node:22.21-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
COPY web/package.json ./web/package.json
RUN npm ci --workspace @herbie/web

COPY web ./web
RUN npm run build:web

FROM nginx:1.29.2-alpine AS runtime

COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/web/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["wget", "--quiet", "--tries=1", "--spider", "http://127.0.0.1/"]
