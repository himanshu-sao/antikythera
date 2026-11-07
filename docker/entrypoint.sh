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

# True (exit 0) when a value is empty or still a template placeholder.
# POSIX sh does not glob-match on the right-hand side of `[ = ]`, so a
# `case` pattern is required here (SEC-14 / O4).
is_placeholder() {
    case "$1" in
        ""|your_*|dummy*) return 0 ;;
        *) return 1 ;;
    esac
}

# ------------------------------------------------------------------------------
# Safe env-file loader (P5-3 C3)
# ------------------------------------------------------------------------------
# The user's .env and .ai_env were previously loaded with `set -a; . file`, which runs the
# file as shell: a $(...) or backtick in a value would execute. This parser only reads
# KEY=VALUE lines and never evaluates the value.
#   - blank lines and lines starting with # are skipped
#   - a leading "export " is accepted
#   - the line is split on the FIRST '='; the name must match ^[A-Za-z_][A-Za-z0-9_]*$
#   - one pair of surrounding double quotes is removed (contents kept literally)
#   - a single-quoted value is unquoted the way bash does: the quotes are removed and each
#     '\'' sequence (the form api/services/ai_engine_config.py writes) becomes one '
#   - an unquoted value ends at an inline " #" comment and loses trailing blanks, as the
#     shell did before (so existing files keep the same values)
load_env_file() {
    _lef_file="$1"
    while IFS= read -r _lef_line || [ -n "$_lef_line" ]; do
        _lef_line="${_lef_line%"$(printf '\r')"}"
        # trim leading whitespace
        _lef_line="${_lef_line#"${_lef_line%%[![:space:]]*}"}"
        case "$_lef_line" in
            ""|"#"*) continue ;;
            "export "*) _lef_line="${_lef_line#export }"
                        _lef_line="${_lef_line#"${_lef_line%%[![:space:]]*}"}" ;;
        esac
        case "$_lef_line" in
            *=*) ;;
            *) continue ;;
        esac
        _lef_key="${_lef_line%%=*}"
        _lef_val="${_lef_line#*=}"
        case "$_lef_key" in
            ""|[0-9]*|*[!A-Za-z0-9_]*) continue ;;
        esac
        case "$_lef_val" in
            \'*\')
                if [ "${#_lef_val}" -ge 2 ]; then
                    _lef_val="${_lef_val#\'}"
                    _lef_val="${_lef_val%\'}"
                    # turn each '\'' into a single quote (pure parameter expansion, no eval)
                    _lef_out=""
                    while :; do
                        case "$_lef_val" in
                            *"'\\''"*)
                                _lef_out="${_lef_out}${_lef_val%%"'\\''"*}'"
                                _lef_val="${_lef_val#*"'\\''"}"
                                ;;
                            *) _lef_out="${_lef_out}${_lef_val}"; break ;;
                        esac
                    done
                    _lef_val="$_lef_out"
                fi
                ;;
            \"*\")
                if [ "${#_lef_val}" -ge 2 ]; then
                    _lef_val="${_lef_val#\"}"
                    _lef_val="${_lef_val%\"}"
                fi
                ;;
            *)
                # unquoted: drop an inline comment (whitespace then #), then trailing blanks
                case "$_lef_val" in
                    *[[:space:]]"#"*) _lef_val="${_lef_val%%[[:space:]]#*}" ;;
                esac
                _lef_val="${_lef_val%"${_lef_val##*[![:space:]]}"}"
                ;;
        esac
        export "$_lef_key=$_lef_val"
    done < "$_lef_file"
    unset _lef_file _lef_line _lef_key _lef_val _lef_out
}

# ------------------------------------------------------------------------------
# Configuration Validation
# ------------------------------------------------------------------------------
validate_config() {
    log_info "Validating Antikythera configuration..."

    CONFIG_DIR="${ANTIKYTHERA_HOME:-${HOME}/.antikythera}"
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
        log_error "  VITE_API_URL=http://localhost:8006"
        log_error "  # Optional (Jira integration):"
        log_error "  JIRA_BASE_URL=https://your-domain.atlassian.net"
        log_error "  JIRA_PAT=your_personal_access_token"
        log_error ""
        exit 1
    fi

    # Load the env file to check variables (parsed, never executed as shell)
    load_env_file "$ENV_FILE"

    # Required variables check (Jira is optional: warn only)
    REQUIRED_VARS="PORT"
    for var in $REQUIRED_VARS; do
        eval "value=\$$var"
        if is_placeholder "$value"; then
            MISSING_VARS="$MISSING_VARS $var"
        fi
    done

    JIRA_CONFIGURED=""
    eval "jira_url=\${JIRA_BASE_URL:-}"
    eval "jira_pat=\${JIRA_PAT:-}"
    if is_placeholder "$jira_url" || is_placeholder "$jira_pat"; then
        WARNINGS="$WARNINGS Jira integration not configured (JIRA_BASE_URL/JIRA_PAT)"
    else
        JIRA_CONFIGURED="yes"
    fi

    # Check for at least one AI provider key
    AI_KEYS="NVIDIA_API_KEY GOOGLE_API_KEY OPENROUTER_API_KEY ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN"
    AI_KEY_FOUND=""
    for key in $AI_KEYS; do
        eval "value=\${$key:-}"
        if ! is_placeholder "$value"; then
            AI_KEY_FOUND="$key"
            break
        fi
    done

    # Check for .ai_env file (optional but recommended)
    if [ -f "$AI_ENV_FILE" ]; then
        log_success "Found AI environment file: $AI_ENV_FILE"

        # Additional AI keys from .ai_env (parsed, never executed as shell)
        load_env_file "$AI_ENV_FILE"
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
    if [ -n "$JIRA_CONFIGURED" ]; then
        log_info "  - Jira Base URL: $JIRA_BASE_URL"
    else
        log_warn "  - Jira: not configured (optional; set JIRA_BASE_URL and JIRA_PAT to enable)"
    fi
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