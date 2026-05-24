Target override (optional):
- If set, use this as the ONLY review target for this run.
- Example: "Phase 1" or "Remediation task R5.1".
- If not set, choose automatically based on rules below.

Use SUPERPOWER-REVIEW.prompt.md.

Goal:
- Select ONE best review target (phase or remediation task group),
  review it end-to-end against spec and verification criteria, and update
  PROJECT_SUMMARY.md and PROGRESS.md with concrete issues and tasks.

Context:
- memory.md = product vision and intent
- PROJECT_SUMMARY.md = defined phases, key decisions, and remediation tasks
- PROGRESS.md = claimed status for each phase
- VERIFICATION_CRITERIA.md = Definition of Done (completion gate)
- REVIEW.md = review rules

Status interpretation:

- A remediation task is considered OPEN if its Status in PROJECT_SUMMARY.md
  is one of:
    - "Pending"
    - "In Progress"
    - "Implemented, pending review"
    - "Blocked"

- A remediation task is considered CLOSED if its Status is:
    - "Verified"
    - "Deferred"

- A phase is considered fully VERIFIED if:
    - PROGRESS.md status for that phase is "Verified", AND
    - there are no remediation tasks for that phase in PROJECT_SUMMARY.md
      with Status other than "Verified" or "Deferred".

- A phase is considered IMPLEMENTED BUT UNREVIEWED if:
    - PROGRESS.md status is "Completed (Unverified)" or "Review Pending".

- A phase is considered PARTIALLY REVIEWED if:
    - PROGRESS.md status is "Review Failed" or "Remediation In Progress", OR
    - there exists at least one OPEN remediation task for that phase.

Selection rules (in order of priority):

1) If a Target override is provided:
   - Use that phase or remediation group as the ONLY review target,
     even if PROGRESS.md says it is Completed or Verified.

2) Otherwise, examine PROGRESS.md and PROJECT_SUMMARY.md:

   - First priority: a phase or remediation group that is PARTIALLY REVIEWED
     (i.e., has status "Review Failed" or "Remediation In Progress", or has
     OPEN remediation tasks).
   - Second priority: a phase that is IMPLEMENTED BUT UNREVIEWED
     ("Completed (Unverified)" or "Review Pending").
   - Third priority: if everything is VERIFIED and has no OPEN remediation
     tasks, do nothing unless a Target override explicitly asks for re-review.

3) Do NOT select phases that are fully VERIFIED unless:
   - There is clear evidence of regression from the code/tests/docs, or
   - The Target override explicitly asks for that phase.

Review behavior for the chosen target:

1) Follow SUPERPOWER-REVIEW.prompt.md:

   - Compare implementation against:
     - memory.md (vision, structure, behavior)
     - PROJECT_SUMMARY.md (phase description + existing remediation tasks)
     - PROGRESS.md (status claims and notes)
     - VERIFICATION_CRITERIA.md (Definition of Done)
     - REVIEW.md (priorities and severity rules)

   - Build a checklist of requirements/tasks for this target with:
     - requirement or task ID/description
     - status:
       - implemented and verified
       - implemented but verification missing/failed
       - partially implemented
       - not implemented
       - implemented but contradicting spec/vision
     - evidence (files, functions, tests)
     - verification notes.

2) Update PROJECT_SUMMARY.md:

   - Under the appropriate "Phase X Remediation Tasks" section:
     - Add NEW remediation tasks for any gaps, contradictions, missing scope,
       or verification failures discovered.
       - Use IDs like R<phase>.<index> (e.g., R1.1, R5.2).
       - For each remediation task, include:
         - Status (Pending / In Progress / Implemented, pending review /
           Verified / Deferred / Blocked).
         - Short issue summary.
         - Why this is an issue (spec mismatch, missing test, regression, etc.).
         - Expected Fix (what must change in code/tests/docs).
         - Verification (exact tests, commands, or manual checks required).
     - Refine existing remediation tasks:
       - Update Status if work has been implemented/verified.
       - Tighten descriptions and verification steps based on findings.

3) Update PROGRESS.md:

   - Adjust the phase status to reflect current reality:
     - If implementation is done but verification has open issues:
       - Use statuses like "Review Failed" or "Remediation In Progress".
     - If implementation is done and only review remains:
       - Use "Review Pending".
     - If implementation + verification now satisfy all relevant items in
       VERIFICATION_CRITERIA.md and there are no OPEN remediation tasks:
       - Set status to "Verified".
   - Update Notes to briefly explain:
     - What was reviewed.
     - What is still missing (if anything).
     - Which remediation IDs (if any) are relevant.

4) Produce follow-up tasks for implementation:

   - Derive a prioritized list of tasks that should feed into
     SUPERPOWER-IMPLEMENT:
     - Group them by phase and remediation ID.
     - Make each task small (2–5 minutes) and verifiable.
     - Reference:
       - the remediation IDs (R<phase>.<index>),
       - the files/functions involved, and
       - the verification steps required.

Output:
- Which target you chose (phase and/or remediation ID) and why.
- Phase/remediation review summary:
  - Vision alignment: pass/fail
  - Scope and phase compliance: pass/fail
  - PROGRESS.md accuracy: pass/fail
  - VERIFICATION_CRITERIA.md satisfaction: pass/fail
- Checklist of requirements/tasks with status and evidence.
- Diff-style descriptions of recommended changes to:
  - PROJECT_SUMMARY.md (remediation tasks, statuses, descriptions).
  - PROGRESS.md (phase statuses and notes).
- A prioritized list of follow-up tasks for SUPERPOWER-IMPLEMENT.
- Important vs Nit findings, clearly labeled.