ARG NODE_VERSION=22
ARG NPM_REGISTRY=https://mirrors.cloud.tencent.com/npm/

FROM node:${NODE_VERSION}-alpine AS builder

ARG NPM_REGISTRY

WORKDIR /app

COPY package*.json ./

RUN npm ci --registry="${NPM_REGISTRY}" --no-audit --fund=false

COPY . .

RUN npm run build

FROM nginxinc/nginx-unprivileged:stable-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
