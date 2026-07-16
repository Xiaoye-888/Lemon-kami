# 构建阶段
FROM node:20-alpine AS builder

WORKDIR /app

# 复制依赖文件
COPY package*.json ./

# 安装依赖（直接全局安装 vite，彻底解决权限）
RUN npm install --registry=https://mirrors.cloud.tencent.com/npm/
RUN npm install -g vite --registry=https://mirrors.cloud.tencent.com/npm/

# 复制源代码
COPY . .

# 构建（直接用 vite，不用 npx）
RUN vite build

# 生产阶段
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
