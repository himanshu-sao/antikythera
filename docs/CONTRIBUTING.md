# Contributing to Antikythera

Antikythera is a perpetual, human-in-the-loop, asynchronous multi-agent automation pipeline. This guide provides instructions on how to set up the development environment and contribute to the project.

## 🚀 Project Overview

Antikythera converts simple automation ideas into structured specifications, architecture, and verified tests.

- **Backend**: FastAPI (Python 3.9+)
- **Frontend**: React 19, Vite, Tailwind CSS, TypeScript
- **State Management**: File-based (`pipeline-state.json`)
- **Interactions**: Kanban UI and Telegram notifications

## 🛠️ Local Development Setup

### 1. Backend Setup

The backend handles agent logic and state management.

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the API server
python api/main.py
```

The API runs on `http://localhost:8006`. You can access the interactive API documentation at `http://localhost:8006/docs`.

### 2. Frontend Setup

The Kanban UI provides a visual operational surface.

```bash
# Navigate to the UI directory
cd ui

# Install dependencies
npm install

# Start the development server
npm run dev
```

The UI runs on `http://localhost:5173`.

### 3. Sandbox Setup (For Tester Agent)

The Tester Agent uses Docker to run tests in an isolated environment. Ensure you have Docker installed and running.

```bash
# Build the sandbox image
docker compose -f docker/docker-compose.yml build
```

## 🧪 Testing

### Backend Tests
Run the Python test suite using pytest:
```bash
pytest tests/
```

### Frontend Tests
Run the Vitest suite for UI components:
```bash
cd ui
npm test
```

## 📐 Contribution Workflow

1. **Create a Branch**: Always create a new branch for your changes (`git checkout -b feat/your-feature`).
2. **Implement Changes**: Follow the project's architecture patterns.
3. **Verify**: Run all tests and manually verify the feature in the browser.
4. **Pull Request**: Submit a PR to the `main` branch with a clear description of the changes and a test plan.

## 📁 Project Structure

- `api/`: FastAPI endpoints and state management.
- `agents/`: Core agent logic (Orchestrator, Refiner, Architect, etc.).
- `ui/`: React frontend code.
- `automation-ideas/`: The source of truth for pipeline state and idea artifacts.
- `docker/`: Sandbox configuration for the Tester Agent.
