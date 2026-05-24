# 🤖 Antikythera Agents Briefing

**Purpose**: High-density context for developing and maintaining the agent roster and the pipeline workflow.

---

## 🏗 The Pipeline Model
Ideas move through a linear sequence of gated stages:
`INTAKE` $\rightarrow$ `REFINEMENT` $\rightarrow$ `REVIEW_SPEC` $\rightarrow$ `ARCHITECTURE` $\rightarrow$ `REVIEW_ARCH` $\rightarrow$ `TESTING` $\rightarrow$ `REVIEW_TEST` $\rightarrow$ `APPROVED` $\rightarrow$ `EXECUTING` $\rightarrow$ `DONE`

## 👥 The Agent Roster
- **Orchestrator**: The state machine. Manages transitions and dispatches work.
- **Refiner**: Idea $\rightarrow$ `spec.md`. Focuses on requirement extraction.
- **Architect**: `spec.md` $\rightarrow$ `architecture.md`. Focuses on technical design and pattern application.
- **Tester**: `architecture.md` $\rightarrow$ `tests.md`. Focuses on verification and sandbox execution.
- **Executor**: `tests.md` $\rightarrow$ Implementation. Focuses on correct, verified code.
- **Memory**: Analyzes logs $\rightarrow$ evolves `brain/patterns.md`.

## 📄 Artifact Specifications
Agents must produce artifacts in `automation-ideas/requirements/{ID}/`:

### 1. `spec.md` (Refiner)
- **Goal**: Convert a one-liner into a detailed functional specification.
- **Must Include**: User stories, functional requirements, constraints, and acceptance criteria.

### 2. `architecture.md` (Architect)
- **Goal**: Map the spec to a technical implementation.
- **Must Include**: Component diagrams (mermaid), data flow, API signatures, and chosen patterns from `brain/patterns.md`.

### 3. `tests.md` (Tester)
- **Goal**: Define the "Definition of Done" in executable terms.
- **Must Include**: Test cases, expected results, and a validation script/plan.

## 🔄 Operational Patterns
- **HITL Regressions**: If a user edits a `spec.md` while a task is in `ARCHITECTURE`, the Orchestrator must regress the stage back to `REFINEMENT`.
- **Confidence Scoring**: Every agent must provide a confidence score (0-100). Low confidence should trigger an alert or a "Needs Revision" state.
- **Audit Logging**: Every agent action must be logged via `audit_module.log_action` for the Memory agent to analyze later.
