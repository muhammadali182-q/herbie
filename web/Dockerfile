FROM node:22.21-alpine@sha256:0340fa682d72068edf603c305bfbc10e23219fb0e40df58d9ea4d6f33a9798bf AS build

WORKDIR /app

COPY package.json package-lock.json ./
COPY web/package.json ./web/package.json
RUN npm ci --workspace @herbie/web

COPY web ./web
RUN npm run build:web

FROM nginx:1.29.2-alpine@sha256:61e01287e546aac28a3f56839c136b31f590273f3b41187a36f46f6a03bbfe22 AS runtime

COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/web/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["wget", "--quiet", "--tries=1", "--spider", "http://127.0.0.1/"]
