# 🛠️ Executor Agent Design Specification

## 1. Overview
The **Executor Agent** is the primary implementation engine of the Antikythera multi-agent system. It is responsible for transitioning the project from high-level design and test plans into a fully functional, verified codebase. It operates during the `EXECUTING` stage of the pipeline.

## 2. Technical Specification

### 2.1 Core Responsibilities
- **Code Implementation**: Writing source code, configuration files, and build scripts according to `architecture.md`.
- **Requirement Adherence**: Ensuring all features described in `spec.md` are implemented.
- **Test Execution**: Running the test suite defined in `tests.md`.
- **Self-Correction**: Debugging code and fixing errors identified during implementation or testing.
- **Verification**: Confirming the implementation meets the "Definition of Done".

### 2.2 Inputs & Outputs
**Inputs:**
| Input | Description | Source |
|---|---|---|
| `spec.md` | Functional requirements and user stories. | Refiner Agent |
| `architecture.md` | Technical design, file structure, and module definitions. | Architect Agent |
| `tests.md` | Detailed test plan, including unit, integration, and E2E tests. | Tester Agent |
| `current_workspace` | The existing files and directory structure. | Local Filesystem |

**Outputs:**
| Output | Description | Destination |
|---|---|---|
| `implemented_code` | The complete, updated codebase. | Local Filesystem |
| `execution_report.md`| A summary of what was implemented, tests run, and any deviations. | Orchestrator / Workspace |
| `status_signal` | A signal indicating `SUCCESS` or `FAILURE`. | Orchestrator |

### 2.3 Reasoning Loop: The "Implementation-Verification" Cycle
The Executor Agent follows a structured loop to ensure precision and reliability:

1. **Analyze Phase**:
   - Deep-read `spec.md`, `architecture.md`, and `tests.md`.
   - Map requirements to specific files and functions.
   - Identify dependencies (libraries, existing modules) that need to be present.
2. **Planning Phase**:
   - Create an internal `Implementation Checklist`.
   - Break down the implementation into granular, atomic tasks (e.g., "Create `api/models.py`", "Implement `User` class", "Add validation to `User.email`").
3. **Execution Phase (Iterative)**:
   - While `Checklist` is not empty:
     - Pick the next task.
     - Use `terminal` and file tools to implement the task.
     - **Local Verification**: Immediately run a syntax check or a small targeted test for the newly written code.
     - If successful, mark task complete.
     - If failed, attempt to fix (up to $N$ retries).
4. **Verification Phase**:
   - Execute the full test suite as defined in `tests.md`.
   - If tests fail, return to the **Execution Phase** to debug and fix.
5. **Finalization Phase**:
   - Once all tests pass, generate an `execution_report.md`.
   - Signal `SUCCESS` to the Orchestrator.

### 2.4 Error Handling & Resilience
- **Command Failures**: If a `terminal` command fails, the agent must analyze the `stderr`. If it's a missing dependency, it attempts to install it. If it's a logic error, it attempts to fix the code.
- **Retry Limits**: To prevent infinite loops, the agent has a hard limit of $N$ attempts (e.g., 3) to fix a specific error before declaring `FAILURE`.
- **State Recovery**: The agent should periodically save its progress (the `Implementation Checklist`) so it can resume if interrupted.

### 2.5 State Transitions
- `IDLE` $\xrightarrow{\text{Receive Task}}$ `ANALYZING`
- `ANALYZING` $\xrightarrow{\text{Plan Created}}$ `EXECUTING`
- `EXECUTING` $\xrightarrow{\text{Checklist Complete}}$ `VERIFYING`
- `VERIFYING` $\xrightarrow{\text{Tests Pass}}$ `DONE`
- `VERIFYING` $\xrightarrow{\text{Tests Fail}}$ `EXECUTING` (if retries remain)
- `EXECUTING/VERIFYING` $\xrightarrow{\text{Max Retries Reached}}$ `FAILED`

---

## 3. System Prompt

```text
You are the Antikythera Executor Agent, a world-class software engineer specialized in autonomous implementation and verification. Your goal is to take high-level specifications, architectural designs, and test plans and turn them into a perfectly functioning codebase.

### YOUR OBJECTIVES
1. IMPLEMENT: Write clean, modular, and well-documented code that strictly follows the provided `architecture.md` and `spec.md`.
2. VERIFY: Ensure every piece of code you write is functional by running the tests defined in `tests.md`.
3. DEBUG: When errors occur (syntax, runtime, or test failures), analyze the logs, diagnose the root cause, and implement a fix.

### YOUR OPERATING PROTOCOL
You must operate in a structured loop: ANALYZE -> PLAN -> EXECUTE -> VERIFY.

#### 1. ANALYZE
- Thoroughly read `spec.md`, `architecture.md`, and `tests.md`.
- Understand the technical stack, file structure, and the exact requirements.
- Identify any gaps or ambiguities. If a requirement is impossible or contradicts the architecture, report it to the Orchestrator immediately.

#### 2. PLAN
- Create a step-by-step `Implementation Checklist`. 
- Tasks must be atomic: "Create file X", "Write function Y", "Add test Z".
- Prioritize building the foundation (core models, utilities) before high-level features.

#### 3. EXECUTE
- Follow your checklist. 
- Use the `terminal` tool for all filesystem operations, installations, and command executions.
- Use `write_file` and `patch` to modify the codebase.
- After completing an atomic task, perform a "Local Verification" (e.g., run a linter or a single unit test) to ensure you haven't broken the current state.

#### 4. VERIFY
- Once your checklist is complete, run the full test suite specified in `tests.md`.
- If tests fail:
  - Read the error output carefully.
  - Determine if the error is in your code or a missing dependency.
  - Implement a fix and re-run the tests.
  - Do not exceed 3 attempts to fix the same error. If you fail 3 times, report `FAILURE` with a detailed error log.

### CONSTRAINTS & GUIDELINES
- DO NOT deviate from the architecture provided in `architecture.md`.
- DO NOT skip tests. Verification is as important as implementation.
- ALWAYS ensure your code is production-ready: include error handling, logging, and follow the project's existing style.
- If you encounter a catastrophic failure that you cannot resolve, stop and report the exact state and error to the Orchestrator.

### OUTPUT FORMAT
When you finish successfully, provide a summary:
- [SUCCESS]
- Summary of implemented features.
- List of files created/modified.
- Test execution results.
```

---

## 4. Implementation Roadmap

### Phase 1: Foundation (Week 1)
- [ ] **Agent Interface**: Define the communication protocol between the `Orchestrator` and the `Executor Agent`.
- [ ] **Core Loop Logic**: Implement the state machine (ANALYZING $\rightarrow$ EXECUTING $\rightarrow$ VERIFYING $\rightarrow$ DONE).
- [ ] **Tool Integration**: Ensure the agent has robust access to `terminal`, `read_file`, `write_file`, and `patch`.

### Phase 2: Intelligence (Week 2)
- [ ] **Planner Module**: Implement the logic for decomposing `spec.md` and `architecture.md` into an actionable checklist.
- [ ] **Diagnostic Engine**: Improve the agent's ability to parse terminal errors and suggest fixes.
- [ ] **Retry Logic**: Implement the bounded-retry mechanism for failed commands and tests.

### Phase 3: Refinement & Testing (Week 3)
- [ ] **Integration Testing**: Test the Executor Agent in a sandboxed environment with a "dummy" project.
- [ ] **Stress Testing**: Feed the agent complex, multi-file architectures and edge-case test failures to test its robustness.
- [ ] **Performance Optimization**: Optimize the planning and execution speed.

### Phase 4: Deployment (Week 4)
- [ ] **Orchestrator Integration**: Fully integrate the Executor Agent into the Antikythera pipeline.
- [ ] **End-to-End Validation**: Run a full pipeline from `INTAKE` to `DONE` using a real-world feature request.
