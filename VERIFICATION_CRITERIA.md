# Hermes Project Verification Criteria (Definition of Done)

To ensure high quality and consistency across all implementation phases, every task must satisfy the following criteria before being marked as "Completed".

## 1. Implementation & Parity
- [ ] **Requirement Parity**: The implementation fully addresses all requirements specified in the Phase plan or PRD.
- [ ] **Clean Code**: The code follows the project's style guidelines (Python PEP 8) and avoids premature abstractions.
- [ ] **Security**: No hardcoded secrets, no command injection vulnerabilities, and proper input validation at boundaries.
- [ ] **Case Sensitivity & Data Integrity**: Ensure that case-sensitive identifiers (e.g., `ID-001` vs `id-001`) are preserved and handled consistently across the pipeline to avoid state mismatches.

## 2. Testing & Validation
- [ ] **Unit Tests**: New logic is covered by unit tests.
- [ ] **Test Execution**: All tests (new and existing) passed successfully.
- [ ] **Edge Cases**: Tests cover not just the "golden path" but also error states, invalid inputs, and edge cases.
- [ ] **Manual Verification**: For UI or critical flows, the feature has been manually verified (if applicable).
- [ ] **Seek Help**: If you think you need to install any tool/skill/agent, or if a specialized agent is not responding as expected, you must ask the user for guidance or alternative tools.

## 3. Quality Assurance
- [ ] **Code Review**: The code has been reviewed by a specialized agent (e.g., `ecc:python-reviewer`) or a peer.
- [ ] **Iteration**: All critical feedback from the code review has been addressed and verified.
- [ ] **Regression Check**: No existing functionality was broken by the changes.
- [ ] **Output Verification**: When using sub-agents or MCP tools, verify that the output was actually received and correctly processed, rather than assuming success based on the tool call.

## 4. Finalization
- [ ] **Documentation**: Any relevant documentation (e.g., `memory.md`, `README.md`) has been updated.
- [ ] **Permission Optimization**: Update the project's `.claude/settings.json` allowlist based on tools/commands approved during the session (using `fewer-permission-prompts` skill) to reduce future prompts.
- [ ] **Commit**: Changes are committed with a clear, descriptive commit message following the project's convention.
- [ ] **Progress Update**: The `PROGRESS.md` file is updated to reflect the current status.
- [ ] **Feedback Loop**: If any issue is found with these verification steps or the workflow, provide the details to the user and update the instructions in this file.
- [ ] **Final Sign-off**: Confirmed that every single item in this `VERIFICATION_CRITERIA.md` has been meticulously followed before marking the task or phase as complete.



---

## Workflow Sequence
Every task must follow this strict sequence without exception:
`Write Code` $\rightarrow$ `Write Tests` $\rightarrow$ `Run Tests` $\rightarrow$ `Code Review` $\rightarrow$ `Fix/Iterate` $\rightarrow$ `Commit` $\rightarrow$ `Update Progress`
