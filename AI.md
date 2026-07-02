# Antikythera Master AI Index

**Purpose**: Entry point for AI agents. Start with `CLAUDE.md` for quick facts, then use the dispatch table below for domain-specific context.

---

## Specialized Briefings

| Scope | Briefing File | Focus Area |
| :--- | :--- | :--- |
| **Agents** | `docs/agents/AI.md` | Pipeline stages, artifact specs, agent roster, and output requirements |
| **Backend/API** | `api/AI.md` | FastAPI, `StateManager`, API routes, and integration adapters |
| **Workflows** | `api/workflow_AI.md` | Workflow engine, trigger management, and automation logic |
| **Frontend/UI** | `ui/AI.md` | React 19, Tailwind, Kanban board UX, and design enhancements |
| **Project Status** | `PROJECT_STATUS.md` | Roadmap, gaps, verification strategy, and pending tasks |
| **API Contract** | `docs/api-spec.md` | REST endpoint schemas, request/response formats |

## Global Constraints (Non-Negotiable)
- **ID Normalization**: All Idea IDs (e.g., `ID-001`) MUST be **UPPERCASE**.
- **State Integrity**: Never write to `pipeline-state.json` directly. Use the `StateManager` API or `WorkflowStateManager` facade.
- **Atomic Operations**: All file writes must be atomic (use `os.replace`). Enforced by `BaseJSONManager._save()`.
- **Secret Management**: Never hardcode secrets. Use `.env` files (symlinked from `~/.antikythera/.env`). The `SecretVault` exists but is currently unused.
- **Idempotency**: Every agent action must be idempotent.
- **Verification**: A task is only `COMPLETED` after satisfying the verification criteria in `PROJECT_STATUS.md`.
- **6-Stage Loop**: Follow Design → Code → Unit Test → Integration Test → Sign Off → Commit.
- **Legacy Code**: Do not use `api/state_manager.py` (legacy). Use `api/workflow_state_manager.py` → `api/managers/` hierarchy.
