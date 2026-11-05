$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

$queryFiles = Get-ChildItem -LiteralPath (Join-Path $projectRoot 'sql') -Filter '0*.sql' -File |
    Sort-Object -Property Name

foreach ($queryFile in $queryFiles) {
    Write-Host "Running $($queryFile.Name)..."
    Get-Content -LiteralPath $queryFile.FullName -Raw |
        docker compose exec -T db psql -X -v ON_ERROR_STOP=1 -U marketlytics -d marketlytics
    if ($LASTEXITCODE -ne 0) {
        throw "SQL analysis failed in $($queryFile.Name) (psql exit code $LASTEXITCODE)."
    }
}

Write-Host "All $($queryFiles.Count) analytical SQL files completed."
