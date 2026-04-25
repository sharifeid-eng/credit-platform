#!/bin/bash
# Post-ingest hook for Tamara — auto-parses new quarterly investor packs.
#
# Trigger: deploy.sh's generic post-ingest hook calls this AFTER
# `dataroom_ctl ingest --company Tamara` lands successfully.
#
# Behavior: locates the newest investor pack file in the management financials
# folder, then runs scripts/ingest_tamara_investor_pack.py inside the backend
# container with --force (regenerates JSON even when a pack with the same
# computed pack_date already exists — covers Tamara revising historicals).
# The parser auto-fires the thesis drift check (default behavior; opt-out is
# the parser's --no-update-thesis flag, which we do NOT pass).
#
# Exit codes: 0 on success OR no-pack-found, non-zero on parse failure.
# deploy.sh treats non-zero as non-fatal — see deploy.sh hook block.
#
# Test hooks (env vars):
#   LAITH_TAMARA_SEARCH_DIR — override default search folder (used by tests
#                             to point at a tmp dir of fake pack files)
#   LAITH_HOOK_DRY_RUN=1    — print what would run, skip docker exec
#                             (used by tests to verify file-finding logic
#                             without touching docker)
set -e

SEARCH_DIR="${LAITH_TAMARA_SEARCH_DIR:-data/Tamara/dataroom/Financials/54.2.2 Management Financials}"

if [ ! -d "$SEARCH_DIR" ]; then
    echo "    Tamara hook: search dir not present ($SEARCH_DIR) — skipping"
    exit 0
fi

# Find newest investor pack file by mtime. Pattern covers both the quarterly
# cadence ("1Q2026 Tamara Cons. Investor Pack.xlsx") and the older monthly
# cadence ("Investor Monthly Reporting_Nov'25.xlsx"). Uses GNU find's -printf
# (available on the Hetzner Linux deploy target + Git Bash for local testing).
LATEST=$(find "$SEARCH_DIR" -maxdepth 1 -type f \
    \( -iname "*Investor*Pack*.xlsx" -o -iname "*Investor*Reporting*.xlsx" \) \
    -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)

if [ -z "$LATEST" ]; then
    echo "    Tamara hook: no investor packs found in $SEARCH_DIR — skipping"
    exit 0
fi

echo "    Tamara hook: parsing $(basename "$LATEST")"

if [ "${LAITH_HOOK_DRY_RUN:-}" = "1" ]; then
    echo "    Tamara hook: DRY RUN — would invoke parser on $LATEST"
    exit 0
fi

docker compose exec -T backend \
    python scripts/ingest_tamara_investor_pack.py --file "$LATEST" --force
