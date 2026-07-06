#!/usr/bin/env bash
# =============================================================================
# Development Environment Setup Script
# =============================================================================
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[SETUP]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check prerequisites
check_prereqs() {
    log "Checking prerequisites..."

    command -v python3 >/dev/null 2>&1 || { err "python3 is required"; exit 1; }
    command -v node >/dev/null 2>&1 || { err "node is required"; exit 1; }
    command -v npm >/dev/null 2>&1 || { err "npm is required"; exit 1; }
    command -v docker >/dev/null 2>&1 || warn "docker not found — container services won't start"
    command -v git >/dev/null 2>&1 || { err "git is required"; exit 1; }

    log "All prerequisites satisfied."
}

# Set up Python backend
setup_backend() {
    log "Setting up Python backend..."

    cd backend

    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
        log "Virtual environment created."
    fi

    # Activate (platform-aware)
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        source .venv/Scripts/activate
    else
        source .venv/bin/activate
    fi

    pip install --upgrade pip
    pip install -r requirements.txt

    log "Backend dependencies installed."
    cd ..
}

# Set up frontend
setup_frontend() {
    log "Setting up Next.js frontend..."

    cd frontend
    npm install
    log "Frontend dependencies installed."
    cd ..
}

# Copy environment file
setup_env() {
    if [ ! -f ".env" ]; then
        cp .env.example .env
        log ".env file created from template. Please edit it with your API keys."
    else
        log ".env file already exists, skipping."
    fi
}

# Start infrastructure
start_infra() {
    log "Starting Docker infrastructure..."
    docker compose -f docker/docker-compose.yml up -d postgres redis minio
    log "Infrastructure started (postgres, redis, minio)."
}

# Main
main() {
    echo ""
    echo "============================================"
    echo " Enterprise RAG Agent — Dev Setup"
    echo "============================================"
    echo ""

    check_prereqs
    setup_env
    setup_backend
    setup_frontend
    start_infra

    echo ""
    log "Setup complete! Run the following to start development:"
    echo ""
    echo "  Backend:  cd backend && uvicorn app.main:app --reload"
    echo "  Frontend: cd frontend && npm run dev"
    echo "  Docs:     http://localhost:8000/docs"
    echo ""
}

main
