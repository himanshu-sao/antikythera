# 🤖 Agents Specialized Briefing

**Purpose**: High-density technical context for all AI agents working on Antikythera's agent system. This document covers pipeline stages, agent roster, artifact specifications, and output requirements.

---

## 🎯 Agent Roster & Responsibilities

### 1. Orchestrator Agent
**Role**: Central coordinator and pipeline manager
**Stages**: All stages (discovery, routing, state transitions)
**Key Responsibilities**:
- Route ideas to appropriate workflow blueprints
- Manage state transitions in `pipeline-state.json`
- Coordinate handoffs between specialized agents
- Trigger human approval gates at critical checkpoints
- Monitor heartbeat scheduler and background tasks

### 2. Refiner Agent
**Role**: Requirements engineering and story mapping
**Stages**: DISCOVERY → BLUEPRINT
**Inputs**: Raw idea from `ideas.md` or webhook
**Outputs**:
- `spec.md`: Functional requirements, user stories, acceptance criteria
- Prioritized feature list with dependency mapping
- Clarification questions if requirements are ambiguous

### 3. Architect Agent
**Role**: Technical design and system architecture
**Stages**: BLUEPRINT
**Inputs**: `spec.md` from Refiner Agent
**Outputs**:
- `architecture.md`: File structure, module definitions, interfaces
- Database schema (if applicable)
- API contract definitions
- Technology stack recommendations with justification

### 4. Tester Agent
**Role**: Test planning and quality assurance
**Stages**: BLUEPRINT → UNIT_VERIFY (post-execution)
**Inputs**: `spec.md`, `architecture.md`, current state of code
**Outputs**:
- `tests.md`: Comprehensive test plan including:
  - Unit test cases ( Jest/Mocha)
  - Integration test scenarios
  - E2E workflow validation
- Docker Compose setup for sandboxed integration testing
- Coverage reports and quality metrics

### 5. Executor Agent
**Role**: Code implementation and verification
**Stages**: IMPLEMENTATION → UNIT_VERIFY
**Inputs**: `spec.md`, `architecture.md`, `tests.md`
**Outputs**:
- Fully functional codebase following architecture
- `execution_report.md`: Summary of implemented features, test results
- Git commits with atomic changes and descriptive messages
**See**: `docs/agents/executor-agent-design.md` for design spec; `api/executors/safe_executor.py` for the actual implementation

### 6. Audit Agent
**Role**: Security review and compliance checking
**Stages**: SYSTEM_VAL (pre-handover)
**Inputs**: Completed implementation, all artifacts
**Outputs**:
- Security audit report (OWASP/CWE checks)
- Dependency vulnerability scan results
- Compliance checklist (auth, encryption, logging)
- Risk assessment and remediation recommendations

### 7. Memory Agent
**Role**: Pattern learning and system evolution
**Stages**: Handover → Pattern Promotion
**Inputs**: Blocked run corrections, successful execution reports
**Outputs**:
- Updated `patterns.json` with new learned resolutions
- Memory entries in `brain/patterns.md` and `automation-ideas/brain/`
- Skill creation suggestions for recurring workflows
- Periodic brain loop summaries

---

## 📦 Artifact Specifications

### Standard Artifact Files

| Artifact | Location | Format | Purpose |
|----------|----------|--------|---------|
| `spec.md` | `artifacts/{idea_id}/` | Markdown | Functional requirements |
| `architecture.md` | `artifacts/{idea_id}/` | Markdown | Technical design |
| `tests.md` | `artifacts/{idea_id}/` | Markdown | Test plan |
| `execution_report.md` | `artifacts/{idea_id}/` | Markdown | Implementation summary |
| `audit_report.md` | `artifacts/{idea_id}/` | Markdown | Security review |
| `patterns.json` | `brain/patterns/` | JSON | Learned resolutions |

### Artifact Validation Rules

1. **spec.md** must include:
   - User stories with clear acceptance criteria
   - Functional requirements (numbered list)
   - Non-functional requirements (performance, security)
   - Edge cases and error handling scenarios

2. **architecture.md** must include:
   - Directory structure with rationale
   - File-level responsibilities
   - Interface definitions (function signatures, classes)
   - Dependencies and imports

3. **tests.md** must include:
   - Test cases mapped to requirements
   - Expected inputs/outputs
   - Integration test setup (Docker Compose if needed)
   - Coverage targets (minimum 80%)

---

## 🔄 Pipeline Stage Transition Rules

```
INTAKE → DISCOVERY → BLUEPRINT → IMPLEMENTATION → UNIT_VERIFY → INTEGRATION → SYSTEM_VAL → HANDOVER → DONE
```

### Stage Entry Criteria

| Stage | Entry Requirement | Agent Responsible |
|-------|-------------------|-------------------|
| DISCOVERY | Idea status = `NEW` or `REVIVE` | Orchestrator |
| BLUEPRINT | All artifacts missing/incomplete | Refiner → Architect → Tester |
| IMPLEMENTATION | All artifacts approved | Executor |
| UNIT_VERIFY | Executor reports SUCCESS | Tester (validation) |
| INTEGRATION | Unit tests pass, docker ready | Executor (sandboxed) |
| SYSTEM_VAL | Integration tests pass | Audit Agent |
| HANDOVER | Audit clears, user approval | Orchestrator |
| DONE | All verification criteria met | Orchestrator |

### Stage Exit Criteria

- **DISCOVERY**: Idea clarity score ≥ 0.8, no blocking questions
- **BLUEPRINT**: All 3 artifacts (spec, architecture, tests) present and approved by user
- **IMPLEMENTATION**: Code compiles, tests run, execution_report generated
- **UNIT_VERIFY**: All unit tests pass, coverage ≥ 80%
- **INTEGRATION**: Docker sandbox spins up, E2E tests pass
- **SYSTEM_VAL**: No CRITICAL/HIGH security vulnerabilities, audit report generated
- **HANDOVER**: User confirms "Ready to commit" or selects "Request Changes"
- **DONE**: Implementation committed to git, pattern promoted if applicable

---

## 🧠 Pattern Store & Learning Loop

### Pattern Format

```json
{
  "pattern_id": "PAT-001",
  "trigger_signature": "npm_build_failed_webpack",
  "context": {
    "error_message": "Module not found: react",
    "file": "package.json",
    "stage": "IMPLEMENTATION"
  },
  "resolution": {
    "action": "terminal",
    "command": "npm install react react-dom",
    "expected_outcome": "Dependencies added, build succeeds"
  },
  "confidence": 0.95,
  "usage_count": 12,
  "created_at": "2026-06-01T10:00:00Z",
  "last_used": "2026-06-04T14:30:00Z"
}
```

### Learning Triggers

1. **Blocked State Rescue**: Human provides manual intervention when AI gets stuck
   - Save: Error context + Human resolution → Pattern
   - Apply: Future runs with matching error signature

2. **Successful Complex Workflow**: Multi-step task completes without escalation
   - Save: Workflow trace → Skill (if ≥ 5 tool calls)
   - Apply: Similar future workflows

3. **Pattern Promotion**: Repeated successful resolution of similar issues
   - Save: Resolution pattern → PatternStore
   - Apply: Future runs with matching error/context signatures

### Pattern Matching Algorithm

1. Hash the current error/workspace state → `query_signature`
2. Match against pattern trigger signatures in `brain/patterns.md` / `pattern_store.py`
3. If match confidence is HIGH → auto-apply resolution
4. If match confidence is MEDIUM → suggest to user (HITL confirmation)
5. If no match found → escalate to Orchestrator for human review

---

## 🛠️ Agent Tool Access Matrix

| Tool | Orchestrator | Refiner | Architect | Tester | Executor | Audit | Memory |
|------|--------------|---------|-----------|--------|----------|-------|--------|
| `read_file` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `write_file` | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| `patch` | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| `terminal` | ✅ (limited) | ❌ | ❌ | ✅ (test runner) | ✅ | ✅ (scan) | ✅ (brain loop) |
| `web_search` | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| `delegate_task` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `skill_view` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `memory` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

**Tool Restrictions**:
- Executors run in sandboxed environments for `terminal` access
- Audit agent has read-only access to logs and configs
- Orchestrator can delegate to specialized agents but cannot directly modify code

---

## 📊 Output Quality Standards

### Code Quality (Executor Agent)
- **Modularity**: Single responsibility principle, < 500 lines per file
- **Documentation**: JSDoc/Python docstrings on all public APIs
- **Error Handling**: Try-catch blocks with generic user messages + detailed server logs
- **Testing**: All functions have corresponding unit tests

### Artifact Quality (All Agents)
- **Clarity**: No ambiguous language ("should", "maybe", "approximately")
- **Specificity**: Numbered requirements with exact values where applicable
- **Completeness**: All edge cases, error scenarios, and dependencies documented
- **Consistency**: Terminology, naming conventions, and formatting aligned across artifacts

### Verification (Tester/Audit Agents)
- **Coverage**: ≥ 80% line coverage on critical paths
- **Security**: Zero CRITICAL/HIGH CVEs in dependency scan
- **Performance**: Response times < 200ms for API endpoints, < 2s for complex operations
- **Accessibility**: WCAG 2.1 AA compliance on UI components (if applicable)

---

## 🔄 Cross-Agent Communication Protocol

### Message Format

```json
{
  "message_id": "MSG-001",
  "from_agent": "Refiner",
  "to_agent": "Architect",
  "stage": "BLUEPRINT",
  "payload": {
    "idea_id": "ID-001",
    "artifacts": {
      "spec_path": "artifacts/ID-001/spec.md",
      "status": "APPROVED"
    }
  },
  "timestamp": "2026-06-04T15:00:00Z"
}
```

### Handoff Rules
1. **Sync Handoff**: Agent waits for acknowledgment before proceeding (e.g., Refiner → Architect)
2. **Async Handoff**: Agent publishes event, next agent picks up when ready (e.g., Executor → Memory)
3. **Escalation**: If any agent fails after max retries, Orchestrator triggers human approval gate

### Error Propagation
- All errors logged to `logs/{idea_id}/agent-{name}.log`
- Critical errors (unrecoverable) → Orchestrator → Human notification via Telegram
- Non-critical errors (retryable) → Bounded retry loop (max 3 attempts) → Blocked state

---

## 🧪 Testing Your Agent

### Unit Testing Agents
```bash
# Run agent-related tests
pytest tests/test_orchestrator_pipeline.py
pytest tests/test_executor_agentic.py
```

### Integration Testing
```bash
# Run integration tests
pytest tests/test_integration_status.py
pytest tests/test_workflow_automation.py
```

### Validation Checklist
- [ ] Agent loads all required tools
- [ ] State transitions follow pipeline rules
- [ ] Artifacts are written to correct paths
- [ ] Error handling prevents infinite loops
- [ ] Logging captures all major decisions
- [ ] Communication with Orchestrator works
- [ ] Recovery from interruption works (checkpoint/resume)

---

## 📖 Related Documentation
- **Root AI.md**: `AI.md` (routing table)
- **PROJECT_STATUS**: `PROJECT_STATUS.md` (master execution document)
- **Executor Design**: `docs/agents/executor-agent-design.md`
- **Workflow Engine**: `api/workflow_AI.md`
- **System Architecture**: `README.md`

---

*Last Updated: July 2026 | Version: 2.1*