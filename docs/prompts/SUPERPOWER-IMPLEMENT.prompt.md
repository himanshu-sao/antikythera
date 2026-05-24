# SUPERPOWER-IMPLEMENT.prompt.md

Use Superpowers implementation workflow for a single phase or remediation task group.

Context:
- memory.md = product vision and constraints
- PROJECT_SUMMARY.md = phase structure, key decisions, and remediation tasks
- PROGRESS.md = current status (done / in progress / pending / review-related)
- VERIFICATION_CRITERIA.md = required checks (Definition of Done)
- REVIEW.md = review rules

Task:
1. Select one explicit work target from PROJECT_SUMMARY.md + PROGRESS.md:
   - Prefer, in order:
     a) A remediation task group created by review that is marked as pending
        or "Remediation In Progress".
     b) The lowest-numbered phase that is "In Progress" or "Pending".
   - Only re-open fully verified phases if the user explicitly asks or if there
     is clear evidence that something regressed.

2. For the chosen phase or remediation task group:
   - Read the relevant sections in memory.md and PROJECT_SUMMARY.md.
   - Read the current status and notes in PROGRESS.md.
   - Read VERIFICATION_CRITERIA.md so you know what must be true before the work
     can be called complete.

3. Use Superpowers planning skills to write an implementation plan:
   - Break work into tasks of roughly 2–5 minutes each.
   - For each task, specify:
     - exact files to change (paths and main functions/components)
     - exact tests to add or update
     - exact commands to run (tests, lint, build, etc.)
     - what verification step will confirm that this task is successful
   - If the work involves the Kanban UI (Phases 5 or 6), align tasks with the
     UI behavior described in memory.md (columns, card fields, drag/drop,
     review integration, etc.).

4. Use Superpowers execution skills to implement the plan task-by-task:
   - After each meaningful task:
     - run the relevant tests/build/lint commands
     - self-check against VERIFICATION_CRITERIA.md where applicable
     - adjust the remaining plan if you discover new constraints or issues

5. When the tasks for this target are implemented and tests pass:
   - Update PROGRESS.md to reflect the new reality, using granular statuses
     such as:
       - "implemented, pending review"
       - "Remediation In Progress"
       - "Review Pending"
   - If the task breakdown in PROJECT_SUMMARY.md was missing or unclear:
     - update or annotate the phase/remediation section to reflect how the work
       is now structured and what remains.

6. Do NOT mark the phase or remediation group as fully "Completed" or
   "Verified" in PROGRESS.md:
   - Leave final completion status to the SUPERPOWER-REVIEW workflow, which
     will check against VERIFICATION_CRITERIA.md and apply REVIEW.md rules.

Output:
- A concrete implementation plan with tasks, files, tests, and commands
- A summary of code changes performed
- Suggested edits to PROGRESS.md and PROJECT_SUMMARY.md
- Commands and checks you ran, with pass/fail results
