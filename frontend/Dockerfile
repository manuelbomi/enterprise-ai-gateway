# ============================================================
# frontend/Dockerfile — Multi-stage build for React frontend
# ============================================================

# ---- Stage 1: Development (used by docker-compose.yml) ----
FROM node:20-alpine AS development
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]


# ---- Stage 2: Builder (creates production static files) ----
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --frozen-lockfile     # ci = clean install, uses lockfile exactly
COPY . .
RUN npm run build                # outputs to /app/dist


# ---- Stage 3: Production (serves static files via nginx) ----
FROM nginx:alpine AS production

# Copy built static files
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom nginx config for SPA routing (all paths → index.html)
COPY nginx-spa.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
