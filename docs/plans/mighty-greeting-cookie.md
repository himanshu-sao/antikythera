# Automation Studio Redesign — Plan

> Turn-based, live-results-led compiler. Human reacts to real returned data; the system materializes those reactions into a durable workflow graph that runs headlessly on cron.

**Status:** design locked 2026-07-20 (29 decisions); this plan written 2026-07-21.
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
- Frontend: single shared `ui/src/types/studio.ts` (dec #22); **migrate the two legacy Pipeline components (`PipelineDashboard`, `PipelineFlowchart`) onto `studio.ts`** — `StudioNode` becomes the only node type, the `PathStep` symbol is deleted (decision resolved 2026-07-21: migrate, not restored-base).
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
- **Legacy Pipeline:** the two migrated components (`PipelineDashboard`, `PipelineFlowchart`) compile against the new `studio.ts` / restored base type.
- **Skill persistence:** a "save as Skill" AI-transform survives server restart (disk-backed, dec #13).
- **Credentials:** no token-paste modal; Studio shows integration status from env vars (dec #14).

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
22. Frontend types = single shared `ui/src/types/studio.ts` (richer node types than backend PathStep); **migrate** the two legacy Pipeline components (PipelineDashboard, PipelineFlowchart) that import the deleted `PathStep` symbol onto `studio.ts` (decision resolved 2026-07-21 — migrate both, **no** restored base type).
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
