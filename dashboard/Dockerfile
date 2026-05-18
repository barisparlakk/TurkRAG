FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

# Bake the API URL at build time
ARG VITE_API_URL=http://localhost:8001
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# Serve static build with a lightweight HTTP server
FROM node:20-alpine
WORKDIR /app
RUN npm install -g serve

COPY --from=builder /app/dist ./dist

EXPOSE 5173
CMD ["serve", "-s", "dist", "-l", "5173"]
