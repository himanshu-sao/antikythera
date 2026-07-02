#!/bin/bash
# Antikythera Docker Automated Test Suite
#
# Usage:
#   ./test-docker.sh              # Run all tests
#   ./test-docker.sh quick        # Quick smoke test only
#   ./test-docker.sh build        # Test build only
#   ./test-docker.sh cleanup      # Clean up test artifacts
#
# This script:
# 1. Builds Docker images
# 2. Runs containers with test config
# 3. Validates configuration, health, API, and cleanup
# 4. Reports pass/fail for each test

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Test configuration
TEST_CONFIG_DIR="$HOME/.antikythera.test_$$"
TEST_DATA_DIR="$HOME/antikythera-data.test_$$"
TEST_LOGS_DIR="$SCRIPT_DIR/logs.test_$$"

# Cleanup on exit
cleanup() {
    log_info "Cleaning up test artifacts..."
    docker-compose -f "$SCRIPT_DIR/docker-compose.yml" down -v 2>/dev/null || true
    rm -rf "$TEST_CONFIG_DIR" "$TEST_DATA_DIR" "$TEST_LOGS_DIR" 2>/dev/null || true
    rm -f "$SCRIPT_DIR/docker-compose.test.yml" 2>/dev/null || true
}

trap cleanup EXIT

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}✓ PASS${NC} $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

log_fail() {
    echo -e "${RED}✗ FAIL${NC} $1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

log_skip() {
    echo -e "${YELLOW}○ SKIP${NC} $1"
    TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
}

log_section() {
    echo -e "\n${BLUE}════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}════════════════════════════════════════${NC}\n"
}

# ------------------------------------------------------------------------------
# Test Functions
# ------------------------------------------------------------------------------

test_build_images() {
    log_section "Test 1: Build Docker Images"

    log_info "Building backend image..."
    if docker build -f "$SCRIPT_DIR/Dockerfile" -t "antikythera-backend:test" "$PROJECT_ROOT" > "$TEST_LOGS_DIR/build_backend.log" 2>&1; then
        log_pass "Backend image built successfully"
    else
        log_fail "Backend image build failed (see $TEST_LOGS_DIR/build_backend.log)"
        cat "$TEST_LOGS_DIR/build_backend.log"
        return 1
    fi

    log_info "Building frontend image..."
    if docker build -f "$SCRIPT_DIR/Dockerfile.ui" -t "antikythera-ui:test" "$PROJECT_ROOT" > "$TEST_LOGS_DIR/build_ui.log" 2>&1; then
        log_pass "Frontend image built successfully"
    else
        log_fail "Frontend image build failed (see $TEST_LOGS_DIR/build_ui.log)"
        cat "$TEST_LOGS_DIR/build_ui.log"
        return 1
    fi
}

test_config_validation_missing() {
    log_section "Test 2: Config Validation - Missing .env"

    # Create test compose without config mount
    cat > "$SCRIPT_DIR/docker-compose.test.yml" << EOF
services:
  backend:
    image: antikythera-backend:test
    container_name: antikythera-test-backend
    volumes:
      - $TEST_DATA_DIR:/app/automation-ideas
    networks:
      - test-network
networks:
  test-network:
    driver: bridge
EOF

    log_info "Starting container without config..."
    docker-compose -f "$SCRIPT_DIR/docker-compose.test.yml" up -d 2>&1 | tee "$TEST_LOGS_DIR/no_config.log" || true

    # Wait for container to exit
    sleep 5

    # Check logs for validation error (looks for either dir or file not found)
    if docker logs antikythera-test-backend 2>&1 | grep -qE "Configuration (directory|file) not found"; then
        log_pass "Correctly fails when .env is missing"
    else
        log_fail "Did not fail on missing .env"
        docker logs antikythera-test-backend 2>&1 | tail -20
    fi

    docker-compose -f "$SCRIPT_DIR/docker-compose.test.yml" down -v 2>/dev/null || true
}

test_config_validation_empty() {
    log_section "Test 3: Config Validation - Empty .env"

    # Create empty config
    mkdir -p "$TEST_CONFIG_DIR"
    touch "$TEST_CONFIG_DIR/.env"

    cat > "$SCRIPT_DIR/docker-compose.test.yml" << EOF
services:
  backend:
    image: antikythera-backend:test
    container_name: antikythera-test-backend
    volumes:
      - $TEST_CONFIG_DIR:/root/.antikythera:ro
      - $TEST_DATA_DIR:/app/automation-ideas
    networks:
      - test-network
networks:
  test-network:
    driver: bridge
EOF

    log_info "Starting container with empty config..."
    docker-compose -f "$SCRIPT_DIR/docker-compose.test.yml" up -d 2>&1 | tee "$TEST_LOGS_DIR/empty_config.log" || true

    sleep 5

    if docker logs antikythera-test-backend 2>&1 | grep -qE "(Missing.*required|Configuration file not found)"; then
        log_pass "Correctly fails with empty .env"
    else
        log_fail "Did not fail on empty .env"
        docker logs antikythera-test-backend 2>&1 | tail -20
    fi

    docker-compose -f "$SCRIPT_DIR/docker-compose.test.yml" down -v 2>/dev/null || true
}

test_config_validation_no_ai_key() {
    log_section "Test 4: Config Validation - Missing AI Key (Warning)"

    # Create config with required vars but no AI key
    cat > "$TEST_CONFIG_DIR/.env" << EOF
PORT=8006
JIRA_BASE_URL=https://test.atlassian.net
JIRA_PAT=test_token
EOF

    cat > "$SCRIPT_DIR/docker-compose.test.yml" << EOF
services:
  backend:
    image: antikythera-backend:test
    container_name: antikythera-test-backend
    volumes:
      - $TEST_CONFIG_DIR:/root/.antikythera:ro
      - $TEST_DATA_DIR:/app/automation-ideas
    networks:
      - test-network
networks:
  test-network:
    driver: bridge
EOF

    log_info "Starting container without AI key..."
    docker-compose -f "$SCRIPT_DIR/docker-compose.test.yml" up -d 2>&1 | tee "$TEST_LOGS_DIR/no_ai.log" || true

    sleep 5

    # Should start but show warning
    if docker logs antikythera-test-backend 2>&1 | grep -q "No AI provider API key configured"; then
        log_pass "Correctly warns about missing AI key"
    else
        log_fail "Did not warn about missing AI key"
        docker logs antikythera-test-backend 2>&1 | tail -20
    fi

    # Container should still be running
    if docker ps | grep -q antikythera-test-backend; then
        log_pass "Container running despite missing AI key"
    else
        log_fail "Container exited (should still run)"
    fi

    docker-compose -f "$SCRIPT_DIR/docker-compose.test.yml" down -v 2>/dev/null || true
}

test_health_check() {
    log_section "Test 5: Health Check"

    # Create test directories first
    mkdir -p "$TEST_CONFIG_DIR"

    # Create valid config
    cat > "$TEST_CONFIG_DIR/.env" << EOF
PORT=8006
JIRA_BASE_URL=https://test.atlassian.net
JIRA_PAT=test_token
NVIDIA_API_KEY=nvapi_test
EOF

    cat > "$SCRIPT_DIR/docker-compose.test.yml" << EOF
services:
  backend:
    image: antikythera-backend:test
    container_name: antikythera-test-backend
    volumes:
      - $TEST_CONFIG_DIR:/root/.antikythera:ro
      - $TEST_DATA_DIR:/app/automation-ideas
    ports:
      - "8007:8006"
    networks:
      - test-network
networks:
  test-network:
    driver: bridge
EOF

    log_info "Starting backend container..."
    docker-compose -f "$SCRIPT_DIR/docker-compose.test.yml" up -d

    log_info "Waiting for health check (up to 60 seconds)..."
    for i in {1..12}; do
        if docker inspect --format='{{.State.Health.Status}}' antikythera-test-backend 2>/dev/null | grep -q "healthy"; then
            log_pass "Health check passed"
            docker-compose -f "$SCRIPT_DIR/docker-compose.test.yml" down -v
            return 0
        fi
        sleep 5
    done

    log_fail "Health check did not pass within 60 seconds"
    docker logs antikythera-test-backend 2>&1 | tail -30
    docker-compose -f "$SCRIPT_DIR/docker-compose.test.yml" down -v
}

test_api_endpoint() {
    log_section "Test 6: API Endpoint"

    # Create valid config
    cat > "$TEST_CONFIG_DIR/.env" << EOF
PORT=8006
JIRA_BASE_URL=https://test.atlassian.net
JIRA_PAT=test_token
NVIDIA_API_KEY=nvapi_test
EOF

    cat > "$SCRIPT_DIR/docker-compose.test.yml" << EOF
services:
  backend:
    image: antikythera-backend:test
    container_name: antikythera-test-backend
    volumes:
      - $TEST_CONFIG_DIR:/root/.antikythera:ro
      - $TEST_DATA_DIR:/app/automation-ideas
    ports:
      - "8007:8006"
    networks:
      - test-network
networks:
  test-network:
    driver: bridge
EOF

    log_info "Starting backend container..."
    docker-compose -f "$SCRIPT_DIR/docker-compose.test.yml" up -d
    sleep 10

    log_info "Testing API endpoint..."
    RESPONSE=$(curl -s http://localhost:8007/ 2>/dev/null || echo "")

    if echo "$RESPONSE" | grep -q "Antikythera API is running"; then
        log_pass "API endpoint responds correctly"
    else
        log_fail "API endpoint did not respond correctly"
        echo "Response: $RESPONSE"
    fi

    docker-compose -f "$SCRIPT_DIR/docker-compose.test.yml" down -v
}

test_readonly_config() {
    log_section "Test 7: Read-Only Config Mount"

    cat > "$TEST_CONFIG_DIR/.env" << EOF
PORT=8006
JIRA_BASE_URL=https://test.atlassian.net
JIRA_PAT=test_token
EOF

    cat > "$SCRIPT_DIR/docker-compose.test.yml" << EOF
services:
  backend:
    image: antikythera-backend:test
    container_name: antikythera-test-backend
    volumes:
      - $TEST_CONFIG_DIR:/root/.antikythera:ro
      - $TEST_DATA_DIR:/app/automation-ideas
    networks:
      - test-network
networks:
  test-network:
    driver: bridge
EOF

    docker-compose -f "$SCRIPT_DIR/docker-compose.test.yml" up -d
    sleep 5

    log_info "Testing read-only config mount..."
    if docker exec antikythera-test-backend sh -c "echo test >> /root/.antikythera/.env" 2>&1 | grep -q "Read-only"; then
        log_pass "Config mount is read-only"
    else
        log_fail "Config mount is writable (security issue!)"
    fi

    docker-compose -f "$SCRIPT_DIR/docker-compose.test.yml" down -v
}

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

print_summary() {
    echo ""
    echo "════════════════════════════════════════"
    echo "              TEST SUMMARY"
    echo "════════════════════════════════════════"
    echo -e "  ${GREEN}Passed:${NC}  $TESTS_PASSED"
    echo -e "  ${RED}Failed:${NC}  $TESTS_FAILED"
    echo -e "  ${YELLOW}Skipped:${NC} $TESTS_SKIPPED"
    echo "════════════════════════════════════════"

    if [ $TESTS_FAILED -gt 0 ]; then
        echo -e "\n${RED}Some tests failed!${NC}"
        return 1
    else
        echo -e "\n${GREEN}All tests passed!${NC}"
        return 0
    fi
}

# Create test directories
mkdir -p "$TEST_LOGS_DIR" "$TEST_DATA_DIR"

# Parse arguments
case "${1:-}" in
    quick)
        log_info "Running quick smoke test..."
        test_build_images
        test_health_check
        print_summary
        ;;
    build)
        log_info "Testing build only..."
        test_build_images
        print_summary
        ;;
    cleanup)
        log_info "Cleaning up..."
        docker-compose -f "$SCRIPT_DIR/docker-compose.yml" down -v 2>/dev/null || true
        docker rm -f antikythera-test-backend 2>/dev/null || true
        rm -rf "$TEST_CONFIG_DIR" "$TEST_DATA_DIR" "$TEST_LOGS_DIR" 2>/dev/null || true
        rm -f "$SCRIPT_DIR/docker-compose.test.yml" 2>/dev/null || true
        docker rmi antikythera-backend:test antikythera-ui:test 2>/dev/null || true
        log_pass "Cleanup complete"
        exit 0
        ;;
    *)
        log_section "🐳 Antikythera Docker Test Suite"
        log_info "Test directories:"
        log_info "  Config: $TEST_CONFIG_DIR"
        log_info "  Data:   $TEST_DATA_DIR"
        log_info "  Logs:   $TEST_LOGS_DIR"
        echo ""

        test_build_images
        test_config_validation_missing
        test_config_validation_empty
        test_config_validation_no_ai_key
        test_health_check
        test_api_endpoint
        test_readonly_config

        print_summary
        ;;
esac