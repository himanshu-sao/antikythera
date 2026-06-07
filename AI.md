# 🤖 Antikythera Master AI Index

**Purpose**: This is the entry point for AI agents. It defines the core identity of the project and directs agents to specialized briefings based on the task.

---

## 🎯 Core Identity
Antikythera is a perpetual, human-in-the-loop, asynchronous multi-agent automation pipeline. It transforms simple ideas into technical specifications, architectures, and verified code through a gated, stage-based workflow. It has evolved into a **Cognitive Orchestration System** combining deterministic workflows with LLM-driven reasoning.

## 📚 Hierarchy of Truth (Precedence)
When information conflicts, follow this order:
1.  **`PROJECT_STATUS.md`**: The **single master document** containing project roadmap, technical baseline, architecture, verification criteria, and granular execution workflow. This is the absolute source of truth.
2.  **`README.md`**: Project overview, setup instructions, and high-level roadmap summary.
3.  **Specialized Briefings** (`docs/agents/AI.md`, `api/AI.md`, etc.): Technical depth for specific domains.

## 🗺️ Specialized Briefings
Depending on your current task, refer to the following specialized `AI.md` files for high-density technical context:

| Scope | Briefing File | Focus Area |
| :--- | :--- | :--- |
| **Agents** | `docs/agents/AI.md` | Pipeline stages, artifact specs, agent roster, and output requirements. |
| **Backend/API** | `api/AI.md` | FastAPI, `StateManager`, API routes, and integration adapters. |
| **Workflows** | `api/workflow_AI.md` | Workflow engine, trigger management, and automation logic. |
| **Frontend/UI** | `ui/AI.md` | React 19, Tailwind, Kanban board UX, and design enhancements. |

## 🛠 Global Constraints (Non-Negotiable)
- **ID Normalization**: All Idea IDs (e.g., `ID-001`) MUST be **UPPERCASE**.
- **State Integrity**: Never write to `pipeline-state.json` directly. Use the `StateManager` or the API.
- **Atomic Operations**: All file writes must be atomic (use `os.replace`).
- **Secret Management**: Never hardcode secrets. Use `.env` files or the SecretVault.
- **Idempotency**: Every agent action must be idempotent.
- **Verification**: A task is only `COMPLETED` after satisfying the **Verification Criteria** in `PROJECT_STATUS.md`.
- **6-Stage Loop**: Follow Design → Code → Unit Test → Integration Test → Sign Off → Commit.

## 📖 Recent Consolidation Notes

### June 2026 Reorganization
- **`PROJECT_STATUS.md`** is now the **single master document** containing:
  - Project roadmap & phase status
  - Technical baseline & architecture
  - Verification Criteria (Definition of Done)
  - Granular 6-stage execution workflow
  - Enhancements, remediation tasks, and Kanban notes
- **Removed files**: `PROGRESS.md`, `memory.md`, `ANTIKYTHERA_PRODUCT_SPEC.md`, `PHASE_3_5_COMPLETION.md`, `VERIFICATION_SUMMARY.md`, `FIXES.md`, `ANTIKYTHERA_SYSTEM_DOCS.md`, `VERIFICATION_CRITERIA.md`, `execution.md`
- **Agent Documentation Consolidated**:
  - Moved `executor_agent_design.md` → `docs/agents/executor-agent-design.md`
  - Created comprehensive `docs/agents/AI.md` covering all agent specifications
- **Keep**: `README.md`, `PROJECT_STATUS.md`, `AI.md`, and specialized briefings (`docs/agents/AI.md`, `api/AI.md`, `ui/AI.md`, `api/workflow_AI.md`)