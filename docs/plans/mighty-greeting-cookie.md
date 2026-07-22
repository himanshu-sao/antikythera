# Automation Studio Redesign — Plan

> Turn-based, live-results-led compiler. Human reacts to real returned data; the system materializes those reactions into a durable workflow graph that runs headlessly on cron.

**Status:** design locked 2026-07-20 (29 decisions); plan written 2026-07-21; **frontend slice + dec #22 reality reconciled 2026-07-21.**
**Branch:** `feat/phase4-workflow-architect` (supersedes the just-shipped WorkflowArchitect / BlueprintArchitect surface — dec #3).
**Supersedes:** current half-wired "NL → one PathStep" Studio recorder (non-functional).

This plan is the canonical doc for the redesign. The decisions log in the appendix is authoritative — if body text and the appendix disagree, the appendix wins.

---

## 0. Identity & North-Star Example

Today the Studio is a half-wired, non-functional "NL → one PathStep" recorder. The redesign makes it a **turn-based, live-results-led compiler**: the human reacts to real returned data and the system materializes those reactions into a workflow graph.

**Canonical example — Twistlock vuln ticket:**

1. "query Jira for open Twistlock tickets" → 3 tickets returned, materialized as **cards**.
2. "3 cards, one per ticket" → **fan-out** (a loop node, one branch per ticket).
3. "pick first" → **collapse/scope** (a selection narrowing, *not a node*).
4. "based on description, sort + tag" → **AI-transform**.
5. "if component==brotli AND status==New → move to Investigating + assign to me" → **conditional action**.

The human's reactions to live data at each turn *are* the graph definition. No separate "draw the graph" step.

### Four node archetypes

| Archetype | Role | Notes |
|-----------|------|-------|
| **Query** | Fetch live data from an integration | Returns a **list/vector** (dec #28 — `fetch_resource` today returns one resource, never a list; we build list query actions on adapters) |
| **Fan-out / loop** | One branch per item | Backed by sandbox `OperatorRegistry.loop_over` |
| **AI-transform** | One-off transform, or **saved as a Skill** (dec #13) | `mode=SCRIPT` via `SafeExecutor` |
| **Conditional-action** | Route/act on a condition | Backed by `OperatorRegistry.condition` (5 types, AND/OR) |

Plus **collapse/pick** = a scope-narrowing selection state, *not a node*.

---

## 1. Backend Map (what shaped the design)

| Component | Capability | Gap |
|-----------|-----------|-----|
| Sandbox `OperatorRegistry` | ✅ `condition` (5 types, AND/OR), ✅ `loop_over`, ✅ `mode=SCRIPT` (AI via SafeExecutor) | ⚠️ `input_ref` read / `output_ref` write |
| Headless `ExecutionEngine` | — | ❌ Never reads `condition` / `loop_over` / `input_ref` / `output_ref` → everything interactive dies at save. **This is *the* make-or-break gap**; the new `PathStepGraphEngine` closes it (dec #17). |
| Step schemas | sandbox `PathStep` vs headless `{step_id,name,category,config,next_step}` | Diverged — share defs via `api/models/automation.py` import (dec #17) |
| `BobShellAdapter` | only sync `execute()` | async ops raise `NotImplementedError` → unusable in sandbox. **Constraint: don't propose a bob_shell node in sandbox** (dec #26). Don't touch it. |
| `fetch_resource` | returns one resource | never a list → build list/vector query actions on adapters (dec #28) |

---

## 2. Storage (all under `automation-ideas/`, atomic writes via `BaseJSONManager` — gotcha #8)

| Path | Purpose | Manager |
|------|---------|---------|
| `studio_graphs/<graph_id>.json` | Saved interactive graph → durable headless template | new `api/managers/studio_graph_manager.py` |
| `skills/<skill_id>.json` | Migrate skills from in-memory dict → disk (dec #13) | new `api/managers/skill_manager.py` |
| `studio_runs/` | One run-log file per run (replay + undefined-queue; queryable) | run-log writer in the engine |

---

## 3. End-State Design

### 3a. Authoring surface (interactive)
Human plays & selects against live data turn by turn. Each reaction (fan-out, pick, AI-transform, conditional-action) becomes a node. System free-emit `capability` + `suggested_model_tier` per proposal (dec #12, BUILD — the auto-benchmark prober is DROPped; replay history yields that signal for free).

### 3b. Save = hybrid (dec #5)
Interactive author → **durable headless template** (+ optional manual drive). Saved graph runs known shapes headlessly; **undefined items are buffered** for later review (dec #6) — a fourth shape, not A/B/C. This is the feedback loop that grows the graph.

### 3c. Headless execution = cron-driven (dec #7)
Wired **in this redesign**, not deferred. Cron target = **simple graphs only** (dec #8/9).

### 3d. Routing (dec #8)
Condition-first; **AI-assisted signature matching** fallback. Branch node carries Condition + a short NL `signature` line (dec #19).

### 3e. Model tiers (dec #9, #10)
- **Simple graphs** run a **4–8B local model** (constrained classify yes/no). Cron target.
- **Complex graphs** (e.g. version-upgrade-from-code) need **20B/27B+**.
- The **graph declares required capability**; runtime resolves to model tier.
- New **"Model tiers" table** in the existing AI Engine config: classify / generate / reason-over-code → chosen provider+model. Defaults: classify→smallest local, generate→current default, reason-over-code→biggest. **Default unchanged for graphs that declare no tier.**

### 3f. Failure flavors (dec #11)
- **undefined-queue** — "don't recognize, cheap to triage." Persisted until resolved, **cap 100/graph, no auto-expiry** (dec #20).
- **escalate-to-human** — "recognize but can't safely complete." Destructive writes **pause via the existing orchestrator REVIEW-gate shape**.
- Replay history: keep the **last 50 full run-logs per graph + perpetual aggregate** (counts matched/undefined/escalated over time) (dec #21).

### 3g. Skills (dec #13, #18)
Skill = reusable AI-transform node, **persisted to disk**. Transform node is one-off or "save as Skill." **Retire the Skill Brainstormer loop from the Studio**; re-anchor Skill as the persisted runtime unit the transform-node reuses. Refine/fix the existing skill path — don't delete wholesale.

### 3h. Credentials (dec #14)
Single source = env vars (`~/.antikythera/.env`). Studio shows integration status + links to Integrations Hub. **No token-paste modal, no store-token endpoint.**

### 3i. MCP (dec #4)
Add MCP as one adapter type; leverage the existing IntegrationHub MCP routing.

### 3j. Target Integration (dec #1)
Optional. Studio job = full NL workflow generator, interactive "play & select" against live data.

---

## 4. First Slice (dec #15)

The interactive authoring loop **+** a runnable **deterministic** headless path. **AI-signature routing fallback is Phase 2 — slice 1 has NO LLM at cron.**

Slice-1 scope:
- Query → fan-out → cards → pick → AI-transform → conditional-action → **save**.
- Headless: condition-match routing + replay history + undefined queue + cron.
- Jira writes: **dry-run/log first, real writes at the END of slice 1** (dec #16).

Slice-1 NON-goals: AI signature fallback, auto-benchmark prober, 20B/27B complex-graph cron, bob_shell nodes.

### Slice-1 architecture constraints (dec #17)
- New dedicated **`PathStepGraphEngine`** for headless; **leave the two existing engines untouched** (zero regression risk to just-shipped work).
- Share model defs via `api/models/automation.py` import — **no shared-evaluator extraction in slice 1.**

---

## 5. Sequenced Phases

**Phase 1 — Slice 1 (deterministic, per §4).**
- Build `PathStepGraphEngine`; adapter list/vector query actions (dec #28); condition-first routing with **reserved-but-unused `signature: str`** (dec #19 — avoids Phase 2 migration); undefined-queue (cap 100, no expiry); replay history (50 logs + aggregate); cron wiring; real Jira writes at the end.
- New managers: `studio_graph_manager.py`, `skill_manager.py` (disk-backed).
- Studio surface rebuilt as the turn-based compiler; replace in place (dec #25); delete old component + `skills_db` on server restart (dec #23/#24 — **no migration**).
- Frontend: single shared `ui/src/types/studio.ts` (dec #22). **Dec #22 scope reconciled 2026-07-21:** the two "legacy Pipeline components" (`PipelineDashboard.tsx`, `PipelineFlowchart.tsx`) + `usePipelineState.ts` are the **Kanban board's pipeline-detail view** (backed by `/api/state` + `/api/pipelines/*`, rendered at `App.tsx:349` with `{pipelineId, onBack}`) — *not* Studio machinery. They import `Path`/`PathStep`/`Pipeline`/`PipelineItem`/`PipelineState`, which are **already absent from `src/types.ts` on HEAD** (pre-existing breakage from a half-finished prior refactor), so the dec #22 step is **not** "swap the import onto `StudioNode`" — see §7 Correction A. `StudioNode`/`StudioGraph` nevertheless become the only node types for the **Studio** surface; the board is restored locally, not coupled to the Studio graph model.
- Dead endpoints: **DELETE** `/api/automation/templates` (hardcoded 3-fake stub) and GET `/api/automation/state` (no consumer) (dec #23).
- Model-tier table scaffolded in AI Engine config with defaults (dec #10); graphs declaring no tier keep the current default.

**Phase 2 — AI routing + complex graphs.**
- AI-assisted signature matching as routing fallback (switches on the reserved `signature` corpus; 4–8B local classifier). No extra dry-run guard needed for Phase 2 routing (dec #27) — routing to a saved branch is executing a user-approved action; the small model never invents actions.
- Auto-benchmark prober remains DROPPED (dec #12); replay history is the signal.
- Complex-graph cron (20B/27B+) behind the capability declaration.

**Phase 3 — Feedback loop closure.**
- Undefined-queue review UI feeds signature-corpus growth → graph runs fewer undefined items over time.
- Perpetual aggregate dashboards (matched/undefined/escalated).
- Hardening pass on the new endpoints (joint with `[[antikythera-backend-template-hardening]]` — adjacent to `/api/builder/*` and templates).

---

## 6. Verification

- **Slice 1 acceptance (the Twistlock replay):** author the §0 example interactively, save, and replay headlessly on cron; condition-match routing dispatches correctly; un-matched items land in the undefined-queue (cap 100 enforced); 50 run-logs + aggregate persist; real Jira write fires once at slice-1 end after dry-run logging.
- **No regression:** existing two engines untouched → current Phase 4 WorkflowArchitect/BlueprintArchitect + full UI suite + affected pytest files stay green (per [[antikythera-prefers-targeted-tests]] — never run the full suite by default).
- **Legacy Pipeline (board):** the two Kanban components (`PipelineDashboard`, `PipelineFlowchart`) + `usePipelineState.ts` compile again against **restored** `Path`/`PathStep`/`PipelineItem`/`PipelineState` symbols (local `legacy-pipeline.ts`), decoupled from the Studio node model. They never compile against `studio.ts` — that file is Studio-only.
- **Skill persistence:** a "save as Skill" AI-transform survives server restart (disk-backed, dec #13).
- **Credentials:** no token-paste modal; Studio shows integration status from env vars (dec #14).

---

## 7. Corrections to the 2026-07-21 Design (reconciled against repo)

Before any frontend code, the slice-1 plan was checked against the working tree at `14a5e99`. Three things the locked design asserted are not what the repo shows. These are corrections of *scope*, not of the design intent.

### Correction A — dec #22 "migrate the two Pipeline components onto `studio.ts`"
The locked design assumed the two legacy Pipeline components import a `PathStep` symbol that the Studio redesign deletes, and that they should be retargeted onto `StudioNode`. Verified reality on `14a5e99`:

- `PipelineDashboard.tsx:3` imports `{ Pipeline, Path, PathStep }` from `../types`; `PipelineFlowchart.tsx:2` imports `{ Path, PathStep }`; `usePipelineState.ts:4` imports `{ PipelineItem, PipelineState }`.
- **`src/types.ts` defines none of these on HEAD** (`grep PathStep|Pipeline|PipelineItem|PipelineState src/types.ts` → empty). The board components are **already non-compiling** — a half-finished prior refactor left them importing a symbol that no longer exists. The import errors are pre-existing, not caused by the Studio work.
- These components are the **Kanban board's pipeline-detail view**: `PipelineDashboard` is rendered at `App.tsx:349` (`<PipelineDashboard pipelineId={pipelineId} onBack=… />`) and backed by `/api/pipelines/{id}` + `/api/pipelines/{id}/runs`; `usePipelineState` polls `/api/state` (the endpoint dec #23 *deletes*) and mutates `/api/item[s]`, `/api/move`, `/api/items/reorder`. **None are Studio routes** — they are the Kanban board (`ID-001` items per CLAUDE.md). Sharing the name "pipeline" is coincidence.

**Decision:** do **not** migrate the board onto `StudioNode` — that couples the live board to the Studio graph model and risks the Kanban surface. Instead (b) restore the five missing legacy symbols in a board-scoped module `ui/src/types/legacy-pipeline.ts` (`PathStep`/`Path`/`Pipeline`/`PipelineItem`/`PipelineState`), and repoint only the three import lines. `studio.ts` stays Studio-only. This honors the *intent* of dec #22 (one shared Studio node type, `StudioNode`) for the Studio surface, while leaving the board intact.

### Correction B — dec #23 `/api/state` is alive (the board polls it)
The locked design calls `/api/state` a "dead endpoint" to DELETE. Verification shows `usePipelineState.ts:14` polls `GET /api/state`. **Implication:** deleting `/api/state` (dec #23) **breaks the board**. Prerequisite before touching dec #23: either (i) repoint `usePipelineState` to `GET /api/board` / whatever state the board should use, or (ii) defer dec #23's `/api/state` deletion until the board is moved off it. **In slice 1, DELETE only `/api/automation/templates` and leave `/api/state` alone** — defer the state-endpoint half of dec #23 to a board-touching slice.

### Correction C — the `api/main.py` "duplicate `studio_router` import" defect is already resolved
A memory note flagged a duplicate `from api.studio_router import router as studio_router` in `api/main.py` for deduping. Verified: it does not exist at `14a5e99` — one import (line 47), one registration (line 121). Nothing to do. (Memory note corrected.)

---

## 8. Frontend Implementation Plan (Slice 1, file-by-file — written 2026-07-21)

Sequence chosen so the type surface compiles (and `studio.ts` gets a real consumer) before the big `AutomationStudio.tsx` rebuild. Each step yields a commit per dec #25 (replace in place) + standing `git/commit-and-push` memory (no `Co-Authored-By` trailer; commit **and** push to origin as default; affected vitest files only, never the full suite or e2e by default).

### Step 0 — dependency
- **`ui/package.json`** — add `"zod": "^3.x"` to `dependencies`. `studio.ts:21` does `import { z } from 'zod'`; without it the type surface does not compile. Pin a 3.x line (the zod schema shape in `studio.ts` is v3-compatible'). Run `npm install` and verify `node_modules/zod` exists; do **not** bump zod to v4 (schema API differs) without re-validating every `StudioGraphSchema`/`NodeSchema`.

### Step 1 — restore the board (Corrections A + B)
- **Create `ui/src/types/legacy-pipeline.ts`** — board-scoped symbols only: `interface PathStep { step_id; operator_id; adapter_id; config: Record<string, unknown> }`, `interface Path { path_id; name; steps: PathStep[] }`, `interface Pipeline { name; description?; status; trigger: { type: string } }`, `interface PipelineItem` (mirror what `/api/state` returns for `ID-001` items — match current board shape), `interface PipelineState { items: Record<string, PipelineItem> }`. Derive the exact fields from a live `GET /api/state` response or `api/board_router.py`, not from memory.
- **`ui/src/components/PipelineDashboard.tsx:3`** → `import { Pipeline, Path, PathStep } from '../types/legacy-pipeline';`
- **`ui/src/components/PipelineFlowchart.tsx:2`** → same.
- **`ui/src/hooks/usePipelineState.ts:4`** → `import type { PipelineItem, PipelineState } from '../types/legacy-pipeline';`
- **Verify:** `npx tsc --noEmit` does not gain new board errors; `npx vitest run` still 8 files / 23 tests green (board has no vitest coverage today — do not add e2e). Do **not** delete `/api/state` (Correction B).

### Step 2 — thin Studio API client
- **Create `ui/src/api/studioClient.ts`** — direct-`fetch` helpers matching the existing convention (`usePipelineState.ts`, `useArtifacts.ts`), no axios. One function per route the Studio surface calls, each validating the response with the matching `studio.ts` zod schema (`StudioGraphSchema` / `SkillSchema` / `GraphRunLogSchema`):
  - `listGraphs()` → `GET /api/studio/graphs` → `StudioGraphAPI[]`
  - `getGraph(id)` → `GET /api/studio/graphs/{id}` → detail
  - `saveGraph(graph)` → `POST /api/studio/graphs` (new) or `PUT /api/studio/graphs/{id}` (update)
  - `deleteGraph(id)` → `DELETE /api/studio/graphs/{id}` (204)
  - `runGraph(id)` → `POST /api/studio/graphs/{id}/run`
  - `listRuns(id)` → `GET /api/studio/graphs/{id}/runs`
  - `getUndefinedQueue(id)` → `GET /api/studio/graphs/{id}/undefined-queue`
  - `listSchedulable()` → `GET /api/studio/schedulable-graphs`
  - `listSkills()`, `getSkill(id)`, `saveSkill(skill)`, `deleteSkill(id)`
  - `getIntegrationStatus()` → `GET /api/studio/integrations/status` (dec #14 — status only, no token)
  All prefixed with `${apiUrl}` from `../config`.
- This gives `studio.ts` its first consumer → unblocks committing it untracked (`Step 5`).

### Step 3 — rebuild `AutomationStudio.tsx` in place (dec #25; the core of slice 1)
Replace the dead NL→one-`PathStep` recorder (459 LOC, posts to `/api/automation/{propose,accept}` + skill brainstormer — both retired by dec #3/#18) with the **turn-based, live-results-led compiler** from §0. Single file `src/components/AutomationStudio.tsx` (keep the export name + the `App.tsx:235` mount; no prop changes — dec #25 replace-in-place requires the call site to stay untouched). Structure:

- **`<AutomationStudio />` state:** `graph: StudioGraph` (in-memory nodes/edges under construction), `executionState: Record<string, unknown>` (live sandbox state, keyed by `output_ref`), `turn: number`, `selectedNodeId`, `proposal: ProposalDTO | null`, `isLoading`, `graph_id` (once saved).
- **Turn loop** (the Twistlock example, §0):
  1. **Query turn** — pick adapter (from `getIntegrationStatus()`), action `list_resources`, `params`, `output_ref`; call backend query path (dec #28 list/vector); render returned items as **cards**. Materialize a `QueryNode` (archetype `QUERY`); push `output_ref → result` into `executionState`; append node + edge to `graph`.
  2. **Fan-out turn** — on the returned list, materialize a `FanOutNode` (`loop_over: { source: <query.output_ref>, iterator_var: "ticket" }`); render one card per item; future turns execute in the per-item scope.
  3. **Collapse/pick turn** — `pick_first` / `pick_n` / `filter` (a `CollapseSpec`, **not a node** — §0). Narrows `executionState` scope; records no node but updates `turn` context.
  4. **AI-transform turn** — author inline `script` (Python for SafeExecutor, `execution_mode: SCRIPT`) or pick a persisted `skill_ref`; `input_ref` / `output_ref`. Materialize `AITransformNode`; "Save as Skill" → `saveSkill()` (dec #13). Honor `suggested_model_tier` from the proposer (dec #12).
  5. **Conditional-action turn** — build a `ConditionExpr` (simple/compound; field dot-path, `ConditionType`, value; AND/OR); `true_action` adapter/action/config; optional `false_action`; `routing_strategy: CONDITION_FIRST`; reserve `signature` (dec #19 — unused in slice 1, max 200). Materialize `ConditionalActionNode`.
  6. **Save turn** — `saveGraph(graph)` → durable headless template (dec #5). After save, `runGraph(id)` in **dry-run/log mode** (dec #16), then slice-end **real Jira write once**.
- **Live sandbox pane** — non-destructive read of `executionState`, reusing the existing `TextHighlighter` (so the extracts UI stays). Retire the Skill Brainstormer modal (dec #18) — replaced by the inline "Save as Skill" on the AI-transform turn.
- **No AuthModal / no token-paste** (dec #14) — integration status comes from `getIntegrationStatus()`. Delete the `AuthModal`/`handleTokenSubmit`/`store-token` code; `store-token` is removed by dec #23.
- **Validation** — every node before materialization passes through `StudioNodeSchema.parse(node)` (zod), via `studioClient`; toast on schema failure.

### Step 4 — (optional slice-1 visuals) Flowchart over `StudioGraph`
- **`ui/src/components/PipelineFlowchart.tsx`** stays board-scoped (Step 1). **Do not** overload it for Studio graphs. If a Studio graph visualization is wanted in slice 1, add a new `ui/components/StudioGraphFlowchart.tsx` that walks `StudioGraph.nodes`/`edges` (respecting `source_handle: "loop"|"true"|"false"`). Mark optional — not in the slice-1 acceptance gate (§6).

### Step 5 — commit the type surface
- Once `studioClient.ts` (`Step 2`) consumes it: `git add ui/src/types/studio.ts ui/src/types/legacy-pipeline.ts ui/src/api/studioClient.ts ui/package.json ui/package-lock.json` + the retargeted board imports — one commit, push to `origin/feat/phase4-workflow-architect`. `AutomationStudio.tsx` (Step 3) lands in its own commit so the type-surface commit is reviewable in isolation.

### Slice-1 acceptance (§6, restated as a runnable checklist)
- [ ] Author the §0 Twistlock example through turns 1–6 interactively;`saveGraph` persists; `runGraph` replays headless.
- [ ] Condition-match routing dispatches; unmatched items land in the undefined-queue (cap 100 enforced by backend — UI reads via `getUndefinedQueue`).
- [ ] 50 run-logs + perpetual aggregate persist (read via `listRuns`).
- [ ] One real Jira write at slice-1 end (after dry-run logging — dec #16).
- [ ] Existing engines untouched; affected vitest files green; board compiles (Corrections A/B).
- [ ] gemma stays the default provider; bob never set default ([[antikythera-avoid-bob-default-provider]]).

---

## Appendix — Decisions Log (29, authoritative)

1. Studio job = full NL workflow generator, interactive "play & select" against live data; Target Integration OPTIONAL.
2. Live sandbox execution = YES (live-results-led, option #3).
3. Supersedes the just-shipped WorkflowArchitect / BlueprintArchitect (those are no longer the relevant surface for this).
4. MCP = add as one adapter type; leverage existing IntegrationHub MCP routing.
5. Saves = hybrid: interactive author → durable headless template (+ optional manual drive).
6. Backend scope: saved graph runs known shapes; **undefined items buffered** for review later (feedback loop grows the graph) — a 4th shape, not A/B/C.
7. Headless = **cron-driven**, wired in THIS redesign (not deferred).
8. Routing = condition-first, **AI-assisted signature matching** fallback.
9. Model tier: simple graphs run **4–8B local model** (constrained classify yes/no); complex graphs (version-upgrade-from-code) need 20B/27B+. The **graph** declares required capability; runtime resolves to model tier. Cron target = simple graphs only.
10. Model-tier→model mapping = new "Model tiers" table in existing AI Engine config (classify / generate / reason-over-code → chosen provider+model; defaults: classify→smallest local, generate→current default, reason-over-code→biggest). Default unchanged for graphs that declare no tier.
11. Two failure flavors: **undefined-queue** ("don't recognize, cheap to triage") vs **escalate-to-human** ("recognize but can't safely complete" — destructive writes pause via existing orchestrator REVIEW-gate shape).
12. Author-time model suggester = BUILD (1): proposal emits `capability` + `suggested_model_tier` for free. DROP (2) the auto-benchmark prober — replay history yields that signal for free.
13. Skill = reusable AI-transform node, **persisted to disk** (not in-memory dict). Transform node is one-off or "save as Skill." Refine/fix existing skill path, don't delete wholesale.
14. Credentials = single source = env vars (`~/.antikythera/.env`). Studio shows integration status + links to Integrations Hub. **No** token-paste modal, no store-token endpoint.
15. First slice = interactive authoring loop (query→fan-out→cards→pick→AI-transform→conditional-action→save) **+** runnable **deterministic** headless path (condition-match routing + replay history + undefined queue + cron). AI-signature fallback = Phase 2 (slice 1 has NO LLM at cron).
16. Slice-1 Jira writes = dry-run/log first, **real writes at the END of slice 1**.
17. Headless engine = new dedicated **PathStepGraphEngine**; leave the two existing engines untouched (zero regression risk to just-shipped work); share model defs via `api/models/automation.py` import; **no** shared-evaluator extraction in slice 1.
18. Skill Brainstormer loop = **retire** from the Studio; re-anchor Skill as the persisted runtime unit the transform-node reuses.
19. Branch signature shape = **(b) Condition + NL signature line**. Condition = exact matches for free; NL signature = corpus the 4–8B classifier matches paraphrased items against in Phase 2. Schema **reserves `signature: str` in slice 1** even though unused for routing (avoids Phase 2 migration). Must stay short labeled examples or 4–8B reliability sags.
20. Undefined-queue retention = persist until resolved, **cap 100/graph**, no auto-expiry.
21. Replay-history retention = last **50 full run-logs** per graph + perpetual aggregate (counts matched/undefined/escalated over time).
22. Frontend types = single shared `ui/src/types/studio.ts` (richer node types than backend PathStep). **Amended 2026-07-21 (reality check):** the two "legacy Pipeline components" (`PipelineDashboard`, `PipelineFlowchart`) + `usePipelineState.ts` are the **Kanban board**'s pipeline-detail view (`App.tsx:349`, backed by `/api/state` + `/api/pipelines/*`), not Studio machinery. `Path`/`PathStep`/`Pipeline`/`PipelineItem`/`PipelineState` are **already absent from `src/types.ts` on HEAD**, so the migration is **not** "retarget those components onto `StudioNode`" — that would couple the live board to the Studio graph model. Instead: (a) **restore the missing legacy symbols locally** (`ui/src/types/legacy-pipeline.ts`, board-scoped) so the board compiles again; (b) `StudioNode`/`StudioGraph` are the only node types for the **Studio** surface only. The board and Studio remain disjoint surfaces sharing `studio.ts`'s `Condition*`/`CapabilityTier` primitives where useful, not the node union. See §7 Correction A.
23. Dead endpoints = **DELETE** `/api/automation/templates` (hardcoded 3-fake-template stub) and GET `/api/automation/state` (no consumer).
24. Migration = **NO migration** — old Studio writes nothing durable (component-state currentPath, in-memory skills_db). Delete old component + skills_db on the server restart.
25. Studio tab = **replace in place** (old one non-functional).
26. Bob shell = untouched, not on critical path (constraint: don't propose a bob_shell node in sandbox).
27. Routing trust = routing to a saved branch = executing a user-approved action = fine to run; small model never invents actions → **no extra dry-run guard** for Phase 2 routing. (Dry-run only applies to slice-1's write rollout, dec #16.)
28. Backend query path = **build list/vector query actions on adapters** (fetch_resource today returns 1, never a list).
29. Plan format = **one comprehensive plan file**: End-state design → First slice → Sequenced phases → Verification + Decisions-log appendix.

---

## Related
- `[[antikythera-backend-template-hardening]]` — deferred hardening adjacent to this redesign's new endpoints (Phase 3).
- `[[antikythera-ai-touchpoints-map]]` — redesign adds cron-time 4–8B classification + keeps authoring through LLMClient.
- `[[antikythera-avoid-bob-default-provider]]` — keep gemma default; don't push bob.
- `[[antikythera-project-status]]` — canonical backlog doc.
