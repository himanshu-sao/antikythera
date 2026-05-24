Target override (optional):
- If set, use this as the ONLY implementation target for this run.
- Example: "Remediation task R5.1" or "Phase 5".
- If not set, choose automatically based on rules below.

Use SUPERPOWER-IMPLEMENT.prompt.md.

Goal:
- Select ONE best next work item (phase or remediation task group) and
  implement it end-to-end, stopping just before final verification.

Context:
- memory.md = product vision and constraints
- PROJECT_SUMMARY.md = phase structure, key decisions, and remediation tasks
- PROGRESS.md = current status, including review/verification states
- VERIFICATION_CRITERIA.md = Definition of Done
- REVIEW.md = review rules

Selection rules (in order of priority):

1) If a Target override is provided:
   - Use that phase or remediation task group as the ONLY target.

2) Otherwise, examine PROJECT_SUMMARY.md and PROGRESS.md:

   - A remediation task is considered open if its Status in PROJECT_SUMMARY.md
     is one of:
       - "Pending"
       - "In Progress"
       - "Implemented, pending review"
       - "Blocked"

   - A phase is considered a candidate for implementation if its Status in
     PROGRESS.md is one of:
       - "In Progress"
       - "Pending"
       - "Remediation In Progress"
       - "Review Failed"
       - "Completed (Unverified)"
       - "Review Pending"

   - A phase is considered fully verified and normally NOT a candidate if:
       - PROGRESS.md status is "Verified", AND
       - all remediation tasks for that phase in PROJECT_SUMMARY.md have
         Status "Verified" or "Deferred" (or there are none).

3) Choose ONE target:
   - First priority: a remediation task group (R<phase>.<index>) whose Status
     is "Pending" or "In Progress".
   - Second priority: the lowest-numbered phase whose PROGRESS.md status is
     "In Progress", "Pending", "Remediation In Progress", "Review Failed",
     "Completed (Unverified)", or "Review Pending".
   - Do NOT select a fully verified phase unless the Target override
     explicitly asks for it or there is obvious evidence of regression.

Implementation behavior:

1) For the chosen target (phase or remediation group):
   - Read the relevant parts of memory.md and PROJECT_SUMMARY.md.
   - Read the current status and notes in PROGRESS.md.
   - Read VERIFICATION_CRITERIA.md so you know what must be true before this
     work can be called complete.
   - Follow SUPERPOWER-IMPLEMENT.prompt.md exactly:
     - Plan the work as tasks of ~2–5 minutes each.
     - For each task, specify:
       - exact files to change
       - exact tests to add or update
       - exact commands to run (tests, lint, build, etc.)
       - what verification step will confirm this task is successful
     - Implement tasks one by one.
     - After each meaningful task:
       - run the relevant tests/build/lint, including Playwright tests to verify that all functionality is still working
       - self-check against VERIFICATION_CRITERIA.md where applicable
       - adjust the remaining plan if new constraints/issues are discovered.

2) Update docs (do not finalize verification):
   - PROGRESS.md:
     - Move the target’s status forward in a granular way, for example:
       - "Pending" → "In Progress"
       - "Remediation In Progress" → "Implemented, pending review"
       - "Completed (Unverified)" → "implemented, pending review"
     - Do NOT set the status to "Verified"; that is reserved for the review
       flow once VERIFICATION_CRITERIA.md is confirmed.
   - PROJECT_SUMMARY.md:
     - For phases: refine any high-level description with notes on what was
       implemented in this run.
     - For remediation tasks:
       - Update the Status field appropriately (e.g. "In Progress" →
         "Implemented, pending review").
       - Clarify Expected Fix and Verification fields if necessary based on
         what you actually implemented.

3) Do NOT mark any phase or remediation task as fully "Verified" in
   PROGRESS.md or PROJECT_SUMMARY.md:
   - Leave final verification and status upgrade to SUPERPOWER-REVIEW.

Output:
- Which target you chose (phase and/or remediation ID) and why.
- The concrete implementation plan (tasks, files, tests, commands).
- Summary of code changes performed.
- Suggested edits to PROGRESS.md (statuses + notes).
- Suggested edits to PROJECT_SUMMARY.md (phase details and remediation tasks).
- Commands and checks you ran, with pass/fail results.