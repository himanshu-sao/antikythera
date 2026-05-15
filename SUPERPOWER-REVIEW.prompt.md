# SUPERPOWER-REVIEW.prompt.md

Use Superpowers review workflow for a single phase or remediation task group.

Context:
- memory.md = product vision and intent
- PROJECT_SUMMARY.md = defined phases, key decisions, and remediation tasks
- PROGRESS.md = claimed status for each phase
- VERIFICATION_CRITERIA.md = completion gate (Definition of Done)
- REVIEW.md = review rules

This prompt supports two modes:
- Audit mode: explicitly review a given phase, even if PROGRESS.md says it is completed.
- Loop mode: review the most recent work that is “implemented, pending review” or similar.

Task:
1. Determine the review target:
   - If the user explicitly specifies a phase (e.g., "Phase 2"), review that phase
     in audit mode, even if PROGRESS.md currently shows ✅ Completed.
   - Otherwise, identify the lowest-numbered phase or remediation task group that
     is in a review-related status in PROGRESS.md, such as:
       - "implemented, pending review"
       - "Review Pending"
       - "Review Failed"
       - "Remediation In Progress"
     and use that as the review target.

2. For the selected phase or remediation task group:
   - Review implementation against memory.md and the phase description in
     PROJECT_SUMMARY.md.
   - Review any remediation tasks recorded for that phase in PROJECT_SUMMARY.md.
   - Check PROGRESS.md claims against the actual code and tests.
   - Evaluate completion strictly against VERIFICATION_CRITERIA.md.

3. Build a structured checklist for that phase:
   - For each requirement or task (original or remediation):
     - requirement/task ID or description
     - status:
       - implemented and verified
       - implemented but verification missing/failed
       - partially implemented
       - not implemented
       - implemented but contradicting spec/vision
     - evidence (files, functions, tests)
     - verification notes

4. Update or propose edits to project docs:
   - PROGRESS.md:
     - Mark a phase/task as fully complete / verified ONLY if all relevant items
       in VERIFICATION_CRITERIA.md have been satisfied (implementation parity,
       tests, review, regression check, docs, progress update, etc.).
     - Otherwise, set a more accurate granular status such as:
       - "implemented, verification pending"
       - "Review Failed"
       - "Remediation In Progress"
       - "Review Pending"
   - PROJECT_SUMMARY.md:
     - Under the remediation section for that phase, add or refine remediation
       tasks when you discover missing scope, ambiguous behavior, or defects.
     - Allow breaking a phase into multiple smaller remediation items if that
       makes implementation and future review clearer.

5. Produce a list of new or revised tasks that should feed into the next
   SUPERPOWER-IMPLEMENT run:
   - Group tasks by phase and remediation ID.
   - Make tasks small (2–5 minutes of focused work) and verifiable.
   - Link each task back to the requirement or defect it addresses.

6. Clearly distinguish in your findings:
   - spec compliance issues (mismatches with memory.md or PROJECT_SUMMARY.md)
   - verification/test gaps (missing or failing tests, missing manual checks)
   - progress/documentation inaccuracies (PROGRESS.md not matching reality)
   - pure code-quality suggestions (nits, refactors, style improvements)

Output:
- Phase or remediation review summary:
  - Vision alignment: pass/fail
  - Scope and phase compliance: pass/fail
  - PROGRESS.md accuracy: pass/fail
  - Verification criteria: pass/fail
- A detailed checklist of requirements/tasks with status and evidence
- Diff-style suggestions for PROGRESS.md and PROJECT_SUMMARY.md
- A prioritized list of follow-up tasks for SUPERPOWER-IMPLEMENT
- Important vs Nit findings, clearly labeled
