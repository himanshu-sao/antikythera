# Hermes Project Verification Criteria (Definition of Done)

To ensure high quality and consistency across all implementation phases, every task must satisfy the following criteria before being marked as "Completed".

## 1. Implementation & Parity
- [ ] **Requirement Parity**: The implementation fully addresses all requirements specified in the Phase plan or PRD.
- [ ] **Clean Code**: The code follows the project's style guidelines (Python PEP 8) and avoids premature abstractions.
- [ ] **Security**: No hardcoded secrets, no command injection vulnerabilities, and proper input validation at boundaries.

## 2. Testing & Validation
- [ ] **Unit Tests**: New logic is covered by unit tests.
- [ ] **Test Execution**: All tests (new and existing) passed successfully.
- [ ] **Edge Cases**: Tests cover not just the "golden path" but also error states and edge cases.
- [ ] **Manual Verification**: For UI or critical flows, the feature has been manually verified (if applicable).
- [ ] **Seek Help**: If you think you need to install any tool/skill/agent, you can ask for it and install it.

## 3. Quality Assurance
- [ ] **Code Review**: The code has been reviewed by a specialized agent (e.g., `ecc:python-reviewer`) or a peer.
- [ ] **Iteration**: All critical feedback from the code review has been addressed and verified.
- [ ] **Regression Check**: No existing functionality was broken by the changes.

## 4. Finalization
- [ ] **Documentation**: Any relevant documentation (e.g., `memory.md`, `README.md`) has been updated.
- [ ] **Commit**: Changes are committed with a clear, descriptive commit message following the project's convention.
- [ ] **Progress Update**: The `PROGRESS.md` file is updated to reflect the current status.
- [ ] **Fixing the issue**: If you found any issue with these steps, provide the details to the user and update the instructions on this file.

---

## Workflow Sequence
Every task must follow this strict sequence:
`Write Code` $\rightarrow$ `Write Tests` $\rightarrow$ `Run Tests` $\rightarrow$ `Code Review` $\rightarrow$ `Fix/Iterate` $\rightarrow$ `Commit` $\rightarrow$ `Update Progress`
