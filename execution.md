1|# 🚀 Master Execution Plan: Low-Code AI Compiler (WYSIWYG Pipeline)
2|
3|This file is the single source of truth for the transformation of Antikythera into a **Recording-based "Low-Code AI Compiler"**. It manages the transition from a generic template system to a deterministic, adapter-based automation engine.
4|
5|## 📖 Operational Guidelines
6|1. **Sequential Flow:** Tasks MUST be completed in order (1.1 -> 1.4, then 1.5.1 -> 1.5.6, etc.).
7|2. **Session Continuity:** In a new session, the AI should read this file and execute the first `PENDING` task.
8|3. **Atomic Updates:** After every successful implementation and verification, the AI must update the status to `COMPLETED`.
9|4. **Verification:** A task is not `COMPLETED` until the code is written, linted, and functionally verified (via API logs or UI).
10|
11|### 🔄 New Workflow: Granular Sprints
12|Each major feature is now broken into a **6-stage loop**:
13|1. **Design** (Define specs/models)
14|2. **Code** (Backend & Frontend implementation)
15|3. **Unit Test** (Logic verification)
16|4. **Integration Test** (End-to-end flow)
17|5. **Sign Off** (User/AI review)
18|6. **Commit** (Git commit after Sign Off)
19|
20|**Note:** Do not skip stages. A task moves to `COMPLETED` only after **Stage 5 (Sign Off)**.
21|
22|---
23|
24|## 🛠️ Phase 1: The Foundation (Deterministic Core)
25|**Goal:** Build the data models and the adapter-based execution engine to ensure the system is extendable and deterministic.
26|
27|| Task | Description | Status | Prompt |
28|| :--- | :--- | :--- | :--- |
29|| **1.1** | **Data Schema** | `COMPLETED` | **See Prompt 1.1** |
30|| **1.2** | **Adapter Layer** | `COMPLETED` | **See Prompt 1.2** |
31|| **1.3** | **Operator Registry** | `COMPLETED` | **See Prompt 1.3** |
32|| **1.4** | **Sandbox State** | `COMPLETED` | **See Prompt 1.4** |
33|
34|### 📝 Phase 1 Prompts
35|**Prompt 1.1:** "I am building a 'Low-Code AI Compiler' for automation pipelines in the Antikythera project. Implement the data models for Phase 1: Backend Pydantic models in `api/models/automation.py` for `Skill`, `PathStep`, `Path`, and `Pipeline`, and matching TypeScript interfaces in `ui/src/types.ts`. A `PathStep` must include: `step_id`, `operator_id`, `adapter_id`, `config`, `input_ref`, and `output_ref`."
36|
37|**Prompt 1.2:** "Continuing the 'Low-Code AI Compiler' implementation. Build the Adapter Layer: Implement a `BaseAdapter` abstract class in `api/adapters/base.py` with `fetch()`, `update()`, `create()`, and `delete()` methods, and concrete implementations for `JiraAdapter` and `GitHubAdapter` in `api/adapters/jira.py` and `api/adapters/github.py`. **Ensure all backend execution uses the local `venv` (`./venv/bin/python`).**"
38|
39|**Prompt 1.3:** "Continuing the 'Low-Code AI Compiler' implementation. Implement the **Operator Registry**. Create a `OperatorRegistry` class that maps a generic `operator_id` to the correct `BaseAdapter` method and handles the dispatching logic `execute_step(step: PathStep, state: SessionState)`, resolving `input_ref` from the state."
40|
41|**Prompt 1.4:** "Final part of Phase 1. Implement the **Sandbox Session State Manager**. Create a `SessionStateManager` that maintains a temporary store of variables for a recording session, allows steps to write `output_ref` results, and supports 'Undo/Rollback' to previous steps."
42|
43|---
44|
45|## 🛠️ Phase 1.5: Core Redesign (New Features Foundation)
46|**Goal:** Extend data models and registry to support **Conditions**, **Iterators (Fan-out)**, **Script Mode**, **Dynamic Package Install**, and **Structured Data**。
47|
48|| Task | Description | Status | Stage |
49|| :--- | :--- | :--- | :--- |
50||| **1.5.0** | **Design: Safe Executor, Dynamic Install & Model** | `COMPLETED` | Design |
51||| **1.5.1** | **Design: Extended Data Models (Structured Fields)** | `COMPLETED` | Design |
52||| **1.5.2** | **Code: Update Pydantic & TS Models** | `COMPLETED` | Code |
53||| **1.5.3** | **Code: Implement Safe Executor with pip** | `COMPLETED` | Code |
54||| **1.5.4** | **Code: Extend Operator Registry** | `COMPLETED` | Code |
55||| **1.5.5** | **Unit Test: Models, Executor & Registry** | `COMPLETED` | Test |
56||| **1.5.6** | **Integration: End-to-Step Execution** | `COMPLETED` | Test |
57|| **1.5.7** | **Sign Off: Design Review** | `COMPLETED` | Sign Off |
58|
59|### 📝 Phase 1.5 Prompts
60|**Prompt 1.5.0:** "Design the **Safe Python Executor** with **Dynamic Package Installation**.
61|1. **Sandbox:** Runs in `venv`. Allowed imports: `json`, `re`, `httpx`, `datetime`, `yaml`, `pandas` (after install).
62|2. **Dynamic Install:** If script imports unknown package (e.g., `pandas`), pause and trigger a **System Proposal**: *'Script requests 'pandas'. Allow install in sandbox venv?'*. On approval, run `./venv/bin/pip install <pkg>` then retry.
63|3. **Migration Strategy:** Ensure backward compatibility with existing data.
64|Output a detailed spec."
65|
66|**Prompt 1.5.1:** "Design the extended data models.
67|1. **Condition:** `regex`, `equals`, `in_list`.
68|2. **Loop Over:** Iterator logic.
69|3. **Structured Data:** Add `extracted_fields` (JSON blob) to Child Execution model to store parsed data (e.g., `{ image: '...', os: '...', java_path: '...' }`).
70|4. **Audit:** `execution_reason`.
71|Output a markdown spec."
72|
73|**Prompt 1.5.2:** "Implement the extended data models. Update `api/models/automation.py` and `ui/src/types.ts`.
74|- Add `extracted_fields: Dict[str, Any]` to the `ExecutionLog` (Child Run) model.
75|- Ensure `condition`, `loop_over`, `mode`, and `execution_reason` are included.
76|- Ensure backward compatibility (optional fields, defaults)."
77|
78|**Prompt 1.5.3:** "Implement the **Safe Executor with Dynamic Install**.
79|- Create `SafeExecutor` class.
80|- Intercepts `ImportError`.
81|- If error is for an allowed package (not in blocklist), trigger a background event for user approval.
82|- On approval, execute `./venv/bin/pip install <pkg>`.
83|- Re-run the script.
84|- Enforce `venv` usage (use `./venv/bin/python` for all subprocess calls)."
85|
86|**Prompt 1.5.4:** "Extend the `OperatorRegistry`.
87|- Implement `execute_condition()`, `execute_loop()`.
88|- Implement `execute_script()` (using SafeExecutor).
89|- Ensure the `JiraAdapter` populates `extracted_fields` when a step runs (or calls a Skill to do so)."
90|
91|**Prompt 1.5.5:** "Write unit tests.
92|- Test `SafeExecutor` security (block `os.system`).
93|- Test **Dynamic Install flow**: Mock `import pandas` -> Trigger Proposal -> Simulate Install -> Re-run.
94|- Test `execute_condition` and `execute_loop`."
95|
96|**Prompt 1.5.6:** "Run an integration test.
97|- Fetch 2 Jira tickets with rich descriptions.
98|- Extract fields (Image, OS, Java Path) into `extracted_fields`.
99|- Split into 2 child runs.
100|- Verify `venv` package installation if needed."
101|
102|**Prompt 1.5.7:** "Sign Off: Review Phase 1.5.
103|- Confirm `venv` usage, Dynamic Install, Structured Data extraction, and Audit Logs work.
104|- Verify backward compatibility.
105|- Ready for commit."
106|
107|---
108|
109|## 🧠 Phase 2: The "Compiler" (AI -> Logic Bridge)
110|**Goal:** Implement the logic that translates natural language instructions into deterministic JSON configurations.
111|
112|| Task | Description | Status | Prompt |
113|| :--- | :--- | :--- | :--- |
114|| **2.1** | **The Proposal Loop** | `COMPLETED` | **See Prompt 2.1** |
115|| **2.2** | **Skill Brainstormer** | `COMPLETED` | **See Prompt 2.2** |
116|
117|### 🧠 Phase 2.5: The "Script Compiler" & Conditional UI
118|**Goal:** Update the AI proposal loop to generate **safe scripts** and **multi-choice proposals**.
119|
120|| Task | Description | Status | Stage |
121|| :--- | :--- | :--- | :--- |
122|| **2.5.1** | **Design: Script Sandboxing & Proposal UI** | `COMPLETED` | Design |
123|| **2.5.2** | **Code: Update Proposal Endpoint** | `COMPLETED` | Code |
124|| **2.5.3** | **Code: Multi-Choice UI Component** | `COMPLETED` | Code |
125|| **2.5.4** | **Unit Test: Script Generation** | `COMPLETED` | Test |
126|| **2.5.5** | **Integration: Approval Flow** | `COMPLETED` | Test |
127|| **2.5.6** | **Sign Off: Compiler Review** | `COMPLETED` | Sign Off |
128|
129|### 📝 Phase 2.5 Prompts
130|**Prompt 2.5.1:** "Design the script sandboxing strategy. Define allowed imports and the structure for multi-choice proposals (options array). **Include support for extracting structured fields (Regex/JSON) as a generated Skill.** Output a spec."
131|
132|**Prompt 2.5.2:** "Update the `propose` endpoint. Modify the AI prompt to generate `python_code` strings (using the SafeExecutor contract) or `adapter_call` objects with `options`. **Include a logic block to generate 'Parsing Skills' for 'Extract Field' commands.**"
133|
134|**Prompt 2.5.3:** "Update `ui/src/components/AutomationStudio.tsx`. Render a modal with buttons for `options` instead of a simple Yes/No checkbox when options are present. **Add a specific prompt for 'Package Install' confirmation.**"
135|
136|**Prompt 2.5.4:** "Unit test script generation. Verify AI output is valid, sandbox-safe Python, and that parsing skills (regex) are correctly generated."
137|
138|**Prompt 2.5.5:** "Integration test approval flow. User selects an option -> Step executes (including dynamic install if needed) -> Result stored."
139|
140|**Prompt 2.5.6:** "Sign Off: Review compiler logic. Confirm AI produces safe, deterministic steps and UI handles multi-choice and package install prompts. Ready for commit."
141|
142|---
143|
144|## 🎨 Phase 3: The WYSIWYG Builder (Recording Interface)
145|**Goal:** Create the interactive "Studio" where users record their automation paths.
146|
147|| Task | Description | Status | Prompt |
148|| :--- | :--- | :--- | :--- |
149|| **3.1** | **Interactive Studio** | `COMPLETED` | **See Prompt 3.1** |
150|| **3.2** | **Step Recorder** | `COMPLETED` | **See Prompt 3.2** |
151|| **3.3** | **Highlighter UI** | `COMPLETED` | **See Prompt 3.3** |
152|
153|### 🎨 Phase 3.5: Execution Splitting & Dashboard
154|**Goal:** Implement the **"1 Fetch -> N Cards"** visual and logical flow.
155|
156|| Task | Description | Status | Stage |
157|| :--- | :--- | :--- | :--- |
158|| **3.5.1** | **Design: Parent-Child Execution & Data Model** | `COMPLETED` | Design |
159|| **3.5.2** | **Code: Update Execution Engine** | `COMPLETED` | Code |
160|| **3.5.3** | **Code: Dashboard Child View** | `COMPLETED` | Code |
161|| **3.5.4** | **Code: Audit & Structured Data UI** | `COMPLETED` | Code |
162|| **3.5.5** | **Unit Test: Split Logic & Data Extraction** | `COMPLETED` | Test |
163|| **3.5.6** | **Integration: Dashboard Visualization** | `COMPLETED` | Test |
164|| **3.5.7** | **Sign Off: Split UX Review** | `COMPLETED` | Sign Off |
165|
166|### 📝 Phase 3.5 Prompts
167|**Prompt 3.5.1:** "Design the Parent-Child execution model.
168|- Define `parent_run_id`.
169|- Define `extracted_fields` (JSON) to store structured data (Image, OS, Priority, Assignee, etc.).
170|- Define `status` and `execution_reason`.
171|Output a spec."
172|
173|**Prompt 3.5.2:** "Update the execution engine.
174|- When `loop_over` is triggered, create multiple execution log entries.
175|- **Crucial:** For each child, run the 'Parsing Skills' to populate `extracted_fields` from the raw Jira description.
176|- Link by `parent_run_id`."
177|
178|**Prompt 3.5.3:** "Update `ui/src/components/PipelineDashboard.tsx`.
179|- Implement accordion/nested list for child runs.
180|- Show `status` and `execution_reason`.
181|- **Display `extracted_fields`** in a table/grid within each card (e.g., 'OS: RHEL8', 'Image: us.icr.io...')."
182|
183|**Prompt 3.5.4:** "Update the Dashboard UI to display `execution_reason` and render `extracted_fields` nicely (key-value pairs, colors for severity)."
184|
185|**Prompt 3.5.5:** "Unit test the split logic.
186|- Verify 2 input tickets -> 2 child records.
187|- Verify `extracted_fields` are populated correctly from mock descriptions."
188|
189|**Prompt 3.5.6:** "Integration test the dashboard.
190|- Run pipeline with 2 tickets.
191|- Verify UI shows 2 cards with correct statuses, reasons, and **parsed data**."
192|
193|**Prompt 3.5.7:** "Sign Off: Review split UX.
194|- Confirm user sees individual status, **parsed data**, and can act on them.
195|- Ready for commit."
196|
197|---
198|
199|## 📈 Phase 4: Pipeline Orchestration & Visualization
200|**Goal:** Promote recorded paths to production pipelines and provide visual monitoring.
201|
202|| Task | Description | Status | Prompt |
203|| :--- | :--- | :--- | :--- |
204|| **4.1** | **Promotion Logic** | `COMPLETED` | **See Prompt 4.1** |
205|| **4.2** | **Flowchart View** | `COMPLETED` | **See Prompt 4.2** |
206|| **4.3** | **Execution History** | `COMPLETED` | **See Prompt 4.3** |
207|
208|### 📈 Phase 4.5: Global Skills & Credential Prompt
209|**Goal:** Implement **reusable skills** and **runtime auth prompts**.
210|
211|| Task | Description | Status | Stage |
212|| :--- | :--- | :--- | :--- |
213|| **4.5.1** | **Design: Global Skill Store & Auth Flow** | `COMPLETED` | Design |
214|| **4.5.2** | **Code: Skill Registry & Adapter Auth** | `COMPLETED` | Code |
215|| **4.5.3** | **Code: Auth Prompt Modal** | `COMPLETED` | Code |
216|| **4.5.4** | **Unit Test: Skill Re-use** | `COMPLETED` | Test |
217|| **4.5.5** | **Integration: Auth Retry Flow** | `COMPLETED` | Test |
218|| **4.5.6** | **Sign Off: Authentication Review** | `COMPLETED` | Sign Off |
|| **4.5.7** | **Test Fix: Auth Retry Mock** | `COMPLETED` | Test |
219|
220|### 📝 Phase 4.5 Prompts
221|**Prompt 4.5.1:** "Design the global skill store.
222|- Skills must support **Text Parsing** (Regex/JSON) to extract fields like 'OS Distro', 'Image Path' from unstructured text.
223|- Design auth prompt flow for 401."
224|
225|**Prompt 4.5.2:** "Update `OperatorRegistry` to query global skills.
226|- Add logic to **execute Parsing Skills** on raw text (Description) to populate `extracted_fields`.
227|- Add 401/403 exception handling."
228|
229|**Prompt 4.5.3:** "Implement the Auth Prompt Modal in `AutomationStudio`.
230|- On 401, prompt for token.
231|- Retry step."
232|
233|**Prompt 4.5.4:** "Unit test skill re-use.
234|- Verify a 'Parse Jira Description' skill created in Path A populates fields in Path B."
235|
236|**Prompt 4.5.5:** "Integration test auth retry.
237|- Trigger 401 -> Input Token -> Success."
238|
239|**Prompt 4.5.6:** "Sign Off: Review authentication and skill re-use.
240|- Confirm credentials handled securely and **parsing skills work across paths**.
241|- Ready for commit."
242|
243|---
244|
245|## 🏠 Phase 5: Home Page Integration (The Hub)
246|**Goal:** Integrate the new automation system into the main application entry point.
247|
248|| Task | Description | Status | Prompt |
249|| :--- | :--- | :--- | :--- |
250|| **5.1** | **Tabbed Navigation** | `COMPLETED` | **See Prompt 5.1** |
251|| **5.2** | **Pipeline Dashboards** | `COMPLETED` | **See Prompt 5.2** |
252|| **5.3** | **E2E Validation** | `COMPLETED` | **See Prompt 5.3** |
253|
254|### 🏠 Phase 5.5: Final E2E Validation (Jira Use Case)
255|**Goal:** Execute the full **Jira Vulnerability Use Case** end-to-end.
256|
257|| Task | Description | Status | Stage |
258|| :--- | :--- | :--- | :--- |
259|| **5.5.1** | **Integration: Full Jira Flow** | `COMPLETED` | Test |
260|| **5.5.2** | **Sign Off: Product Acceptance** | `COMPLETED` | Sign Off |
261|
262|### 📝 Phase 5.5 Prompts
263|**Prompt 5.5.1:** "Run the full Jira Vulnerability flow:
264|1. Record path: 'Fetch Jira tickets'.
265|2. Record step: 'Extract OS and Image' (create parsing skill).
266|3. Record step: 'If OS=RHEL8, update status'.
267|4. Promote to Pipeline.
268|5. Run: Fetch 2 tickets -> **Split into 2 cards** -> **Populate extracted_fields** -> Apply conditions.
269|6. Verify Dashboard shows 2 cards with **parsed data**, status, and reason."
270|
271|**Prompt 5.5.2:** "Final Sign Off: Verify the system matches the user's requirements for automating mundane developer tasks. Confirm all underlying features (Venv, Dynamic Install, Structured Data, Splitting) work."