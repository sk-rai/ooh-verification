# TrustCapture Web Frontend - Build & Serve
FROM node:18-alpine AS build

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* yarn.lock* ./
RUN npm install

# Copy source and build
COPY . .

# Build arg for API URL (set at build time)
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# Serve with lightweight nginx
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html

# SPA routing: redirect all paths to index.html
RUN echo 'server { \
    listen 80; \
    location / { \
        root /usr/share/nginx/html; \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
