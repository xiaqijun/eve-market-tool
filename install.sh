#!/usr/bin/env bash
# ============================================================
# EVE Market Tool — One-Click Installer
#
# Download and run:
#   curl -fsSL https://raw.githubusercontent.com/xiaqijun/eve-market-tool/main/install.sh | bash
#
# Or with custom settings:
#   curl -fsSL .../install.sh | bash -s -- --port 9000 --dir /opt/eve
# ============================================================

set -euo pipefail

# ---- Auto-detect sudo ----
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo &>/dev/null; then
        SUDO="sudo"
    else
        echo "Error: This script requires root. Run with: sudo bash"
        exit 1
    fi
else
    SUDO=""
fi

# ---- Defaults ----
INSTALL_DIR="/opt/eve-market-tool"
APP_PORT=8000
DB_PORT=5432
REPO_URL="https://github.com/xiaqijun/eve-market-tool.git"
BRANCH="main"

# ---- Parse args ----
UPDATE_MODE=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --update) UPDATE_MODE=true; shift ;;
        --dir)    INSTALL_DIR="$2"; shift 2 ;;
        --port)   APP_PORT="$2"; shift 2 ;;
        --db-port) DB_PORT="$2"; shift 2 ;;
        --repo)   REPO_URL="$2"; shift 2 ;;
        --branch) BRANCH="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --update         Update existing installation"
            echo "  --dir PATH       Install directory (default: /opt/eve-market-tool)"
            echo "  --port PORT      App port (default: 8000)"
            echo "  --db-port PORT   Database port (default: 5432)"
            echo "  --repo URL       Git repository URL"
            echo "  --branch NAME    Git branch (default: main)"
            echo "  -h, --help       Show this help"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ---- Colors ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }
info() { echo -e "${CYAN}[i]${NC} $*"; }

# ---- Banner ----
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     EVE Market Tool — One-Click Setup    ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

# ---- Check prerequisites ----
info "Checking prerequisites..."

if ! command -v docker &>/dev/null; then
    warn "Docker not found. Installing..."
    curl -fsSL https://get.docker.com | bash
    systemctl enable docker && systemctl start docker
    log "Docker installed"
else
    log "Docker: $(docker --version | head -1)"
fi

if ! docker compose version &>/dev/null 2>&1; then
    warn "Docker Compose plugin not found. Installing..."
    apt-get update -qq && apt-get install -y -qq docker-compose-plugin
    log "Docker Compose installed"
else
    log "Docker Compose: $(docker compose version --short 2>/dev/null || echo 'OK')"
fi

if ! command -v git &>/dev/null; then
    warn "Git not found. Installing..."
    apt-get update -qq && apt-get install -y -qq git
    log "Git installed"
else
    log "Git: $(git --version)"
fi

# ---- Update mode ----
if [ "$UPDATE_MODE" = true ]; then
    if [ ! -d "$INSTALL_DIR/.git" ]; then
        err "No installation found at $INSTALL_DIR. Run without --update first."
    fi

    echo ""
    info "Updating EVE Market Tool..."

    cd "$INSTALL_DIR"

    # Save current version
    OLD_VER=$(grep 'version' pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')
    info "Current version: $OLD_VER"

    # Pull latest
    info "Pulling latest code..."
    git fetch origin "$BRANCH"
    git reset --hard "origin/$BRANCH"
    NEW_VER=$(grep 'version' pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')
    log "Updated: $OLD_VER → $NEW_VER"

    # Rebuild
    info "Rebuilding containers..."
    docker compose build --pull
    log "Images rebuilt"

    # Restart
    info "Restarting services..."
    docker compose up -d
    log "Services restarted"

    # Migrations
    info "Running migrations..."
    docker compose exec -T app alembic upgrade head 2>&1 || warn "Migration may need manual review"

    # Health check
    sleep 3
    HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:${APP_PORT}/" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        log "App responding (HTTP $HTTP_CODE)"
    else
        warn "App returned HTTP $HTTP_CODE — may still be starting"
    fi

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          Update Complete!                ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  Version: ${OLD_VER} → ${CYAN}${NEW_VER}${NC}"
    echo -e "  Logs:    cd ${INSTALL_DIR} && docker compose logs -f"
    echo ""
    exit 0
fi

# ---- Clone or update repo ----
echo ""
info "Setting up project..."

if [ -d "$INSTALL_DIR/.git" ]; then
    info "Existing installation found. Pulling latest..."
    cd "$INSTALL_DIR"
    git fetch origin "$BRANCH"
    git reset --hard "origin/$BRANCH"
    log "Updated to latest"
elif [ -d "$INSTALL_DIR" ]; then
    warn "Directory $INSTALL_DIR exists but is not a git repo."
    BACKUP="${INSTALL_DIR}.bak.$(date +%s)"
    info "Backing up to $BACKUP ..."
    $SUDO mv "$INSTALL_DIR" "$BACKUP"
    log "Old directory moved to $BACKUP"
    info "Cloning fresh copy..."
    $SUDO git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
    $SUDO chown -R "$(id -u):$(id -g)" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    log "Cloned to $INSTALL_DIR"
else
    info "Cloning repository..."
    $SUDO git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
    $SUDO chown -R "$(id -u):$(id -g)" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    log "Cloned to $INSTALL_DIR"
fi

# ---- Generate .env ----
echo ""
info "Configuring environment..."

if [ -f .env ]; then
    warn ".env already exists — keeping existing config"
else
    # Generate random secrets
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)
    POSTGRES_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))" 2>/dev/null || openssl rand -base64 16)

    # Detect server IP
    SERVER_IP=$(curl -s --max-time 5 https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}' || echo "YOUR_SERVER_IP")

    cat > .env <<EOF
# ---- Database ----
POSTGRES_USER=eve_market
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=eve_market
DB_PORT=${DB_PORT}

# ---- Application ----
APP_PORT=${APP_PORT}

# ---- ESI API ----
ESI_USER_AGENT=EVE-Market-Tool/1.0 (installer; +https://github.com/xiaqijun/eve-market-tool)
ESI_BASE_URL=https://esi.evetech.net/latest

# ---- Security ----
SECRET_KEY=${SECRET_KEY}

# ---- EVE SSO (optional, configure at https://developers.eveonline.com/) ----
EVE_CLIENT_ID=
EVE_CLIENT_SECRET=
EVE_CALLBACK_URL=http://${SERVER_IP}:${APP_PORT}/api/v1/auth/callback

# ---- Scheduler ----
MARKET_FETCH_INTERVAL_MINUTES=5
EOF

    log ".env generated with random secrets"
    info "Server IP detected: ${SERVER_IP}"
fi

# ---- Build and start ----
echo ""
info "Building Docker images (this may take a few minutes)..."
docker compose build --pull

info "Starting services..."
docker compose up -d

# ---- Wait for DB ----
info "Waiting for PostgreSQL..."
for i in $(seq 1 30); do
    if docker compose exec -T db pg_isready -U eve_market &>/dev/null; then
        log "PostgreSQL ready"
        break
    fi
    sleep 1
done

# ---- Run migrations ----
echo ""
info "Running database migrations..."
docker compose exec -T app alembic upgrade head 2>&1 || warn "Migration may need manual review"

# ---- Health check ----
info "Verifying deployment..."
sleep 3

HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:${APP_PORT}/" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    log "App responding (HTTP $HTTP_CODE)"
else
    warn "App returned HTTP $HTTP_CODE — may still be starting up"
fi

# ---- Install CLI tool ----
info "Installing 'eve' CLI tool..."
$SUDO cp "$INSTALL_DIR/eve" /usr/local/bin/eve
$SUDO chmod +x /usr/local/bin/eve
log "CLI tool installed: eve"

# ---- Done ----
SERVER_IP_OUT=$(curl -s https://api.ipify.org 2>/dev/null || echo 'YOUR_SERVER_IP')
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║        Installation Complete!            ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "  App:       ${CYAN}http://${SERVER_IP_OUT}:${APP_PORT}/${NC}"
echo -e "  API Docs:  ${CYAN}http://${SERVER_IP_OUT}:${APP_PORT}/docs${NC}"
echo ""
echo -e "  Config:    ${INSTALL_DIR}/.env"
echo ""
echo "  CLI commands:"
echo "    eve status    — view service status"
echo "    eve logs      — view logs"
echo "    eve update    — pull latest and rebuild"
echo "    eve restart   — restart services"
echo "    eve help      — show all commands"
echo ""
echo "  Next steps:"
echo "  1. Open port ${APP_PORT} in your cloud firewall"
echo "  2. Edit .env to configure EVE SSO (optional)"
echo "  3. Set EVE SSO callback: http://${SERVER_IP_OUT}:${APP_PORT}/api/v1/auth/callback"
echo ""
