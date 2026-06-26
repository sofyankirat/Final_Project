# PowerShell Script to Restore RAG Database Volumes
# Run this script after installing and starting Docker Desktop.

$ErrorActionPreference = "Stop"

# 1. Check if Docker is running
try {
    & docker ps > $null
} catch {
    Write-Error "Docker is not running or not in your system path. Please install and start Docker Desktop first."
    exit 1
}

# Get script folder and project folders
$volumesFolder = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $volumesFolder
$dockerFolder = Join-Path $projectRoot "docker"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Restoring Mini_RAG Database Volumes..." -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Volumes directory: $volumesFolder"
Write-Host "Docker directory:  $dockerFolder"
Write-Host ""

# 2. Start containers once to initialize the empty volumes, then stop them
Write-Host "-> Initializing Docker volumes..." -ForegroundColor Yellow
Set-Location $dockerFolder
& docker compose up -d
& docker compose down

# 3. Import backup data into each volume using Alpine container mount
Write-Host "-> Importing pgvector database backup..." -ForegroundColor Yellow
& docker run --rm -v docker_pgvector_data:/data -v "${volumesFolder}:/backup" alpine sh -c "rm -rf /data/* && tar xzf /backup/pgvector_backup.tar.gz -C /data"

Write-Host "-> Importing FastAPI assets backup..." -ForegroundColor Yellow
& docker run --rm -v docker_fastapi_data:/data -v "${volumesFolder}:/backup" alpine sh -c "rm -rf /data/* && tar xzf /backup/fastapi_backup.tar.gz -C /data"

Write-Host "-> Importing Qdrant vector database backup..." -ForegroundColor Yellow
& docker run --rm -v docker_qdrant_data:/data -v "${volumesFolder}:/backup" alpine sh -c "rm -rf /data/* && tar xzf /backup/qdrant_backup.tar.gz -C /data"

# 4. Start all services in detached mode
Write-Host "-> Starting all Docker services..." -ForegroundColor Yellow
& docker compose up -d

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  ✅ RESTORE COMPLETED SUCCESSFULLY!  " -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host "You can now run your FastAPI server with:"
Write-Host "cd $projectRoot\Mini_RAG\src"
Write-Host "python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000" -ForegroundColor Cyan
