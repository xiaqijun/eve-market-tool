#!/usr/bin/env bash
# ============================================================
# EVE Market Tool — Deployment Script
# Usage: bash deploy.sh [server_ip] [ssh_user]
# Example: bash deploy.sh 123.45.67.89 root
# ============================================================

set -euo pipefail

SERVER_IP="${1:-}"
SSH_USER="${2:-root}"
PROJECT_DIR="F:/github/EVE_Market_Tool"

# ---- Colors ----
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log()  { echo -e "${GREEN}[INFO]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ---- Validate ----
if [ -z "$SERVER_IP" ]; then
    echo "Usage: bash deploy.sh <SERVER_IP> [SSH_USER]"
    echo "Example: bash deploy.sh 123.45.67.89 root"
    exit 1
fi

log "Deploying to ${SSH_USER}@${SERVER_IP} ..."

# ---- Check .env exists ----
if [ ! -f .env ]; then
    log "Creating .env from .env.production..."
    cp .env.production .env
    err "Please edit .env before deploying:
    - POSTGRES_PASSWORD
    - SECRET_KEY
    - ESI_USER_AGENT (set your contact email)
    - EVE_CLIENT_ID / EVE_CLIENT_SECRET / EVE_CALLBACK_URL"
fi

# ---- Step 1: Install Docker on server (if needed) ----
log "Step 1: Check Docker on server..."
ssh "${SSH_USER}@${SERVER_IP}" 'bash -s' <<'DOCKER_SETUP'
    if ! command -v docker &>/dev/null; then
        echo "Installing Docker..."
        curl -fsSL https://get.docker.com | bash
    fi
    if ! docker compose version &>/dev/null 2>&1; then
        echo "Docker Compose plugin not found. Installing..."
        apt-get update -qq && apt-get install -y -qq docker-compose-plugin 2>/dev/null || true
    fi
    echo "Docker version: $(docker --version)"
    echo "Compose version: $(docker compose version 2>/dev/null || echo 'use docker-compose (standalone)')"
DOCKER_SETUP

# ---- Step 2: Sync project files ----
log "Step 2: Syncing project files..."
rsync -avz --delete \
    --exclude='.venv' \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='eve_market_tool.egg-info' \
    --exclude='.env' \
    --exclude='.env.example' \
    --exclude='uv.lock' \
    ./ "${SSH_USER}@${SERVER_IP}:/opt/eve-market-tool/"

# ---- Step 3: Upload .env separately ----
log "Step 3: Uploading .env..."
scp .env "${SSH_USER}@${SERVER_IP}:/opt/eve-market-tool/.env"

# ---- Step 4: Build and start ----
log "Step 4: Building and starting containers..."
ssh "${SSH_USER}@${SERVER_IP}" <<'REMOTE'
    cd /opt/eve-market-tool

    # Build images
    docker compose build --pull

    # Start services
    docker compose up -d

    # Wait for DB
    echo "Waiting for PostgreSQL to be ready..."
    sleep 5

    # Run migrations
    echo "Running database migrations..."
    docker compose exec -T app alembic upgrade head || echo "Migration may have already been applied or DB not ready yet"

    # Check status
    echo ""
    echo "=== Container Status ==="
    docker compose ps
REMOTE

# ---- Step 5: Open firewall port ----
log "Step 5: Opening firewall port 8000 (if ufw is active)..."
ssh "${SSH_USER}@${SERVER_IP}" 'bash -s' <<'FW'
    if command -v ufw &>/dev/null && ufw status | grep -q "Status: active"; then
        ufw allow 8000/tcp
        echo "Port 8000 opened"
    else
        echo "ufw not active — ensure cloud firewall allows port 8000"
    fi
FW

# ---- Done ----
log "============================================"
log "Deployment complete!"
log "============================================"
log "App:     http://${SERVER_IP}:8000"
log "API Docs: http://${SERVER_IP}:8000/docs"
log ""
log "Next steps:"
log "  1. Open port 8000 in 腾讯云 firewall console"
log "  2. Set EVE SSO callback to: http://${SERVER_IP}:8000/api/v1/auth/callback"
log "  3. View logs: ssh ${SSH_USER}@${SERVER_IP} 'cd /opt/eve-market-tool && docker compose logs -f'"
