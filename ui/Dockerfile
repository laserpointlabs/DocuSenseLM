# syntax=docker/dockerfile:1.4
FROM node:20-alpine

WORKDIR /app

# Install dependencies first (better caching)
COPY package.json package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm/_cacache \
    npm ci --only=production=false || npm install

# Copy application code (excludes node_modules via .dockerignore)
COPY . .

ENV NEXT_TELEMETRY_DISABLED 1
ENV NEXT_PUBLIC_API_URL=http://localhost:8000

EXPOSE 3000

CMD ["npm", "run", "dev"]
