# Task 5.3: E2E Validation Test Plan

**Status:** PENDING (Requires running backend)  
**Date:** 2026-06-02

## Objective
Validate the complete end-to-end flow of the Low-Code AI Compiler:
1. Record a Path via Automation Studio
2. Promote the Path to a Pipeline
3. Configure Cron schedule
4. Execute the pipeline
5. Verify results in Execution History dashboard

---

## Prerequisites

### Running Services
- [ ] Backend API running on `http://localhost:8000`
- [ ] Frontend dev server running on `http://localhost:5173`
- [ ] Database/storage initialized

### Test Data
- [ ] At least one external service configured (Jira or GitHub adapter)
- [ ] Valid API credentials in vault

---

## Test Scenario: Complete Automation Pipeline

### Phase 1: Record a Path (Studio → Path)

**Step 1.1: Open Automation Studio**
- Navigate to http://localhost:5173
- Click "Automation Studio" tab
- **Expected:** Studio interface loads with split-screen view

**Step 1.2: Create New Automation**
- Click "New Recording" or similar button
- Enter instruction: "Fetch Jira ticket PROJ-123 and update status to 'In Progress'"
- **Expected:** AI proposes a PathStep configuration

**Step 1.3: Review Proposed Step**
- Examine the proposed step in the preview panel
- Should show:
  ```json
  {
    "operator_id": "fetch_resource",
    "adapter_id": "jira_adapter",
    "config": { "resource_id": "PROJ-123" },
    "input_ref": null,
    "output_ref": "ticket_data"
  }
  ```
- **Expected:** Step preview shows valid configuration

**Step 1.4: Execute Step in Sandbox**
- Click "Play" or "Test Step" button
- **Expected:** 
  - API call made to Jira
  - Result displayed in right panel
  - `ticket_data` variable stored in session state

**Step 1.5: Add Second Step**
- New instruction: "Update the ticket status"
- AI proposes update step with `input_ref: "ticket_data"`
- Click "Save" to append to path
- **Expected:** Path timeline shows 2 steps

**Step 1.6: Finalize Path**
- Click "Save Path" or "Promote to Pipeline"
- Enter path name: "Update Jira Status"
- **Expected:** Path saved, ready for promotion

---

### Phase 2: Promote to Pipeline

**Step 2.1: Promotion Dialog**
- In promotion dialog, enter:
  - Pipeline name: "Jira Status Automation"
  - Description: "Automatically update Jira ticket status"
  - Trigger type: "CRON"
  - Cron expression: "0 */2 * * *" (every 2 hours)
- **Expected:** Promotion request sent to backend

**Step 2.2: Backend Processing**
- Check backend logs or API response
- **Expected:** 
  - `POST /api/pipelines/promote` returns `{ pipeline_id, path_ids }`
  - Pipeline status: "ACTIVE"

**Step 2.3: Verify Pipeline Created**
- New tab appears in navigation bar with pipeline name
- Click the new tab
- **Expected:** Pipeline Dashboard loads with:
  - Visual flowchart showing 2 nodes
  - Status badge: "ACTIVE"
  - Trigger badge: "CRON"

---

### Phase 3: Configure & Verify Pipeline

**Step 3.1: Review Flowchart**
- In Visual Workflow section
- **Expected:**
  - Two nodes connected by arrows
  - Node 1: "fetch_resource" (Jira adapter)
  - Node 2: "update_resource" (Jira adapter)
  - Color-coded by adapter type

**Step 3.2: Review Path Details**
- In Path Details section
- **Expected:**
  - Step 1: `fetch_resource` via `jira_adapter`
  - Step 2: `update_resource` via `jira_adapter`
  - Correct input/output references

**Step 3.3: Check Execution History (Empty)**
- In Run History section
- **Expected:** "No runs yet" message displayed

---

### Phase 4: Execute Pipeline

**Step 4.1: Trigger Manual Run**
- Click "Run Now" button in Run History panel
- **Expected:**
  - Toast notification: "Pipeline triggered"
  - New run appears in history with status "RUNNING"

**Step 4.2: Monitor Execution**
- Wait 5-10 seconds
- Refresh run history or watch for auto-update
- **Expected:**
  - Run status changes: RUNNING → SUCCESS (or FAILED)
  - Duration displayed
  - Logs populated

**Step 4.3: View Execution Logs**
- Click on the run to expand details
- **Expected to see:**
  ```
  14:23:45 [INFO] Pipeline execution started: Jira Status Automation
  14:23:46 [INFO] Executing fetch_resource via jira_adapter
  14:23:47 [INFO] Step completed successfully
  14:23:47 [INFO] Executing update_resource via jira_adapter
  14:23:48 [INFO] Step completed successfully
  14:23:48 [INFO] Pipeline execution succeeded
  ```

**Step 4.4: Verify External System**
- Check Jira ticket PROJ-123
- **Expected:** Ticket status updated to "In Progress"

---

### Phase 5: Verify Dashboard Updates

**Step 5.1: Check Execution History Panel**
- **Expected:**
  - Run list shows the new execution
  - Status badge: green (SUCCESS) or red (FAILED)
  - Duration: ~3 seconds
  - Timestamp: recent

**Step 5.2: Expand Run Details**
- **Expected:**
  - Full metadata displayed (run_id, pipeline_id, duration)
  - Complete log entries visible
  - No errors in console

**Step 5.3: Test Failed Execution (Optional)**
- Modify path with invalid resource_id
- Trigger run
- **Expected:**
  - Run status: FAILED
  - Error message displayed
  - Failure point highlighted: "Step 1: fetch_resource"
  - Red error banner with error details

---

## Phase 6: Cron Schedule Verification

**Step 6.1: Wait for Scheduled Execution**
- Note: Cron runs every 2 hours in our test config
- For testing, temporarily change cron to "*/1 * * * *" (every minute)
- Wait up to 2 minutes
- **Expected:** New run appears automatically (no manual trigger)

**Step 6.2: Verify Scheduled Run**
- Check run details
- **Expected:**
  - Status: SUCCESS
  - Trigger source: "CRON" (if tracked)
  - Same behavior as manual trigger

---

## Success Criteria

### All Tests Must Pass
- [ ] Path can be recorded via Studio
- [ ] Path successfully promoted to Pipeline
- [ ] Pipeline appears as new tab in navigation
- [ ] Flowchart renders correctly with proper nodes/edges
- [ ] Manual execution triggers pipeline
- [ ] Execution logs captured correctly
- [ ] External system (Jira/GitHub) updated as expected
- [ ] Execution History shows accurate status and logs
- [ ] Cron trigger executes automatically (if tested)
- [ ] Failed executions are properly logged and highlighted
- [ ] No console errors during any step
- [ ] UI is responsive and usable

---

## Failure Scenarios & Expected Behavior

### Scenario A: API Timeout
- **Trigger:** Slow network, API downtime
- **Expected:** 
  - Timeout error in UI
  - Toast notification: "Request failed"
  - Run status: FAILED
  - Error log: "Connection timeout after 30s"

### Scenario B: Invalid Credentials
- **Trigger:** Wrong API token in vault
- **Expected:**
  - 401/403 error from adapter
  - Run status: FAILED
  - Error message: "Authentication failed"
  - Clear guidance to check credentials

### Scenario C: Invalid Path Configuration
- **Trigger:** Broken input_ref reference
- **Expected:**
  - Step fails at execution
  - Error: "Input reference not found in state"
  - Pipeline marked as failed
  - Lock inzichto error step

### Scenario D: Partial Execution Failure
- **Trigger:** Step 1 succeeds, Step 2 fails
- **Expected:**
  - Run status: FAILED
  - Step 1: SUCCESS in logs
  - Step 2: ERROR in logs
  - Failure point: "Step 2"
  - No rollback of Step 1 (for this implementation)

---

## Test Data Cleanup

After testing, clean up test data:
```bash
# Option 1: Delete via UI
- Navigate to Pipeline tab
- Look for "Delete Pipeline" button (if exists)
- Confirm deletion

# Option 2: Direct API call
curl -X DELETE http://localhost:8000/api/pipelines/{pipeline_id}

# Option 3: Clear in-memory store
- Restart backend (if using in-memory DB)
```

---

## Automated Test Script

See `e2e-test-script.sh` for automated execution of these steps.

---

## Notes for Reviewers

1. **Test Environment:** Ensure backend uses test/sandbox environment, not production
2. **Rate Limits:** Be aware of API rate limits when running multiple tests
3. **Concurrency:** Only one test runner at a time to avoid state conflicts
4. **Logging:** Keep browser console open during tests to catch JavaScript errors
5. **Network Tab:** Use browser DevTools Network tab to verify API calls

---

**Last Updated:** 2026-06-02  
**Test Plan Status:** READY FOR EXECUTION  
**Blocker:** Backend API must be running with proper dependencies installed