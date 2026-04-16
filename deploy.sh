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

# Wait for backend to be ready
echo "Waiting for backend..."
for i in $(seq 1 30); do
    if docker compose exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/companies')" > /dev/null 2>&1; then
        echo "  Backend ready"
        break
    fi
    echo "  Attempt $i/30..."
    sleep 2
done

# Rebuild dataroom search indexes if needed
echo "Checking dataroom indexes..."
for registry in data/*/dataroom/registry.json; do
    if [ -f "$registry" ]; then
        company_dir=$(dirname $(dirname "$registry"))
        company=$(basename "$company_dir")
        chunks_dir="$(dirname "$registry")/chunks"
        if [ ! -d "$chunks_dir" ] || [ -z "$(ls -A "$chunks_dir" 2>/dev/null)" ]; then
            # Find product from config.json
            for config in data/$company/*/config.json; do
                product=$(basename $(dirname "$config"))
                if [ "$product" != "dataroom" ]; then
                    echo "  Ingesting dataroom for $company/$product..."
                    docker compose exec -T backend python -c "
import urllib.request, json
req = urllib.request.Request('http://localhost:8000/companies/$company/products/$product/dataroom/ingest', method='POST')
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
print(f\"    Done: {data.get('total_files', '?')} files, {data.get('ingested', '?')} ingested, {data.get('skipped', '?')} skipped\")
" 2>&1 || echo "    Failed"
                fi
            done
        else
            echo "  $company: chunks exist, skipping ingest"
        fi
    fi
done

# Verify
echo ""
echo "=== Deploy complete ==="
docker compose ps
echo ""
echo "Site should be live at https://laithanalytics.ai"
