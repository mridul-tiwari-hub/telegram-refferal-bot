#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "Telegram Referral Growth & Group Management Bot Deployment"
echo "=========================================================="

# Check for Docker and Docker Compose
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
fi

if ! command -v docker compose &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo "Installing docker-compose plugin..."
    apt-get update && apt-get install -y docker-compose-plugin
fi

# Ensure .env exists
if [ ! -f .env ]; then
    echo "Copying .env.example to .env..."
    cp .env.example .env
    echo "IMPORTANT: Please edit .env with your BOT_TOKEN before running in production."
fi

# Create persistent storage directories
mkdir -p data logs /var/lib/telegram-bot/postgres /var/lib/telegram-bot/redis

echo "Building and launching containers via Docker Compose..."
docker compose -f docker-compose.yml up -d --build

echo "Checking container status..."
docker compose ps

echo ""
echo "=========================================================="
echo "Deployment completed successfully!"
echo "Your bot is configured with 'restart: unless-stopped' and"
echo "will continue running 24/7 independently of this session."
echo "View logs with: docker compose logs -f bot"
echo "=========================================================="
