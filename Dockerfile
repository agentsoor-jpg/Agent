# Build and production container for Node.js + Python
FROM node:20-slim

# Install Python 3 and build-essential for any native deps
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files first for layer caching
COPY package*.json ./
RUN npm install

# Copy everything else
COPY . .

# Build Vite frontend assets and bundle TS server
RUN npm run build

# Expose server port
EXPOSE 3000

ENV PORT=3000
ENV NODE_ENV=production

# Start Node production server
CMD ["npm", "start"]
