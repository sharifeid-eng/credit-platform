#!/bin/bash
# Laith Production Deploy Script
# Run on the Hetzner VPS: ./deploy.sh
set -e

echo "=== Laith Deploy ==="

# Pull latest code
echo "Pulling latest code..."
git pull origin main

# Build and restart containers
echo "Building containers..."
docker compose build

echo "Starting services..."
docker compose up -d

# Run database migrations
echo "Running migrations..."
docker compose exec backend alembic upgrade head

# Verify
echo ""
echo "=== Deploy complete ==="
docker compose ps
echo ""
echo "Site should be live at https://laithanalytics.ai"
