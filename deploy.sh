#!/bin/bash
# Laith Production Deploy Script
# Run on the Hetzner VPS: ./deploy.sh
set -e

echo "=== Laith Deploy ==="

# Pull latest code — record what changed
echo "Pulling latest code..."
BEFORE=$(git rev-parse HEAD)
git pull origin main
AFTER=$(git rev-parse HEAD)

# Build containers — force rebuild backend if code changed
echo "Building containers..."
if git diff --name-only "$BEFORE" "$AFTER" | grep -qE '^(core/|backend/)'; then
    echo "  Backend code changed — rebuilding without cache..."
    docker compose build --no-cache backend
    docker compose build frontend
else
    docker compose build
fi

echo "Starting services..."
docker compose up -d

# Run database migrations
echo "Running migrations..."
docker compose exec backend alembic upgrade head

# Rebuild dataroom search indexes if needed (bypasses HTTP auth by calling Python directly)
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
from core.dataroom.engine import DataRoomEngine
engine = DataRoomEngine()
result = engine.ingest('$company', '$product', 'data/$company/dataroom')
print(f\"    Done: {result.get('total_files', '?')} files, {result.get('ingested', '?')} new, {result.get('skipped', '?')} skipped\")
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
