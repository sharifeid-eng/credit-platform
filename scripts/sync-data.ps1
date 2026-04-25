# Laith Data Sync — push local dataroom files to production server
# Usage:
#   .\scripts\sync-data.ps1              # sync all companies
#   .\scripts\sync-data.ps1 -Company Tamara   # sync one company
#
# Requires: SSH key access to production server
#
# Design notes:
#   - Pushes ONLY raw source files. Server owns registry.json / chunks / index.pkl
#     and rebuilds them on ingest. This prevents the dedup-skip bug where a
#     pre-populated registry.json synced onto a server with no chunks/ caused
#     every file to be "skipped (already ingested)".
#   - After sync, run deploy.sh on the server — it detects misalignment
#     (registry count != chunk count) and triggers ingest automatically.

param(
    [string]$Company = "",
    [string]$Server = "root@204.168.252.26",
    [string]$RemotePath = "/opt/credit-platform/data"
)

# SSH keepalive flags — long ingests/large PDF pushes were dropping connections.
# ServerAliveInterval 30 + ServerAliveCountMax 20 gives ~10min idle tolerance.
$SshOpts = @(
    "-o", "ServerAliveInterval=30",
    "-o", "ServerAliveCountMax=20"
)

$LocalData = Join-Path $PSScriptRoot "..\data"

# Files and folders the SERVER owns — never push these from laptop.
# Server rebuilds registry.json / chunks / index.pkl / meta.json on ingest.
# `notebooklm_state.json` is Google NotebookLM workspace state (transient app
# metadata, not analyst content) — see core/dataroom/engine.py _EXCLUDE_FILENAMES.
$ServerOwnedFiles = @('index.pkl', 'registry.json', 'meta.json', 'notebooklm_state.json')
$ServerOwnedFolders = @('chunks', 'analytics')

# Find companies with dataroom folders
if ($Company) {
    $companies = @($Company)
} else {
    $companies = Get-ChildItem -Path $LocalData -Directory |
        Where-Object { Test-Path (Join-Path $_.FullName "dataroom") } |
        ForEach-Object { $_.Name }
}

if ($companies.Count -eq 0) {
    Write-Host "No companies with dataroom folders found." -ForegroundColor Yellow
    exit 0
}

Write-Host "=== Laith Data Sync ===" -ForegroundColor Cyan
Write-Host "Server: $Server"
Write-Host "Companies: $($companies -join ', ')"
Write-Host "Server-owned files excluded: $($ServerOwnedFiles -join ', ')"
Write-Host "Server-owned folders excluded: $($ServerOwnedFolders -join ', ')"
Write-Host ""

foreach ($co in $companies) {
    $localDir = Join-Path $LocalData "$co\dataroom"
    if (-not (Test-Path $localDir)) {
        Write-Host "[$co] No dataroom folder, skipping" -ForegroundColor Yellow
        continue
    }

    # Count source files to sync (exclude server-owned artifacts)
    $files = Get-ChildItem -Path $localDir -Recurse -File |
        Where-Object {
            $excluded = $false
            foreach ($folder in $ServerOwnedFolders) {
                if ($_.FullName -match "\\$folder\\") { $excluded = $true; break }
            }
            (-not $excluded) -and ($_.Name -notin $ServerOwnedFiles)
        }

    Write-Host "[$co] $($files.Count) source files to sync from dataroom/" -ForegroundColor Green

    # Ensure remote directory exists
    ssh $SshOpts $Server "mkdir -p $RemotePath/$co/dataroom"

    # Sync each subfolder and root file individually to preserve structure
    # and exclude server-owned artifacts
    $subfolders = Get-ChildItem -Path $localDir -Directory |
        Where-Object { $_.Name -notin $ServerOwnedFolders }

    $rootFiles = Get-ChildItem -Path $localDir -File |
        Where-Object { $_.Name -notin $ServerOwnedFiles }

    # Sync root source files (do NOT sync registry.json — server owns it)
    foreach ($file in $rootFiles) {
        scp $SshOpts "$($file.FullName)" "${Server}:${RemotePath}/${co}/dataroom/"
    }

    # Sync subfolders (excluding chunks/analytics)
    foreach ($folder in $subfolders) {
        Write-Host "  Syncing $($folder.Name)/" -ForegroundColor Gray
        scp $SshOpts -r "$($folder.FullName)" "${Server}:${RemotePath}/${co}/dataroom/"
    }

    Write-Host "[$co] Sync complete" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Sync complete ===" -ForegroundColor Cyan
Write-Host "Now run on the server to rebuild search indexes:"
Write-Host "  ssh $Server"
Write-Host "  cd /opt/credit-platform && ./deploy.sh"
Write-Host ""
Write-Host "deploy.sh will auto-detect registry/chunks misalignment and re-ingest"
Write-Host "any dataroom where counts don't match."
Write-Host ""
Write-Host "To force-rebuild a single company's index without a full deploy:"
Write-Host "  ssh $Server 'cd /opt/credit-platform && docker compose exec -T backend \\"
Write-Host "    python scripts/dataroom_ctl.py ingest --company <name>'"
