#!/bin/bash
# Laith Production Deploy Script
# Run on the Hetzner VPS: ./deploy.sh
set -e

echo "=== Laith Deploy ==="

# NOTE: `git stash` was removed here — it was silently discarding any local edits
# on every deploy (e.g. server-side enrichment of registry.json). The server
# should have zero local edits; if `git pull` hits a conflict, we WANT to stop.

# Pull latest code — record what changed
echo "Pulling latest code..."
BEFORE=$(git rev-parse HEAD)
git pull origin main
AFTER=$(git rev-parse HEAD)

# Build containers — always --no-cache for backend to avoid stale code
# Docker layer cache unreliably invalidates COPY core/ after git pull
echo "Building containers..."
docker compose build --no-cache backend
docker compose build frontend

echo "Starting services..."
docker compose up -d

# Run database migrations
echo "Running migrations..."
docker compose exec backend alembic upgrade head

# Rebuild dataroom search indexes if needed (bypasses HTTP auth by calling Python directly)
#
# Heuristic: compare the registry entry count with the chunk file count. Any
# misalignment (0 chunks, fewer chunks than registry entries, zero registry
# entries with stale chunk files) triggers a full ingest. The OLD heuristic —
# "chunks dir non-empty → skip" — was fooled by single stray chunks from
# previous failed ingests, leaving Klaim/Tamara stuck with 1 chunk each.
echo "Checking dataroom indexes..."
for registry in data/*/dataroom/registry.json; do
    if [ -f "$registry" ]; then
        company_dir=$(dirname $(dirname "$registry"))
        company=$(basename "$company_dir")
        chunks_dir="$(dirname "$registry")/chunks"

        # Count registry entries (docs) and chunk files on disk
        registry_count=$(python3 -c "import json; print(len(json.load(open('$registry'))))" 2>/dev/null || echo "0")
        if [ -d "$chunks_dir" ]; then
            chunk_count=$(ls -1 "$chunks_dir"/*.json 2>/dev/null | wc -l | tr -d ' ')
        else
            chunk_count=0
        fi

        if [ "$registry_count" -gt 0 ] && [ "$registry_count" = "$chunk_count" ]; then
            echo "  $company: registry aligned ($registry_count docs) — skipping ingest"
        else
            echo "  $company: misalignment (registry=$registry_count, chunks=$chunk_count) — ingesting via dataroom_ctl..."
            # Unified CLI (scripts/dataroom_ctl.py) auto-resolves the product,
            # writes a structured manifest entry, and returns a non-zero exit
            # code on failure. Human-readable summary on stderr; JSON on stdout.
            docker compose exec -T backend \
                python scripts/dataroom_ctl.py ingest --company "$company" \
                || echo "    Failed (exit=$?)"
        fi
    fi
done

# Verify
echo ""
echo "=== Deploy complete ==="
docker compose ps
echo ""
echo "Site should be live at https://laithanalytics.ai"
