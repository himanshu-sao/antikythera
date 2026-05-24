# 🚀 Antikythera Cognitive Platform

Antikythera is a perpetual, human-in-the-loop, asynchronous multi-agent automation platform. It has evolved from a linear stage-based pipeline into a **Cognitive Orchestration System** that combines deterministic workflows with LLM-driven reasoning.

## 🌟 Vision
The goal of Antikythera is to provide a high-leverage platform where AI agents handle the "heavy lifting" of software engineering (refining requirements, designing architecture, writing tests) while allowing human operators to maintain absolute control through gated review stages and a high-fidelity Kanban UI.

## 🛠 Tech Stack
- **Agent Logic**: Python 3.9+
- **UI**: React 19, Vite, Tailwind CSS, TypeScript
- **State Management**: File-based JSON stores with `filelock` for concurrency.
- **Cognitive Layer**: LLM-powered reasoning steps and a few-shot learning pattern store.
- **Integrations**: Hybrid architecture supporting **MCP (Model Context Protocol) Servers** and **Native Python Adapters**.
- **Scheduling**: `APScheduler` for background polling and event-driven triggers.

---

## 🏗 System Architecture

### 1. The Cognitive Pipeline
The system supports two modes of operation:
- **Generic Pipeline**: A linear flow for high-level idea refinement (`INTAKE` $\rightarrow$ `DONE`).
- **Cognitive Workflows**: Reusable blueprints consisting of:
    - **Triggers**: Webhooks, Polling (JQL/Cron), or Manual starts.
    - **Steps**: Action steps (via adapters), AI Reasoning steps (decisions), or Human Approval gates.
    - **Context**: A `RunContext` that persists data across the entire lifecycle of a run.

### 2. The Integration Hub
A centralized hub for managing external services:
- **Secret Vault**: Encrypted storage for API keys and tokens.
- **Connector Types**:
    - **MCP Servers**: Plug-and-play discovery of tools from external MCP servers.
    - **Native Adapters**: Custom Python glue code for complex local tasks or niche APIs.
    - **Shell Sandbox**: Secure execution of whitelisted local scripts.

### 3. The Learning Loop
Antikythera implements "Self-Learning" through human intervention:
- **Blocked State**: If the AI cannot make a decision, the run enters a `BLOCKED` state.
- **Human Correction**: The operator provides the correct resolution in the UI.
- **Pattern Promotion**: This correction is saved to the `PatternStore`.
- **Future Application**: The AI uses these learned patterns to resolve similar future cases automatically.

### 4. The Operational Surface (UI)
- **Global Pipeline**: The universal triage board for all ideas.
- **Virtual Boards**: Template-specific filtered views that show only the items processed by a specific workflow.
- **Workflow Architect**: A visual builder allowing users to generate blueprints using natural language prompts.
- **Cognitive Timeline**: A high-fidelity event stream showing the AI's reasoning, adapter outputs, and state transitions.

---

## 🗺️ Project Roadmap & Status

### Phase 1: Foundation (Completed ✅)
- [x] Basic Kanban board with drag-and-drop.
- [x] State persistence and basic API.
- [x] Core agent roster (Refiner, Architect, Tester).

### Phase 2: Cognitive Orchestration (Completed ✅)
- [x] **Integration Hub**: MCP/Native support + Encrypted Secret Vault.
- [x] **Cognitive Engine**: `RunContext`, `AIAdapter`, and `Decision Logic`.
- [x] **Reliability**: 3-stage retry policy (5, 10, 15 mins) $\rightarrow$ `BLOCKED`.
- [x] **Learning**: `PatternStore` for few-shot learning from human interventions.
- [x] **Scheduling**: Background polling and Webhook gateway.
- [x] **The Studio**: AI-powered Visual Workflow Builder.
- [x] **The Surface**: Virtual Boards and Cognitive Timelines.

---

## ⚙️ Setup & Configuration

### 1. Environment Setup
- Ensure Python 3.9+ and Node.js 18+ are installed.
- Install Python dependencies: `pip install fastapi uvicorn cryptography apscheduler requests`
- Setup frontend: `cd ui && npm install`

### 2. Running the System
- **Backend**: `python -m uvicorn api.main:app --host 0.0.0.0 --port 8000`
- **Frontend**: `npm run dev`

### 3. Key Directories
- `api/`: The core backend logic and routers.
- `ui/`: The React frontend.
- `automation-ideas/`: The data store for state, templates, and requirements.
- `ANTIKYTHERA_SYSTEM_DOCS.md`: Deep-dive technical specifications.

---

*Antikythera: Automating the mundane, empowering the human.*
