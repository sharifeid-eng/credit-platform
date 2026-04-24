#!/bin/bash
# Laith Production Deploy Script
# Run on the Hetzner VPS: ./deploy.sh
set -e

echo "=== Laith Deploy ==="

# NOTE: `git stash` was removed here — it was silently discarding any local edits
# on every deploy (e.g. server-side enrichment of registry.json). The server
# should have zero local edits; if `git pull` hits a conflict, we WANT to stop.

# Pull latest code — record what changed
#
# Detect "untracked-file collides with incoming git commit" case (session 35).
# This happens when a file was manually SCP'd to prod and LATER added to git
# from a different machine — git pull refuses to overwrite the untracked file
# even when byte-identical. For each colliding file, verify sha256 match with
# the incoming git blob; if identical, remove the untracked copy so pull can
# land cleanly. If different, stop and let the human investigate.
echo "Pulling latest code..."
BEFORE=$(git rev-parse HEAD)
git fetch origin main
# Files added by the incoming commits that currently exist untracked in the
# working tree
COLLIDING=$(git diff --name-only --diff-filter=A "HEAD..origin/main" 2>/dev/null | while read f; do
    if [ -f "$f" ] && ! git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
        echo "$f"
    fi
done)
if [ -n "$COLLIDING" ]; then
    echo "  Detected untracked files colliding with incoming commits:"
    echo "$COLLIDING" | sed 's/^/    /'
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        local_hash=$(sha256sum "$f" | awk '{print $1}')
        incoming_hash=$(git cat-file -p "origin/main:$f" 2>/dev/null | sha256sum | awk '{print $1}')
        if [ "$local_hash" = "$incoming_hash" ]; then
            echo "  $f — identical sha256 ($local_hash); removing untracked copy"
            rm -f "$f"
        else
            echo "  ⚠️  $f — local ($local_hash) != incoming ($incoming_hash)"
            echo "     MANUAL RESOLUTION REQUIRED: back up the local file, diff vs incoming,"
            echo "     decide which version to keep, then re-run deploy.sh."
            exit 1
        fi
    done <<< "$COLLIDING"
fi
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
