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
1. Under "AI Engine Configuration" section:
	a. When we click on Models, there is no option to delete a model/configuration. Ideally in the card, there should be an option to delete the cart, and there should be a confirmation prompt when trying to delete it.
	b. I also would like a filter based on provider, so that a user can click on the filter card for one or more providers, and based on that the list of model will be shown.
	c. When I set an API key, and tryied testing, i get the errror "Google Gemma returned status 400: { "error": { "code": 400, "message": "API key not valid. Please pass a valid API key.",". But now, I no longer have an option to edit the key, there should be some such option.
	d. Ideally, when I click on the "Configured keys" a section should open, and this section should show me the current set of configured keys and option to edit/add a new key for a provider.
	e. Add Model button is not working. Also, when I click on it, and select the "Provider" there should be a button to "refresh" the list of available models, and the code should actualy go an query the list of available models and let user select the ones they want. The list could be long, so there should be a seaarch bar as we with auto-complete functionality.
	f. Overview is good, but I would like to see some graph and some more datapoints. 
	g. Can you add support to have Openrouter as a provider as well.
	h. Please add the functionality to tail logs in the logs section. Keep the buffer size to be as long as 1Mb.
2. In the integration Hub
	a. When I select any MCP server, the pop up opens in the right side of the screen, I want it to be in the center. 
	b. The "Test connection" in the pop-up is not working.
	c. Even if the connection is successful, the tile says disconnected.
	d. ON the MCP server tile, there should be a toggle to enable and disable an MCP server.
	e. If the MCP server is enabled, the "label" that we have should show the actual status, if needed, we can have a small button to test connection there itself.
	f. The Search is not working. Search bar as we as the drop down.
	g. The Manage secret should show the list of secrets configured, and ability to add/remove/edit those.
3. Automation Studio
	a. When I land on this page, I get the error "Failed to fetch templates".
4. When I switch the theme to "Night/Dark" only the background changes, Ideally all the element should change based on the dark theme"

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
