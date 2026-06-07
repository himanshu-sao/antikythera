# Project Issues & Incompleteness Log

## 🤖 Instructions for AI Agents
**This file is a living document of technical and functional gaps. If you are assigned to resolve an issue from issues.md, you MUST follow these protocols:**

1. **Update Documentation**: Whenever an issue is addressed, you must update the project `README.md` (and any other relevant design docs) to reflect the updated design and user behavior.
   - **CRITICAL**: Do not add a "list of fixes" or a changelog to the README. Update the actual description of how the system works.
   - **Why**: This ensures the README remains the single source of truth for current system behavior.
2. **Cleanup**: Once an issue is resolved and verified, you should **remove the corresponding checklist entry** from this file (or move it to an archive). The overall file should remain as a living document; only delete the whole file when no pending items remain.
3. **Testing Protocol**: After implementing a feature, **move the item to the `Needs Testing` section** (below) with enough context (what was changed, which files, exact test commands + expected output) for an AI to run the verification autonomously.
4. **General Guideline**: Use stop_antikythera.sh and start_antikythera.sh to restart the server, and always use python virtual environment.

**Protocol for Adding New Issues:**
When a user reports a gap or issue:
- **Analyze**: Do not simply record the user's text. Investigate the codebase and `README.md` to understand the current implementation and the exact nature of the gap.
- **Collaborate**: Discuss the technical findings and the proposed "complete" state with the user.
- **Finalize**: Only after the user confirms the detailed specification should the issue be recorded in this file.

## ⏳ Pending Tasks (Consolidated Run‑book)

*(All items have been completed and moved to the archive.)*

## 📦 Archive (Completed Items)
- AI Engine Configuration: Delete model, Provider filter, API key edit, Configured keys view, Add Model workflow, OpenRouter support, Log tail.
- Integration Hub: Secret management UI enhancements, Centered pop‑up (already centered), Test connection works, Enable/disable toggle.
- Automation Studio: Added `/api/automation/templates` endpoint to supply templates.
- Overview: Added placeholder `AIEngineOverview` component.
- Dark theme: Basic theme toggle via `data-theme` attribute (existing).


## Test Strategy

1. **Unit Tests**:
   - Test individual hooks in isolation
   - Test pure functions and utilities
   - Test component rendering with different props

2. **Integration Tests**:
   - Test component interactions
   - Test API integration points
   - Test state management flows

3. **UI/Functional Tests**:
   - Test user interactions (drag/drop, clicks, form submissions)
   - Test responsive behavior
   - Test accessibility features

4. **End-to-End Tests**:
   - Test complete user workflows
   - Test error scenarios
   - Test loading states
