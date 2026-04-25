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
# Decision is delegated to `dataroom_ctl needs-ingest`, which checks BOTH:
#   (a) registry corruption (missing/empty registry, registry-vs-chunks
#       mismatch) — replaces the old inline registry/chunks count heuristic
#   (b) source files newer than ingest_log.jsonl mtime — catches the
#       session-37 footgun where sync-data.ps1 dropped new source files
#       on prod but the alignment check was satisfied (e.g. 271==271)
#       and deploy silently skipped ingest, leaving the new files
#       un-chunked and invisible to the dashboard.
#
# Iterates `data/*/dataroom/` (any company with a dataroom directory),
# delegates to needs-ingest per company, ingests when exit 0.
echo "Checking dataroom indexes..."
for dr_dir in data/*/dataroom/; do
    if [ -d "$dr_dir" ]; then
        company=$(basename "$(dirname "$dr_dir")")

        # `needs-ingest` exits 0 if ingest needed, 1 if clean. Discard JSON
        # on stdout but let the human-readable per-company summary on stderr
        # surface in deploy logs (code-review flag — `2>&1 >/dev/null` here
        # silenced both streams, hiding the reason for ingest decisions).
        if docker compose exec -T backend \
            python scripts/dataroom_ctl.py needs-ingest --company "$company" >/dev/null; then
            echo "  $company: ingest needed — running dataroom_ctl ingest..."
            if docker compose exec -T backend \
                python scripts/dataroom_ctl.py ingest --company "$company"; then
                # Generic post-ingest hook. Companies can register a per-company
                # bash script at `data/{co}/dataroom/.post-ingest.sh` that runs
                # AFTER `dataroom_ctl ingest` lands successfully. Failures are
                # logged but do NOT fail the deploy — the hook is fire-and-forget
                # at this layer. Skipped when ingest itself failed AND when
                # needs-ingest reports clean (no new data → no work to do).
                #
                # The hook runs ON THE HOST (not inside the container) and is
                # responsible for using `docker compose exec -T backend ...`
                # itself when it needs to invoke Python in the backend
                # container. Invoked via `bash "$hook"` (not `./$hook`) so the
                # executable bit isn't required — Windows clones don't
                # reliably preserve it.
                hook="data/${company}/dataroom/.post-ingest.sh"
                if [ -f "$hook" ]; then
                    echo "  $company: running post-ingest hook ($hook)..."
                    bash "$hook" || echo "    Hook failed (exit=$?)"
                fi
            else
                echo "    Failed (exit=$?)"
            fi
        else
            echo "  $company: clean — skipping ingest"
        fi
    fi
done

# Verify
echo ""
echo "=== Deploy complete ==="
docker compose ps
echo ""
echo "Site should be live at https://laithanalytics.ai"
