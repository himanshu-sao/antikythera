#!/bin/sh
# Antikythera Backend Entrypoint
# Validates configuration and starts services

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
    log_info "Validating Antikythera configuration..."

    CONFIG_DIR="${HOME}/.antikythera"
    ENV_FILE="${CONFIG_DIR}/.env"
    AI_ENV_FILE="${CONFIG_DIR}/.ai_env"
    MISSING_VARS=""
    WARNINGS=""

    # Check if config directory exists
    if [ ! -d "$CONFIG_DIR" ]; then
        log_error "Configuration directory not found: $CONFIG_DIR"
        log_error ""
        log_error "Please create the directory and add your configuration:"
        log_error "  mkdir -p $CONFIG_DIR"
        log_error "  vim $CONFIG_DIR/.env"
        log_error ""
        log_error "See README.md for configuration template."
        exit 1
    fi

    # Check for .env file
    if [ ! -f "$ENV_FILE" ]; then
        log_error "Configuration file not found: $ENV_FILE"
        log_error ""
        log_error "Please create this file with your credentials."
        log_error "Template:"
        log_error "  PORT=8006"
        log_error "  VITE_API_URL=http://localhost:5173"
        log_error "  JIRA_BASE_URL=https://your-domain.atlassian.net"
        log_error "  JIRA_PAT=your_personal_access_token"
        log_error ""
        exit 1
    fi

    # Source the env file to check variables
    set -a
    . "$ENV_FILE"
    set +a

    # Required variables check
    REQUIRED_VARS="PORT JIRA_BASE_URL JIRA_PAT"
    for var in $REQUIRED_VARS; do
        eval "value=\$$var"
        if [ -z "$value" ] || [ "$value" = "your_"* ] || [ "$value" = "dummy"* ]; then
            MISSING_VARS="$MISSING_VARS $var"
        fi
    done

    # Check for at least one AI provider key
    AI_KEYS="NVIDIA_API_KEY GOOGLE_API_KEY OPENROUTER_API_KEY ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN"
    AI_KEY_FOUND=""
    for key in $AI_KEYS; do
        eval "value=\$$key"
        if [ -n "$value" ] && [ "$value" != "dummy"* ] && [ "$value" != "your_"* ]; then
            AI_KEY_FOUND="$key"
            break
        fi
    done

    # Check for .ai_env file (optional but recommended)
    if [ -f "$AI_ENV_FILE" ]; then
        log_success "Found AI environment file: $AI_ENV_FILE"

        # Additional AI keys from .ai_env
        set -a
        . "$AI_ENV_FILE"
        set +a
    else
        WARNINGS="$WARNINGS AI environment file not found ($AI_ENV_FILE)"
    fi

    # Report missing required variables
    if [ -n "$MISSING_VARS" ]; then
        log_error "Missing or unconfigured required variables:$MISSING_VARS"
        log_error ""
        log_error "Please add these to your $ENV_FILE"
        exit 1
    fi

    # Warn if no AI key found
    if [ -z "$AI_KEY_FOUND" ]; then
        log_warn "No AI provider API key configured."
        log_warn "Add one of these to $ENV_FILE or $AI_ENV_FILE:"
        log_warn "  - NVIDIA_API_KEY"
        log_warn "  - GOOGLE_API_KEY"
        log_warn "  - OPENROUTER_API_KEY"
        log_warn "  - ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN"
        log_warn ""
        log_warn "AI features will not work until an API key is configured."
    else
        log_success "AI provider configured: $AI_KEY_FOUND"
    fi

    # Check data directory
    DATA_DIR="/app/automation-ideas"
    if [ ! -d "$DATA_DIR" ]; then
        log_error "Data directory not found: $DATA_DIR"
        log_error "This should be mounted from the host."
        exit 1
    fi

    # Check if data directory is writable
    if [ ! -w "$DATA_DIR" ]; then
        log_error "Data directory is not writable: $DATA_DIR"
        log_error "Please ensure the host directory has write permissions."
        exit 1
    fi

    log_success "Configuration validation passed!"
    log_info "  - Port: $PORT"
    log_info "  - Jira Base URL: $JIRA_BASE_URL"
    log_info "  - Data directory: $DATA_DIR"
    if [ -n "$AI_KEY_FOUND" ]; then
        log_info "  - AI Provider: $AI_KEY_FOUND"
    fi
}

# ------------------------------------------------------------------------------
# Start Services
# ------------------------------------------------------------------------------
start_backend() {
    log_info "Starting Antikythera Backend on port $PORT..."

    # Use PYTHONPATH to ensure proper module resolution
    export PYTHONPATH=/app

    # Start uvicorn
    exec python -m uvicorn api.main:app --host 0.0.0.0 --port "$PORT"
}

start_orchestrator() {
    log_info "Starting Antikythera Orchestrator..."

    export PYTHONPATH=/app
    exec python scripts/run_orchestrator.py
}

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

# Run validation first
validate_config || exit 1

# Parse command line arguments
if [ "$#" -eq 0 ]; then
    # Default: start backend
    start_backend
fi

case "$1" in
    --start-backend)
        start_backend
        ;;
    --start-orchestrator)
        start_orchestrator
        ;;
    --validate-only)
        log_info "Validation complete. Exiting."
        exit 0
        ;;
    *)
        # Pass through to whatever command was given
        exec "$@"
        ;;
esac