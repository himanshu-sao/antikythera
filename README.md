# 🚀 Hermes Multi-Agent Automation System

Hermes is a perpetual, human-in-the-loop, asynchronous multi-agent automation pipeline. It converts simple idea descriptions into structured specifications, architecture, and verified tests, allowing a human operator to review and approve progress via a Kanban UI and Telegram.

## 🌟 Vision
The goal of Hermes is to provide a high-leverage platform where AI agents handle the "heavy lifting" of software engineering (refining requirements, designing architecture, writing tests), while the human maintains absolute control through gated review stages.

## 🛠 Tech Stack
- **Agent Logic**: Python 3.x
- **UI**: React, Vite, Tailwind CSS, TypeScript
- **State Management**: File-based (`pipeline-state.json`)
- **Notifications**: Telegram Bot API
- **Sandbox**: Docker (used by the Tester Agent for isolated validation)

---

## 🏗 System Architecture

### 1. The Pipeline Workflow
Ideas move through a linear sequence of stages. Each stage is mapped to a column on the Kanban board.

`INTAKE` $\rightarrow$ `REFINEMENT` $\rightarrow$ `REVIEW_SPEC` $\rightarrow$ `ARCHITECTURE` $\rightarrow$ `REVIEW_ARCH` $\rightarrow$ `TESTING` $\rightarrow$ `REVIEW_TEST` $\rightarrow$ `APPROVED` $\rightarrow$ `EXECUTING` $\rightarrow$ `DONE`

### 2. The Agent Roster
- **Orchestrator**: The "brain" of the operation. It manages the pipeline state, dispatches work to other agents, and handles triggers.
- **Refiner Agent**: Transforms one-line ideas into detailed `spec.md` files.
- **Architect Agent**: Designs the technical solution and creates `architecture.md`.
- **Tester Agent**: Develops a test plan (`tests.md`) and validates implementations in a Docker sandbox.
- **Memory Agent**: A separate loop that analyzes audit logs and reviews to evolve the system's `patterns.md`.
- **Audit Agent**: A passive observer that logs every agent action to daily audit files.

### 3. Core Components
- **`automation-ideas/ideas.md`**: The primary intake file where new ideas are added.
- **`pipeline-state.json`**: The single source of truth for the current stage and metadata of every idea.
- **Kanban UI**: A local web application for visual management and inline editing of review files.
- **Telegram**: Used for real-time notifications and slash-command triggers.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Node.js & npm
- Docker (for Tester Agent sandboxing)
- A Telegram Bot Token (configured in the system)

### Installation & Setup

#### 1. Backend (Agents & API)
```bash
# Install Python dependencies
pip install -r requirements.txt

# Start the API server (for UI communication)
python api/main.py
```

#### 2. Frontend (Kanban UI)
```bash
cd ui
npm install
npm run dev
```

#### 3. Triggering the System
The system can be triggered in three ways:
- **Heartbeat**: Runs automatically on a schedule (default: 10 PM daily).
- **File Watcher**: Automatically triggers when files in `automation-ideas/` are modified.
- **Telegram**: Use slash commands (e.g., `/run ID-001`) to trigger specific ideas.

---

## 🕹 Operating the System

### Adding an Idea
Add a one-liner to the `## TODO` section of `automation-ideas/ideas.md`:
`- [ID-001] Description of the automation | Priority: High`

### Reviewing Progress
1. Open the **Kanban UI**.
2. Drag a card to a `REVIEW_*` column to signal your intent to review.
3. Open the **Artifact Viewer** to read the `spec.md`, `architecture.md`, or `tests.md`.
4. Edit the `review.md` file inline. Set `review_status: APPROVED` to move the idea to the next stage, or `NEEDS_REVISION` to send it back to the agent.

### Telegram Commands
- `/status`: Get a summary of all active pipeline items.
- `/run ID-XXX`: Force-trigger the pipeline for a specific idea.
- `/approve ID-XXX`: Mark the current stage as approved.
- `/redo ID-XXX`: Mark the current stage as needing revision.

---

## 🧠 The Brain Loop (Continuous Learning)
Hermes doesn't just execute; it learns. The **Memory Agent** runs a nightly loop:
1. It scans `audit/` logs and `review.md` comments.
2. It identifies recurring patterns (e.g., "The user always prefers environment variables over config files").
3. It proposes updates to `brain/patterns.md` via `brain/pending-updates.md`.
4. Once the human approves these updates, the system's behavior evolves.

---

## 🤖 AI Agent Guide
If you are an AI agent assisting with Hermes:
- **Source of Truth**: Follow the hierarchy: `memory.md` $\rightarrow$ `PROJECT_SUMMARY.md` $\rightarrow$ `PROGRESS.md` $\rightarrow$ `VERIFICATION_CRITERIA.md`.
- **State**: Always check `pipeline-state.json` before assuming an item's stage.
- **Normalization**: Use uppercase for all Idea IDs (e.g., `ID-001`).
- **Verification**: No task is complete until it satisfies the rules in `VERIFICATION_CRITERIA.md`.
