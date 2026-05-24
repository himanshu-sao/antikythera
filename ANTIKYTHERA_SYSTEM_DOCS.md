# Antikythera: Cognitive Automation Platform

Antikythera transforms a generic pipeline into a reusable, AI-orchestrated workflow automation system.

## Architecture Overview
The system follows a layered approach to separate high-level design from low-level execution:
1. **The Surface (UI)**: High-fidelity React interface featuring a Global Pipeline, Virtual Boards (template-filtered views), and a Workflow Architect.
2. **The Orchestrator (Builder)**: AI-powered blueprint generation that converts natural language into structured Templates.
3. **The Cognitive Engine**: A reasoning layer using `AIAdapter` for decision-making, `RunContext` for memory, and `PatternStore` for learning from human interventions.
4. **The Integration Hub**: A hybrid system supporting both **MCP Servers** (plug-and-play) and **Native Adapters** (custom glue code), with an encrypted `SecretVault` for credentials.
5. **The Clock (Scheduler)**: Background polling and webhook gateways to trigger runs autonomously.

## Key Product Features
- **Self-Learning**: When a run is `BLOCKED`, human corrections are saved as patterns. The AI uses these patterns for few-shot learning to resolve similar future cases automatically.
- **Virtual Boards**: Switch from the global view to a specific workflow's view, filtering items by their associated template.
- **Resilient Execution**: Automatic 3-stage retry policy (5, 10, 15 mins) before marking a run as `BLOCKED`.
- **Cognitive Timeline**: Full transparency into the AI's reasoning process, tool calls, and state transitions.

## Installation & Setup
1. Install dependencies: `pip install fastapi uvicorn cryptography apscheduler`
2. Start the API: `uvicorn api.main:app --reload`
3. Start the Frontend: `npm run dev`

## API Endpoints
- `/api/integrations`: Manage connection profiles and secrets.
- `/api/builder/generate`: AI-powered template generation.
- `/api/boards/virtual/{id}`: Get a filtered board view for a template.
- `/api/triggers/webhook/{provider}`: External event entry point.
