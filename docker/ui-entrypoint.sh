#!/bin/sh
# Antikythera Frontend Entrypoint
# Validates configuration and starts Vite dev server

set -e

# Colors for output (disabled if not a terminal)
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

log_info() {
    echo "${BLUE}[INFO]${NC} $1"
}

log_warn() {
    echo "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo "${RED}[ERROR]${NC} $1"
}

log_success() {
    echo "${GREEN}[OK]${NC} $1"
}

# ------------------------------------------------------------------------------
# Configuration Validation
# ------------------------------------------------------------------------------
validate_config() {
    log_info "Validating Frontend configuration..."

    # Check VITE_API_URL - required for API proxy
    if [ -z "$VITE_API_URL" ]; then
        log_warn "VITE_API_URL not set, defaulting to http://localhost:8006"
        export VITE_API_URL="http://localhost:8006"
    fi

    log_success "Frontend configuration passed!"
    log_info "  - Vite API URL: $VITE_API_URL"
}

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

# Run validation
validate_config || exit 1

# If arguments are provided, pass them to npm
if [ "$#" -gt 0 ]; then
    exec npm run "$@"
fi

# Default: run dev server
log_info "Starting Vite development server..."
exec npm run dev -- --host 0.0.0.0 --port 5173