# Laith Data Sync — push local dataroom files to production server
# Usage:
#   .\scripts\sync-data.ps1              # sync all companies
#   .\scripts\sync-data.ps1 -Company Tamara   # sync one company
#
# Requires: SSH key access to production server

param(
    [string]$Company = "",
    [string]$Server = "root@204.168.252.26",
    [string]$RemotePath = "/opt/credit-platform/data"
)

$LocalData = Join-Path $PSScriptRoot "..\data"

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
Write-Host ""

foreach ($co in $companies) {
    $localDir = Join-Path $LocalData "$co\dataroom"
    if (-not (Test-Path $localDir)) {
        Write-Host "[$co] No dataroom folder, skipping" -ForegroundColor Yellow
        continue
    }

    # Count files to sync (exclude chunks, analytics, index.pkl)
    $files = Get-ChildItem -Path $localDir -Recurse -File |
        Where-Object {
            $_.FullName -notmatch '\\chunks\\' -and
            $_.FullName -notmatch '\\analytics\\' -and
            $_.Name -ne 'index.pkl'
        }

    Write-Host "[$co] $($files.Count) files to sync from dataroom/" -ForegroundColor Green

    # Use scp to push the dataroom folder
    # Ensure remote directory exists first
    ssh $Server "mkdir -p $RemotePath/$co/dataroom"

    # Sync each subfolder and root file individually to preserve structure
    # and exclude chunks/analytics/index.pkl
    $subfolders = Get-ChildItem -Path $localDir -Directory |
        Where-Object { $_.Name -notin @('chunks', 'analytics') }

    $rootFiles = Get-ChildItem -Path $localDir -File |
        Where-Object { $_.Name -ne 'index.pkl' }

    # Sync root files (registry.json, etc.)
    foreach ($file in $rootFiles) {
        scp "$($file.FullName)" "${Server}:${RemotePath}/${co}/dataroom/"
    }

    # Sync subfolders
    foreach ($folder in $subfolders) {
        Write-Host "  Syncing $($folder.Name)/" -ForegroundColor Gray
        scp -r "$($folder.FullName)" "${Server}:${RemotePath}/${co}/dataroom/"
    }

    Write-Host "[$co] Sync complete" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Sync complete ===" -ForegroundColor Cyan
Write-Host "Now run on the server to rebuild search indexes:"
Write-Host "  ssh $Server"
Write-Host "  cd /opt/credit-platform && ./deploy.sh"
Write-Host ""
Write-Host "Or ingest manually:"
foreach ($co in $companies) {
    # Find products for this company
    $configFiles = Get-ChildItem -Path (Join-Path $LocalData $co) -Recurse -Filter "config.json" |
        Where-Object { $_.DirectoryName -notmatch '\\dataroom\\' }
    foreach ($cfg in $configFiles) {
        $product = Split-Path $cfg.DirectoryName -Leaf
        Write-Host "  docker compose exec backend curl -X POST http://localhost:8000/companies/$co/products/$product/dataroom/ingest"
    }
}
