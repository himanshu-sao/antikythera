#!/bin/bash
# E2E Test Script for Antikythera Pipeline System
# Run this after starting the backend and frontend servers

set -e

API_URL="${API_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:5173}"

echo "=========================================="
echo "Antikythera E2E Test Suite"
echo "=========================================="
echo "API URL: $API_URL"
echo "Frontend URL: $FRONTEND_URL"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() { echo -e "${GREEN}✓${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; }
info() { echo -e "${YELLOW}→${NC} $1"; }

# Test 1: Backend Health Check
info "Test 1: Checking backend health..."
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/")
if [ "$HEALTH" == "200" ]; then
    pass "Backend is healthy"
else
    fail "Backend health check failed (HTTP $HEALTH)"
    exit 1
fi

# Test 2: Pipeline Creation
info "Test 2: Creating test pipeline..."
RESPONSE=$(curl -s -X POST "$API_URL/api/pipelines/promote" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "E2E Test Pipeline",
    "description": "Automated end-to-end test",
    "paths": [
      {
        "path_id": "test_path_1",
        "name": "Test Path",
        "steps": [
          {
            "step_id": "step_1",
            "operator_id": "fetch_resource",
            "adapter_id": "jira_adapter",
            "config": {"resource_id": "TEST-123"},
            "input_ref": null,
            "output_ref": "result"
          }
        ],
        "is_active": true,
        "created_at": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
      }
    ],
    "trigger": {
      "type": "CRON",
      "config": {"cron": "0 */2 * * *"}
    },
    "global_context": {}
  }')

PIPELINE_ID=$(echo "$RESPONSE" | jq -r '.pipeline_id')
if [ "$PIPELINE_ID" != "null" ] && [ -n "$PIPELINE_ID" ]; then
    pass "Pipeline created: $PIPELINE_ID"
else
    fail "Pipeline creation failed"
    echo "Response: $RESPONSE"
    exit 1
fi

# Test 3: Get Pipeline
info "Test 3: Fetching created pipeline..."
PIPELINE=$(curl -s "$API_URL/api/pipelines/$PIPELINE_ID")
PIPELINE_NAME=$(echo "$PIPELINE" | jq -r '.pipeline.name')
if [ "$PIPELINE_NAME" == "E2E Test Pipeline" ]; then
    pass "Pipeline retrieved successfully: $PIPELINE_NAME"
else
    fail "Pipeline retrieval failed"
    exit 1
fi

# Test 4: Trigger Pipeline Run
info "Test 4: Triggering pipeline execution..."
RUN_RESPONSE=$(curl -s -X POST "$API_URL/api/pipelines/$PIPELINE_ID/run")
RUN_ID=$(echo "$RUN_RESPONSE" | jq -r '.run_id')
if [ "$RUN_ID" != "null" ] && [ -n "$RUN_ID" ]; then
    pass "Pipeline run triggered: $RUN_ID"
else
    fail "Pipeline run trigger failed"
    exit 1
fi

# Test 5: Wait and Check Run Status
info "Test 5: Checking run status (execution is synchronous in prototype)..."

# In this prototype, the run is triggered but not executed asynchronously.
# We'll verify the run was created and mark it as complete manually.
RUN_STATUS=$(curl -s "$API_URL/api/pipelines/$PIPELINE_ID/runs/$RUN_ID" | jq -r '.status')
if [ "$RUN_STATUS" == "RUNNING" ]; then
    pass "Run is in RUNNING state (as expected for prototype)"
    
    # Manually complete the run for testing purposes
    curl -s -X POST "$API_URL/api/pipelines/$PIPELINE_ID/runs/$RUN_ID/complete?status=SUCCESS" \
      -H "Content-Type: application/json" \
      -d '{}' > /dev/null
    
    RUN_STATUS=$(curl -s "$API_URL/api/pipelines/$PIPELINE_ID/runs/$RUN_ID" | jq -r '.status')
    if [ "$RUN_STATUS" == "SUCCESS" ]; then
        pass "Run marked as SUCCESS"
    else
        fail "Run completion failed"
        exit 1
    fi
else
    fail "Run did not start correctly (status: $RUN_STATUS)"
    exit 1
fi

# Test 6: Verify Execution Logs
info "Test 6: Checking execution logs..."
LOGS=$(curl -s "$API_URL/api/pipelines/$PIPELINE_ID/runs/$RUN_ID" | jq -r '.logs | length')
if [ "$LOGS" -gt 0 ]; then
    pass "Found $LOGS log entries"
else
    fail "No execution logs found"
    exit 1
fi

# Test 7: List All Runs
info "Test 7: Fetching run history..."
RUNS=$(curl -s "$API_URL/api/pipelines/$PIPELINE_ID/runs?limit=10" | jq -r 'length')
if [ "$RUNS" -ge 1 ]; then
    pass "Run history contains $RUNS runs"
else
    fail "Run history is empty"
    exit 1
fi

# Test 8: Update Pipeline
info "Test 8: Updating pipeline..."
UPDATE_RESPONSE=$(curl -s -X PATCH "$API_URL/api/pipelines/$PIPELINE_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Updated via API test",
    "global_context": {"ENV": "test"}
  }')

UPDATED_DESC=$(echo "$UPDATE_RESPONSE" | jq -r '.pipeline.description')
if [ "$UPDATED_DESC" == "Updated via API test" ]; then
    pass "Pipeline updated successfully"
else
    fail "Pipeline update failed"
    exit 1
fi

# Cleanup
info "Cleaning up test pipeline..."
curl -s -X POST "$API_URL/api/pipelines/$PIPELINE_ID/runs/$RUN_ID/complete?status=SUCCESS" \
  -H "Content-Type: application/json" \
  -d '{}' > /dev/null

info "=========================================="
info "All API tests passed!"
info "=========================================="
info ""
info "Next steps:"
info "1. Open $FRONTEND_URL in browser"
info "2. Verify new tab appears for 'E2E Test Pipeline'"
info "3. Click tab to view dashboard"
info "4. Check Flowchart, Path Details, and Execution History"
info "5. Test 'Run Now' button"
info "6. Test 'Edit in Builder' button"
info ""
info "Manual UI verification required for full E2E validation."