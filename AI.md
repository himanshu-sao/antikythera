# 🤖 Antikythera Master AI Index

**Purpose**: This is the entry point for AI agents. It defines the core identity of the project and directs agents to specialized briefings based on the task.

---

## 🎯 Core Identity
Antikythera is a perpetual, human-in-the-loop, asynchronous multi-agent automation pipeline. It transforms simple ideas into technical specifications, architectures, and verified code through a gated, stage-based workflow.

## 📚 Hierarchy of Truth (Precedence)
When information conflicts, follow this order:
1.  **`memory.md`**: Foundational patterns and learned behaviors.
2.  **`PROJECT_STATUS.md`**: The current implementation roadmap and technical baseline.
3.  **`PROGRESS.md`**: Real-time status of completed/pending tasks.
4.  **`VERIFICATION_CRITERIA.md`**: The absolute "Definition of Done".

## 🗺️ Specialized Briefings
Depending on your current task, refer to the following specialized `AI.md` files for high-density technical context:

| Scope | Briefing File | Focus Area |
| :--- | :--- | :--- |
| **Agents** | `agents/AI.md` | Pipeline stages, artifact specs, agent roster, and output requirements. |
| **Backend/API** | `api/AI.md` | FastAPI, `StateManager`, API routes, and integration adapters. |
| **Workflows** | `api/workflow_AI.md` | Workflow engine, trigger management, and automation logic. |
| **Frontend/UI** | `ui/AI.md` | React 19, Tailwind, Kanban board UX, and design enhancements. |
| **UI Enhancements** | `design/ui-enhancement/AI.md` | Specialized design specs for visual polish and UX upgrades. |

## 🛠 Global Constraints (Non-Negotiable)
- **ID Normalization**: All Idea IDs (e.g., `ID-001`) MUST be **UPPERCASE**.
- **State Integrity**: Never write to `pipeline-state.json` directly. Use the `StateManager` or the API.
- **Atomic Operations**: All file writes must be atomic (use `os.replace`).
- **Secret Management**: Never hardcode secrets. Use `.env` files.
- **Idempotency**: Every agent action must be idempotent.
