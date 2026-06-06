# Antikythera UI Redesign — Agent Context & Status File

> **FOR AI AGENTS**: Read this entire file before doing any work. This is the single source of truth for the major UI redesign task. 
> **CRITICAL RULE**: Implement the changes **one page/view at a time**, beginning with the **landing page (Lifecycle Orchestrator)**. Do not build multiple pages at once. This allows the user to review and confirm correctness at each step.
> **TESTING RULE**: After making changes to a page or view, restart the server using `./stop_antikythera.sh` followed by `./start_antikythera.sh` from the project root to verify the updates.
> After completing any work session, update **Section 8 (Current Status)** and append an entry to **Section 9 (Session Log)**. Do not remove existing entries — only append/update.

---

## 1. Project Overview

**Antikythera** is a full-stack AI lifecycle orchestration platform. The UI is a React 19 + Vite 8 + Tailwind CSS 4 app (at `ui/`) that manages AI work items through a 10-stage Kanban pipeline, automation workflows, integrations with external tools, and AI engine configuration.

**Tech Stack:**
- **Frontend**: React 19, Vite 8, TypeScript 6, Tailwind CSS 4, `@dnd-kit` (drag-and-drop), `react-hot-toast`, `mermaid`, `react-markdown`, `lucide-react`
- **Backend**: Python FastAPI on port `8006`
- **Dev Frontend**: `http://localhost:5173`
- **Start all services**: `./start_antikythera.sh` (from project root)
- **Stop all services**: `./stop_antikythera.sh` (from project root)
- **Run tests**: `cd ui && npm run test`

---

## 2. What This Redesign Actually Is

This is **NOT** a color-swap. This is a **complete layout and structural overhaul** of the UI, moving from a flat tab-bar design to a modern application shell with a persistent left navigation sidebar, icon support, collapsible states, a contextual top toolbar, and panel-based content layout — similar to VS Code, Linear, or Notion.

### Current Layout (BEFORE)

```
┌──────────────────────────────────────────────────────────────────────┐
│ [Lifecycle] [Studio] [Workflows] [Integrations] [AI Engine] [+Pipeline]│ ← horizontal tab bar
│                                                [+ New Idea] [Refresh] │
├──────────────────────────────────────────────────────────────────────┤
│   Full page content area (kanban / studio / settings)                 │
└──────────────────────────────────────────────────────────────────────┘
```

**Problems with current layout:**
- No icons anywhere — purely text tabs
- Tabs overflow horizontally when pipelines are added
- No visual hierarchy — everything is the same weight
- Clicking a card opens a centered full-screen modal, blocking the board entirely
- Workflows and Integrations show "coming soon" placeholder text (broken tabs)
- No dark mode

---

### Target Layout (AFTER) — from screenshots

```
┌─────────────────┬────────────────────────────────────────────────────────────────────┐
│ (C) Antikythera  │  [⊞ Lifecycle Orchestrator] [Studio] [Workflows] [Integ] [AI Engine]│
│ ────────────── │  [+ New Idea (dark teal)]  [avatar]                                │
│ ⌂  Home        ├────────────────────────────────────────────────────────────────────┤
│ ⊞  Orchestrator│  PAGE TITLE                            [action buttons top-right]   │
│ ✏  Studio      │  page subtitle                                                     │
│ ◇  Workflows   │                                                                    │
│ ⊛  Integrations│  MAIN CONTENT (Kanban / Integrations grid / AI config / Studio)    │
│ ⊙  AI Engine   │                                                                    │
│ ⚙  Settings    │                                                                    │
│                │                                                                    │
│                │                                                                    │
│ ────────────── │                                                                    │
│ [A] Acme Corp  │                                                                    │
│     Enterprise │                                                                    │
└─────────────────┴────────────────────────────────────────────────────────────────────┘
```

> **Key from screenshots**: The left sidebar is ALWAYS the primary navigation. The top bar shows the current section name + the other section tabs + global actions. This is NOT a hamburger menu — it's always visible.

---

## 3. Detailed Component Specifications

---

### 3.1 Left Navigation Sidebar — from screenshots

**File to modify**: `ui/src/App.tsx`

**Exact structure from all 4 screenshots:**
```
┌────────────────────────────────┐
│  (C) Antikythera               │  ← Teal circle logo + "Antikythera" bold text
├────────────────────────────────┤
│  ⌂   Home                      │  ← Lucide `Home` icon
│  ⊞   Orchestrator              │  ← Lucide `LayoutGrid` or `Columns` icon
│  ✏   Studio                    │  ← Lucide `PenLine` icon
│  ◇   Workflows                 │  ← Lucide `Workflow` or `Diamond` icon
│  ⊛   Integrations              │  ← Lucide `Globe` or `Plug` icon
│  ⊙   AI Engine                 │  ← Lucide `Cpu` or `Bot` icon
│  ⚙   Settings                  │  ← Lucide `Settings` icon
├────────────────────────────────┤
│  [avatar] Acme Corp       ∨    │  ← Bottom user section
│           Enterprise           │
└────────────────────────────────┘
```

**Visual rules (from screenshots):**
- **Active item**: dark teal pill background (`var(--accent)` @ ~15% opacity), accent-colored icon and text, no left border (pill shape covers full width with padding)
- **Inactive item**: gray icon + gray text, no background
- **Hover**: light gray bg (`var(--panel-2)`)
- **Logo**: small teal circle with a `C` or ring icon + "Antikythera" in `font-semibold text-base`
- **User section** at bottom: small avatar circle + name + "Enterprise" tag + chevron-down for dropdown
- Sidebar background: **white** (`#ffffff`) in the screenshots (not cream — pure white left rail)
- Sidebar border-right: `1px solid var(--border)`
- Nav item padding: `10px 16px`, `border-radius: 8px`, `gap: 10px`
- Icon size: `18px`
- Label size: `text-sm font-medium`

**Width:**
- Expanded: `180px` (screenshots show a narrower sidebar than typical)
- Collapsed: `56px` (icon only — keep as optional enhancement)
- Full height: `100vh`
- Transition: `width 200ms ease`

**Persistence**: `isSidebarCollapsed` and `theme` in `localStorage`

**Note on "Home" nav item**: The screenshots show a "Home" item at the top of the nav. This does NOT exist in the current codebase. For now, make it show the **Kanban board** (same as Orchestrator tab) — it is cosmetic for UI completeness.

---

### 3.2 Top Navigation Bar — from screenshots

**File to modify**: `ui/src/App.tsx`

This is a **horizontal top bar** that shows the current section name + other section tabs as secondary nav + global action buttons. It sits to the RIGHT of the sidebar.

**Exact structure from screenshots:**
```
┌──────────────────────────────────────────────────────────────────────┐
│ [⊞ Lifecycle Orchestrator] [Studio] [Workflows] [Integrations] [AI Engine]    [+ New Idea] [avatar] │
└──────────────────────────────────────────────────────────────────────┘
```

- The **active section** is shown with an icon + text, accent-colored text + underline indicator
- Other sections: gray text, no underline
- Clicking a top nav item navigates to that section (same as sidebar)
- **Right side**: `[+ New Idea]` button (solid dark teal bg `#0b6b72`, white text, rounded `8px`)
- **User avatar**: circular image, right-most element
- **Refresh icon**: small icon-only button between AI Engine and + New Idea (visible on Kanban/Orchestrator view)
- Height: `52px`
- Background: `white` / `var(--panel)`, border-bottom `1px solid var(--border)`
- Top bar items font: `text-sm`

---

### 3.3 Card Detail — Slide-in Right Drawer

**File to modify**: `ui/src/App.tsx`

**Current behavior**: clicking a card opens a centered full-screen blocking modal.

**New behavior**: clicking a card slides in a panel from the right. The kanban board stays visible behind with a semi-transparent backdrop.

```
┌───────────────────────────┬──────────────────────┐
│                           │  Card ID / Title      │
│   Kanban board            │  [Edit] [✕]           │
│   (still visible,         │  ─────────────────    │
│    dimmed by backdrop)    │  ArtifactViewer /     │
│                           │  CardEditor content   │
└───────────────────────────┴──────────────────────┘
```

**Specs:**
- Width: `520px` (`min(520px, 90vw)` on small screens)
- Position: `fixed right-0 top-0 h-full z-40`
- Animation: `translateX(100%)` → `translateX(0)`, `250ms ease`
- Backdrop: `fixed inset-0 bg-black/30`, click-to-close
- Keep ALL existing logic: `editMode`, `CardEditor`, `ArtifactViewer`, `selectedRunId`

---

### 3.4 Lifecycle Orchestrator / Kanban Board — from screenshot 3

**File to modify**: `ui/src/components/KanbanColumn.tsx`

#### Overall Page Layout:
- Title: "Lifecycle Orchestrator" shown in the top nav bar (not repeated as a page heading)
- Board is a **horizontally scrollable flex row** of columns
- Bottom of each column: `+ Add idea` text button (centered, muted color)
- Page background: white/near-white

#### Column Header (exact from screenshot):
```
┌──────────────────────────────────────┐
│ [icon]  Intake             0  [+]   │
└──────────────────────────────────────┘
```
- Icon: styled SVG/Lucide icon, **teal-tinted box** with rounded corners (not emoji)
  - Intake → `Inbox` icon in a soft blue-teal box
  - Refinement → `Pencil` icon in a soft peach/orange box
  - Review Spec → `FileText` / `ClipboardList` icon in a soft purple box
  - Architecture → `LayoutGrid` / `Network` icon in a soft teal box
  - Review Arch → `Eye` / `CheckSquare` icon in a soft blue box
  - Testing → `TestTube` / `FlaskConical` / `User` icon in a soft green box
  - Approved → `CheckCircle` icon in a green box
  - Executing → `Zap` icon in a teal box
  - Done → `Archive` icon in a gray box
- Column name: `text-sm font-semibold text-gray-700`
- Count badge: plain number, muted gray, small
- `[+]` button: small `+` icon, top-right of header, accent color on hover
- Header is NOT separated by a border — it flows into the column body

#### Column Body:
- Background: `white` border `1px solid var(--border)` (light gray `#e5e7eb`)
- Border radius: `12px` (from screenshot, relatively tight rounding)
- Min-width: `240px` fixed
- Min-height: fills available vertical space
- Padding: `12px`
- Drop highlight: `2px solid var(--accent)` border + very subtle teal bg tint

#### Empty State (exact from screenshot):
```
          ┌──────────────────────────┐
          │                          │
          │    [outline icon]        │  ← Lucide icon, light gray, ~32px
          │  No ideas yet            │  ← text-sm font-medium text-gray-500
          │  Ideas added here will   │  ← text-xs text-gray-400, centered
          │  start your journey.     │
          └──────────────────────────┘
```
- Empty state icon is a **outline-style lucide icon** matching the column stage (e.g., `Inbox` for Intake)
- Custom subtitle text per column:
  - Intake: "Ideas added here will start your journey."
  - Refinement: "Add details and context to shape the idea."
  - Review Spec: (has card, skip)
  - Architecture: "Approved specs will move here."
  - Review Arch: "No items for review"
  - Testing: "QA and validation happen here."

#### Card (exact from screenshot — the `Testing Memory Agent` card):
```
┌──────────────────────────────────────────┐
│ ⚠ ACTION REQUIRED                   ...  │  ← amber badge top-left, ⋮ menu top-right
│ [TEST] [HIGH] [100%]                      │  ← tag + priority + confidence badges
│                                          │
│ Testing Memory Agent                     │  ← text-base font-semibold
│ Validates memory retention and retrieval │  ← text-sm text-gray-500, 3 lines max
│ across sessions and context boundaries.  │
│                                          │
│ TEST-MEM-001          -        6/5/2026  │  ← footer: ID · · · date
└──────────────────────────────────────────┘
```

**Card details:**
- Background: `white`, border: `1px solid #e5e7eb`, border-radius: `10px`
- Box shadow: `0 1px 3px rgba(0,0,0,0.08)`
- Padding: `14px`
- Hover: `box-shadow: 0 4px 12px rgba(0,0,0,0.12)`, `transform: translateY(-1px)`
- ACTION REQUIRED badge: amber bg `#fef3c7`, amber text `#d97706`, small dot `●`, `text-xs font-semibold`
  - When `EXECUTING`: teal/cyan pulsing badge `⚡ AGENT WORKING`
- `⋮` (kebab) menu: always visible top-right, gray, opens edit/delete options
- Tag badge (`[TEST]`): from `tags[]` — gray bg `#f3f4f6`, gray text `#6b7280`, `text-xs`
- Priority badge (`[HIGH]`): amber bg `#fef3c7`, amber text `#92400e`, `text-xs font-semibold`
- Confidence badge (`[100%]`): light gray bg, gray text, `text-xs`
- Footer: ID in `text-xs font-mono text-gray-400` · date in `text-xs text-gray-400`, space-between
- Bottom of each column: `+ Add idea` centered text link

---

### 3.5 Automation Studio — Full Page Rebuild — from screenshot 4

**File to modify**: `ui/src/components/AutomationStudio.tsx`

The current layout is a simple 2-column split. The target is a **3-column panel layout** with a numbered step workflow on the left.

#### Page Structure:
- **Page header** (inside the main content area, NOT the top nav bar):
  - Title: `Automation Studio` in `text-2xl font-bold`
  - Subtitle: `Record your process. The AI compiles it into logic.` in `text-sm text-muted`
  - (No top-right buttons — the + New Idea button is in the global top nav)
- **3-column body** below the header:

```
┌─────────────────────┬──────────────────────────────┬──────────────────────┐
│  LEFT PANEL          │  CENTER PANEL                 │  RIGHT PANEL         │
│  (Steps list)        │  (Live Sandbox)               │  (Path Sequence)     │
│  ~1/3 width         │  ~1/2 width                   │  ~1/4 width          │
└─────────────────────┴──────────────────────────────┴──────────────────────┘
```

#### Left Panel — "Compose Instruction" (numbered step UI):
- Shows steps as a vertical numbered list:
  - `1  Compose Instruction` — **active/expanded** (white card, border, shadow)
  - `2  Refine & Confirm` — collapsed (gray text, no card)
  - `3  Add to Workflow` — collapsed (gray text, no card)
- Step 1 expanded content:
  - **AI Model selector**: label `AI Model`, a dropdown showing `[provider-icon] Llama 3.1 (Ollama) ▼` with a `⚙` settings icon to the right
  - **Instruction textarea**: label `Your instruction`, multi-line textarea with placeholder, char count `86 / 2000` bottom-right
  - **Action chips row** (below textarea): `[⊕ Add context]` `[{} Use variable]` `[⊟ Examples]` — small pill buttons, ghost style
  - **Propose Step button**: full-width, dark teal bg `#0b6b72`, white text `✦ Propose Step`, `border-radius: 8px`
- All panels have white bg, `var(--border)` border, `border-radius: 12px`

#### Center Panel — "Live Sandbox":
- Header row: `Live Sandbox` (text-base font-semibold) + `● Live` green dot + "Live" text (green)
- **Active Variables** table section:
  - Column headers: `VARIABLE` | `TYPE` | `VALUE` (all-caps, text-xs, muted)
  - Each row: variable name (monospace, accent color) | type (gray) | value (normal text)
  - Bottom of table: `+ Add variable` text link (accent color)
- **Step Preview** section (below variables):
  - Dark code block bg (`#1e1e2e` or similar dark), monospace font
  - Line numbers on left, syntax-colored YAML
  - Bottom-right: `Test Step` text link (accent color)

#### Right Panel — "Current Path Sequence":
- Header: `⚙ Simulation mode` badge in amber — top-right of panel area
- Below: section label (implicit from content)
- **Numbered steps list** (vertical timeline):
  - Each item: circle with number (dark filled), step title `text-sm font-semibold`, step description `text-xs text-gray-500`
  - Example:
    - `① Jira: Search Issues` / `Find tickets with status New`
    - `② Process Results` / `Summarize by priority`
    - `③ Notify User` / `Send summary via Slack`
  - Timeline line connects circles vertically
- Bottom: `+ Add Step` text link (accent color)

#### What to KEEP from existing `AutomationStudio.tsx` logic:
- `handlePropose()` → still fires from the Propose Step button
- `handleAccept()` / `handleReject()` → still handle AI proposals
- `handleExtract()` / `handleSaveSkill()` → brainstorm skill promotion
- `sandboxState` variables table → maps to "Active Variables" table (add TYPE column — derive type from `typeof value`)
- `currentPath` steps → maps to "Current Path Sequence" panel
- `proposal` state → when set, expands step 2 "Refine & Confirm" with the proposal card
- `isAuthModalOpen` / `AuthModal` → keep exactly as-is
- AI Model selector: add a `selectedModel` state that calls `/api/ai-engine/config` to fetch available models; default to first model

---

### 3.6 Integrations Hub — Full Page Rebuild — from screenshot 1

**File to modify**: `ui/src/components/IntegrationsManager.tsx`

#### BEFORE (current):
The current `IntegrationsManager` has a sidebar + detail panel layout.

#### AFTER (target — match screenshot exactly):

**Page header:**
- Title: `Integrations Hub` in `text-2xl font-bold`
- Subtitle: `Connect external services via Native Adapters or MCP Servers` in `text-sm text-muted`
- Top-right buttons: `[Manage Secrets]` (outline style, `text-sm`) + `[+ Add Connection]` (solid dark teal)

**Filter bar** (below header):
```
[🔍 Search integrations...]    [All Types ▼]    [All Status ▼]
```
- Search: `240px` width input, `text-sm`, magnifying glass icon prefix
- All Types dropdown: filters by `MCP` vs `Native Adapter`
- All Status dropdown: filters by `Connected` / `Error` / `Warning` / `Disconnected`

**Card grid:**
- CSS Grid: `repeat(auto-fill, minmax(240px, 1fr))` — fills to 4 columns at normal width
- Gap: `16px`
- Cards are filterable by search + type + status

**Integration Card (exact from screenshot):**
```
┌──────────────────────────────────┐
│ [icon]  Jira Cloud          ⋮   │  ← provider icon (brand-colored) + name + kebab menu
│          MCP                     │  ← type badge: "MCP" or "Native Adapter" in gray text
│                                  │
│ Issue tracking and project       │  ← description, 2 lines max, text-sm text-gray-500
│ management                       │
│                                  │
│ ● Connected                      │  ← status badge: green dot + "Connected"
│ Last sync: 2m ago                │  ← small gray text
│ ──────────────────────────────── │
│ . . .                            │  ← bottom action row: 3 dots / quick actions
└──────────────────────────────────┘
```

**Card specifics:**
- Background: `white`, border: `1px solid #e5e7eb`, border-radius: `12px`
- Padding: `16px`
- Hover: subtle shadow elevation + border color becomes `var(--accent)`
- Provider icon: **brand-colored square** with rounded corners, `36px`, containing a letter/logo
  - Jira → blue box with Jira logo `J`
  - Slack → multi-color Slack `#` icon
  - GitHub → dark gray Octocat circle
  - Confluence → blue `X`-shape box
  - ServiceNow → black circle with white icon
  - Salesforce → blue cloud icon
  - PagerDuty → green `P` circle
- Type label below name: `text-xs text-gray-400` — `MCP` or `Native Adapter`
- Status badges:
  - `● Connected` → green dot `#16a34a` + green text
  - `✕ Error` → red `×` + red text `#dc2626`
  - `⚠ Warning` → amber `⚠` + amber text `#d97706`
  - `○ Disconnected` → gray dot + gray text
- `Last sync: Xm ago` → `text-xs text-gray-400`
- Bottom `...` row → horizontal dots (ellipsis) or quick action icon buttons
- `⋮` kebab menu (top-right of card): opens dropdown with `Edit`, `Test Connection`, `Disconnect`, `Remove`

**"Add Connection" CTA card** (last card in grid):
```
┌──────────────────────────────────┐
│                                  │
│         +                        │  ← large `+` icon, muted gray
│   Add Connection                 │  ← text-sm font-semibold text-gray-700
│   Connect a new service          │  ← text-xs text-gray-400
│   or MCP server.                 │
│                                  │
└──────────────────────────────────┘
```
- Border: `2px dashed #d1d5db`, bg: `#f9fafb`, border-radius `12px`
- Clicking opens the "Add Integration" modal/form (existing logic)

#### What to KEEP from existing `IntegrationsManager.tsx` logic:
- All fetch calls to `/api/integrations` and `/api/mcp/tools`
- `testConnection()` function
- Add/edit/delete integration modals
- MCP tool execution panel
- Auth token storage

#### What CHANGES in layout:
- Remove the sidebar + detail panel layout
- Replace with the card grid described above
- Clicking a card opens a **slide-in drawer** (right side, consistent with card detail drawer pattern) showing connection details + test/edit options

---

### 3.7 AI Engine — Full Page Rebuild

**File to modify**: `ui/src/components/AIEngineSettings.tsx`

> ⚠️ This is NOT a "visual polish" pass. The user has provided a before/after screenshot. The AI Engine page needs a **full component rebuild** matching the target design exactly.

---

#### BEFORE (current state):
```
┌─────────────────────────────────────────────────────────────────┐
│ AI Engine Configuration          [Refresh]  [+ Add Model]       │
│ Manage AI models, providers, and connection settings            │
├─────────────────────────────────────────────────────────────────┤
│ [Overview] [Models] [Providers] [Settings]                      │  ← 4 sub-tabs only
├─────────────────────────────────────────────────────────────────┤
│ ┌──────────┐ ┌────────────┐ ┌──────────────────┐ ┌──────────┐  │
│ │Total     │ │Default     │ │Configured        │ │API Keys  │  │  ← 4 stat cards
│ │Models: 6 │ │Model:llama │ │Providers: 3      │ │Set: 3/6  │  │
│ └──────────┘ └────────────┘ └──────────────────┘ └──────────┘  │
│                                                                 │
│ ┌─── Current Default Model (blue tinted) ───────────────────┐  │
│ │ Llama 3.1 (Ollama)  OLLAMA • Context: 8192 tokens      ⚙  │  │
│ └────────────────────────────────────────────────────────────┘  │
│                                                                 │
│ ┌── Quick Start ──────┐  ┌── Connection Status ─────────────┐  │
│ │ ✅ Ollama: no key    │  │ ● Ollama (3 models)              │  │
│ │ 🔑 Cloud: set keys  │  │ ● Nvidia Nim (2 models)          │  │
│ │ ⚡ Test connections  │  │ ● Google Gemma (1 model)         │  │
│ └─────────────────────┘  └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

#### AFTER (target — match this exactly from screenshot):
```
┌─────────────────────────────────────────────────────────────────┐
│ AI Engine Configuration                  [↻ Refresh] [+ Add Model (dark teal)] │
│ Manage AI models, providers, and connection settings            │
├─────────────────────────────────────────────────────────────────┤
│ [Overview*] [Models] [Providers] [Connections] [Settings] [Logs]│  ← 6 sub-tabs, accent underline
├─────────────────────────────────────────────────────────────────┤
│ ┌──────────┐ ┌──────────┐ ┌──────────────┐ ┌────────┐ ┌──────────────────────┐ │
│ │Total     │ │Active    │ │Configured    │ │API Keys│ │Default Model         │ │  ← 5 stat cards
│ │Models: 12│ │Models: 8 │ │Providers: 5  │ │7 / 10  │ │Llama 3.1 (Ollama)  📋│ │
│ └──────────┘ └──────────┘ └──────────────┘ └────────┘ └──────────────────────┘ │
│                                                                 │
│ ┌── Provider Health ──────────────────┐ ┌── Model Inventory ──────────────────┐│
│ │                                     │ │ [🔍 Search models...]  [All Prov. ▼]││
│ │ [icon] Ollama      3 models Healthy │ │                                      ││
│ │ [icon] NVIDIA NIM  2 models Healthy │ │ [icon] Llama 3.1 (Ollama) [Default] ││
│ │ [icon] IBM Granite 2 models Degraded│ │        Ollama    8,192    Ready   ⋮  ││
│ │ [icon] Google Gem  2 models Healthy │ │ [icon] CodeLlama (Ollama)            ││
│ │ [icon] OpenAI      3 models Error   │ │        Ollama    4,096    Ready   ⋮  ││
│ │                                     │ │ [icon] NVIDIA Nemotron-3 8B          ││
│ │                                     │ │        NVIDIA NIM 128,000 Needs Key ⋮││
│ │                                     │ │ [icon] Granite 3.1 8B Instruct       ││
│ │                                     │ │        IBM Granite 8,192  Ready   ⋮  ││
│ └─────────────────────────────────────┘ └──────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

#### Detailed Rebuild Specification

**Header:**
- Title: `AI Engine Configuration` in `text-2xl font-bold`
- Subtitle: `Manage AI models, providers, and connection settings` in `text-sm text-muted`
- Top-right buttons: `[↻ Refresh]` (outline style) and `[+ Add Model]` (solid dark teal bg, white text)

**Sub-tabs (add 2 new ones):**
- Current: `Overview | Models | Providers | Settings`
- Target: `Overview | Models | Providers | Connections | Settings | Logs`
- Active tab: accent-colored text + 2px accent underline border
- Inactive: muted text, no border, hover shows lighter accent text

**Stats Row (5 cards, not 4):**

| Card | Label | Value Style |
|---|---|---|
| 1 | Total Models | large bold number |
| 2 | Active Models | large bold number ← **NEW** |
| 3 | Configured Providers | large bold number |
| 4 | API Keys Set | `X / Y` format, accent-colored fraction |
| 5 | Default Model | Model name in accent color + 📋 copy-to-clipboard icon |

Each stat card: white bg, `1px solid var(--border)` border, `var(--radius)` rounded, `12px 16px` padding. Label in `text-xs text-muted uppercase`. Value in `text-2xl font-bold`.

---

**Overview Tab — Two-Column Panel Layout:**

Both panels sit side by side on one row. Each panel: white bg, `var(--border)` border, `var(--radius-lg)` rounded, no fixed height (grows with content).

**Left Panel — "Provider Health":**
- Title: `Provider Health` in `text-base font-semibold` inside panel header
- A table/list — each row:
  ```
  [provider-icon]  Provider Name    N models    [Status Badge]
  ```
  - Provider icon: colored square/circle icon (use `lucide-react` icons or emoji-style colored boxes matching provider brand)
  - Status badges:
    - `Healthy` → green text `#16a34a`
    - `Degraded` → orange/amber text `#d97706`
    - `Error` → red text `#dc2626`
  - Row hover: subtle `var(--panel-2)` background
  - No border between rows, just `py-3` padding with a thin `border-b var(--border)` divider

**Right Panel — "Model Inventory":**
- Title: `Model Inventory` in `text-base font-semibold` inside panel header
- Top controls row: `[🔍 Search models... input]` + `[All Providers ▼ dropdown]` (right-aligned)
- A table/list — each row:
  ```
  [provider-icon]  Model Name  [Default badge?]   Provider    Context    Status    [⋮]
  ```
  - Provider icon: small colored square icon per provider brand
  - Model name: `text-sm font-medium`
  - `[Default]` badge: only on the default model — small pill, outline style, `var(--accent)` border + text
  - Provider label: `text-xs text-muted`
  - Context: `text-sm text-muted` (e.g. `8,192`)
  - Status:
    - `Ready` → green text
    - `Needs Key` → amber/orange text
    - `Testing` → accent/teal text
    - `Failed` → red text
  - `⋮` kebab menu button: appears on row hover, opens a context menu with: Set as Default, Edit, Test Connection, Remove
  - Row hover: `var(--panel-2)` background

---

#### State Mapping (existing API data → new UI fields)

The existing `AIConfig` interface already has most of what's needed. Map as follows:

| New UI Field | Source in existing code |
|---|---|
| Total Models | `config.models.length` |
| Active Models (NEW) | `config.models.filter(m => m.api_key_set \|\| m.provider === 'ollama').length` |
| Configured Providers | `new Set(config.models.map(m => m.provider)).size` |
| API Keys Set (X/Y) | `config.models.filter(m => m.api_key_set \|\| m.provider === 'ollama').length` / `config.models.length` |
| Default Model name | `config.models.find(m => m.is_default)?.name` |
| Provider Health status | Derived from `testResults[model_id]` — group by provider, if any model `failed` → `Error`, if some missing key → `Degraded`, all ready → `Healthy` |
| Model row status | `testResult?.success ? 'Ready' : !model.api_key_set && model.provider !== 'ollama' ? 'Needs Key' : 'Ready'` |

#### New sub-tab content (Connections, Logs):
- **Connections**: Show the existing `connection_settings` form (timeout, retries, fallback, caching) — already implemented in Settings tab. Move it here or duplicate it under Connections.
- **Logs**: Show a placeholder "Coming soon — AI request logs will appear here" for now.

#### What to KEEP from existing code (do not remove):
- `testConnection()` function and UI
- `saveApiKey()` / `setDefaultModel()` functions
- `showApiKeyModal` API key entry modal
- `isAddingModel` / add model UI
- All fetch calls to `/api/ai-engine/config`, `/api/ai-engine/test-connection`, etc.
- Provider metadata array (`providers`) — keep but add icons for IBM Granite and OpenAI

---

### 3.8 CSS Variables & Design System

**File to modify**: `ui/src/index.css`

Add CSS custom properties for full light/dark theming:

```css
@import "tailwindcss";

:root {
  --bg:           #f4f3ef;
  --panel:        #fcfbf8;
  --panel-2:      #f1eee8;
  --border:       rgba(39, 37, 29, 0.12);
  --text:         #27251d;
  --text-muted:   #68645d;
  --accent:       #0b6b72;
  --accent-hover: #0a5c62;
  --accent-light: #d5e7e6;
  --shadow-sm:    0 2px 8px rgba(0,0,0,0.06);
  --shadow-md:    0 8px 24px rgba(0,0,0,0.10);
  --shadow-lg:    0 16px 40px rgba(0,0,0,0.14);
  --radius:       12px;
  --radius-lg:    18px;
  --sidebar-w:    220px;
  --sidebar-collapsed-w: 56px;
}

[data-theme="dark"] {
  --bg:           #161412;
  --panel:        #1e1c18;
  --panel-2:      #252220;
  --border:       rgba(255, 255, 255, 0.09);
  --text:         #f0ede6;
  --text-muted:   #9e9a93;
  --accent:       #14b8c4;
  --accent-hover: #12a4af;
  --accent-light: rgba(20, 184, 196, 0.15);
  --shadow-sm:    0 2px 8px rgba(0,0,0,0.30);
  --shadow-md:    0 8px 24px rgba(0,0,0,0.40);
  --shadow-lg:    0 16px 40px rgba(0,0,0,0.55);
}
```

Also add:
- `.hover-lift { transition: transform 0.15s ease, box-shadow 0.15s ease; }`
- `.hover-lift:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }`
- Extended `custom-scrollbar` already present — keep it
- Google Fonts import for Inter (or use system font stack)

---

## 4. Functionality That Must Be Preserved (Do Not Break)

- ✅ Drag-and-drop between Kanban columns (`@dnd-kit`, `DragOverlay`, `SortableContext`)
- ✅ Card detail view: `ArtifactViewer` with artifact tabs, markdown rendering, mermaid diagrams, review form
- ✅ Card editing: `CardEditor` form inside the detail panel
- ✅ Delete confirmation modal
- ✅ Create item modal (`CreateItemModal`)
- ✅ Pipeline tabs: dynamic tabs added per pipeline from `/api/pipelines`
- ✅ Pipeline dashboard: clicking a pipeline tab shows `PipelineDashboard`
- ✅ Workflow builder: `WorkflowArchitect` + `TransactionPanel` in `BuilderModal`
- ✅ Automation Studio: AI step recorder with `TextHighlighter` + brainstorm (logic only, layout changes)
- ✅ Integrations: add/edit/delete/test connections + MCP tool runner (logic only, layout changes)
- ✅ AI Engine: model list, test connection, set default, set API keys (logic only, layout changes)
- ✅ Real-time polling in `usePipelineState`
- ✅ Keyboard shortcut: `Escape` closes open panels/modals
- ✅ Virtual Board: `VirtualBoard` component
- ✅ Toast notifications via `react-hot-toast`

---

## 5. Known Bugs in Current Code (Fix As Part of Redesign)

1. **`handleDragStart` in `App.tsx`**: References `active.id` before destructuring from `event`.
   - **Fix**: Change `String(active.id)` → `String(event.active.id)`

2. **`WorkflowArchitect.test.tsx` goal text**: Tests assert `Complete map of affected files...` but `LIFECYCLE_PIPELINE[0].goal` in `types.ts` says `Understand the problem domain and gather requirements`.
   - **Fix**: Update test assertion text to match `types.ts` values.

3. **`ManagementModals.test.tsx` `TransactionProposal` shape mismatch**: Mock returns `{ id, status, context, plan, verification }` but interface expects `{ proposal_id, phase, description, actions }`.
   - **Fix**: Update mock to match the interface, or update interface to match real API shape.

4. **`App.polling.test.tsx` call count off-by-one**: `loadPipelines()` fires on mount alongside `fetchState()`, so initial fetch count is 2, not 1.
   - **Fix**: Update expected call count OR count only `/api/state` calls.

5. **`WorkflowArchitect.tsx` polling interval**: Interval runs every 5s in tests causing log noise. Already fixed by adding `currentPhase` prop — verify tests pass cleanly.

---

## 6. File Map

```
antikythera/
├── UI_REDESIGN_CONTEXT.md        ← THIS FILE — read before starting work
├── antikythera-redesign-mockups.html  ← Visual reference mockups
├── start_antikythera.sh          ← Start backend + frontend + orchestrator
├── stop_antikythera.sh           ← Kill all services, clear ports 8006 & 5173
└── ui/
    ├── vite.config.ts            ← Vitest config (e2e excluded)
    ├── src/
    │   ├── App.tsx               ← 🔴 MAJOR CHANGES — layout, sidebar, top nav, drawer
    │   ├── index.css             ← 🔴 MAJOR CHANGES — CSS variables, theming
    │   ├── config.ts             ← apiUrl (no changes needed)
    │   ├── types.ts              ← TypeScript types + LIFECYCLE_PIPELINE
    │   ├── hooks/
    │   │   └── usePipelineState.ts  ← No changes needed
    │   └── components/
    │       ├── KanbanColumn.tsx        ← 🔴 MAJOR CHANGES — column + card full rebuild
    │       ├── AutomationStudio.tsx    ← 🔴 MAJOR CHANGES — 3-column layout rebuild
    │       ├── IntegrationsManager.tsx ← 🔴 MAJOR CHANGES — card grid rebuild
    │       ├── AIEngineSettings.tsx    ← 🔴 MAJOR CHANGES — full page rebuild
    │       ├── ArtifactViewer.tsx      ← 🟢 NO CHANGES — will live inside drawer
    │       ├── CardEditor.tsx          ← 🟢 NO CHANGES — will live inside drawer
    │       ├── WorkflowManager.tsx     ← 🟢 NO CHANGES — full tab content
    │       ├── WorkflowArchitect.tsx   ← 🟡 MINOR — optional props already added
    │       ├── PipelineDashboard.tsx   ← 🟢 NO CHANGES
    │       ├── SkeletonBoard.tsx       ← 🟢 NO CHANGES
    │       ├── ErrorBoundary.tsx       ← 🟢 NO CHANGES
    │       ├── TransactionPanel.tsx    ← 🟢 NO CHANGES
    │       ├── VirtualBoard.tsx        ← 🟢 NO CHANGES
    │       └── modals/
    │           ├── CreateItemModal.tsx     ← 🟢 NO CHANGES
    │           ├── DeleteConfirmModal.tsx  ← 🟢 NO CHANGES
    │           └── ManagementModals.tsx    ← 🟢 NO CHANGES (BuilderModal stays)
```

---

## 8. Current Status

**Last Updated:** 2026-06-06

### Phase 0: Test Suite Cleanup
- [x] Delete phantom `ui/ui/` directory (duplicate that broke module resolution)
- [x] Fix `ArtifactViewer.test.tsx` — OXC parser crash from copy-pasted line-number prefixes
- [x] Fix `App.polling.test.tsx` — pipeline map crash (URL-routing fetch mock)
- [x] Fix `vite.config.ts` — exclude `e2e-tests/` from Vitest
- [x] Fix `WorkflowArchitect.tsx` — add optional `currentPhase`, `initialProposal`, `itemId` props
- [x] Fix `WorkflowArchitect.test.tsx` — add `beforeEach` fetch mock with orchestrator state
- [x] Fix `ManagementModals.test.tsx` — add `beforeEach`/`afterEach` fetch mock
- [ ] Fix `WorkflowArchitect.test.tsx` — goal text assertion mismatch (see Section 5, Bug #2)
- [ ] Fix `ManagementModals.test.tsx` — `TransactionProposal` interface mismatch (see Section 5, Bug #3)
- [ ] Fix `App.polling.test.tsx` — call count off-by-one (see Section 5, Bug #4)


### Phase 1: CSS Design System
- [ ] Rewrite `ui/src/index.css` with CSS variables (light + dark), sidebar dimensions, utility classes

### Phase 2: App Shell — Major Layout Restructure (`ui/src/App.tsx`)
- [ ] Implement left sidebar: logo row, nav items with Lucide icons + labels, user section at bottom
- [ ] Sidebar nav items: Home, Orchestrator, Studio, Workflows, Integrations, AI Engine, Settings

- [ ] Active state: teal pill bg, accent icon + text (no left border)
- [ ] Sidebar width: `180px` expanded, `56px` icon-only collapsed
- [ ] Persist `isSidebarCollapsed` in `localStorage`
- [ ] Implement top navigation bar: current section + other section tabs + [+ New Idea] + avatar
- [ ] Top bar active tab: accent text + underline indicator
- [ ] Theme toggle: dark/light, persist in `localStorage`, apply `data-theme` attribute
- [ ] Wire Workflows tab → render `<WorkflowManager />` (remove "coming soon" placeholder)
- [ ] Wire Integrations tab → render `<IntegrationsManager />` (remove "coming soon" placeholder)
- [ ] Replace centered card modal with slide-in right drawer (520px, animated, backdrop)
- [ ] Add `open-workflow-builder` custom event listener → `setShowBuilder(true)`
- [ ] Fix `handleDragStart` bug: `active.id` → `event.active.id` (see Section 5, Bug #1)

### Phase 3: Lifecycle Orchestrator / Kanban Board (`ui/src/components/KanbanColumn.tsx`)
- [ ] Column header: Lucide icon in a colored rounded box + column name + count + [+] button
- [ ] Column icon/color per stage (see Section 3.4 for exact icon + color mapping)
- [ ] Column body: white bg, `1px solid #e5e7eb` border, `12px` radius, `12px` padding
- [ ] Drop highlight: `2px solid var(--accent)` border + teal bg tint
- [ ] Empty state: outline Lucide icon + stage-specific title + stage-specific subtitle text
- [ ] Card: white bg, `1px solid #e5e7eb` border, `10px` radius, `14px` padding, `0 1px 3px` shadow
- [ ] Card hover: `0 4px 12px` shadow + `translateY(-1px)`
- [ ] Card badges row: tag badge (gray) + priority badge (amber/teal/gray) + confidence badge
- [ ] ACTION REQUIRED badge: amber bg/text, pulsing
- [ ] AGENT WORKING badge: teal bg/text, pulsing
- [ ] ⋮ kebab menu always visible top-right on card
- [ ] Card footer: monospace ID (left) + date (right), space-between, `text-xs text-gray-400`
- [ ] Bottom of each column: `+ Add idea` centered text link

### Phase 4: Automation Studio Rebuild (`ui/src/components/AutomationStudio.tsx`)
- [ ] Add page header: title + subtitle (inside content area)
- [ ] Restructure to 3-column layout: Left (steps) | Center (live sandbox) | Right (path sequence)
- [ ] Left panel: numbered step list (1 Compose, 2 Refine & Confirm, 3 Add to Workflow)
- [ ] Step 1 expanded: AI Model selector dropdown + instruction textarea + char count + action chips + Propose Step button
- [ ] Action chips: `[⊕ Add context]` `[{} Use variable]` `[⊟ Examples]` (ghost pill style)
- [ ] Step 2 (Refine & Confirm): expands when `proposal` is set — shows proposal card with Accept/Reject
- [ ] Center panel: \"Live Sandbox\" header + green `● Live` badge
- [ ] Active Variables table: VARIABLE | TYPE | VALUE columns (TYPE = `typeof value`) + `+ Add variable` link
- [ ] Step Preview: dark code block (YAML, line-numbered) + `Test Step` link bottom-right
- [ ] Right panel: `⚙ Simulation mode` amber badge + numbered timeline steps + `+ Add Step` link
- [ ] Timeline: dark filled circles with numbers + step title + description + vertical connecting line
- [ ] Add AI Model selector state (`selectedModel`) fetching from `/api/ai-engine/config`
- [ ] All existing logic preserved: `handlePropose`, `handleAccept`, `sandboxState`, `currentPath`, `AuthModal`

### Phase 5: Integrations Hub Rebuild (`ui/src/components/IntegrationsManager.tsx`)
- [ ] Add page header: \"Integrations Hub\" title + subtitle + `[Manage Secrets]` + `[+ Add Connection]` buttons
- [ ] Add filter bar: search input + All Types dropdown + All Status dropdown
- [ ] Replace sidebar+detail layout with CSS Grid card layout (`repeat(auto-fill, minmax(240px, 1fr))`)
- [ ] Integration card: brand-colored icon + name + type label + description + status badge + last sync + ⋮ menu
- [ ] Status badges: Connected (green), Error (red), Warning (amber), Disconnected (gray)
- [ ] Card hover: shadow elevation + accent border color
- [ ] ⋮ kebab menu: Edit, Test Connection, Disconnect, Remove
- [ ] \"Add Connection\" CTA card: dashed border + `+` icon + text (last card in grid)
- [ ] Clicking a card opens slide-in right drawer with connection detail + test/edit options
- [ ] Search, Type, Status filters all work independently
- [ ] All existing fetch/API logic preserved: `/api/integrations`, `/api/mcp/tools`, `testConnection()`

### Phase 6: AI Engine Full Rebuild (`ui/src/components/AIEngineSettings.tsx`)
- [ ] Add 2 new sub-tabs: `Connections` and `Logs` (6 total: Overview, Models, Providers, Connections, Settings, Logs)
- [ ] Rebuild stats row: 5 cards (add \"Active Models\"; make \"Default Model\" the 5th card with copy icon)
- [ ] Remove \"Current Default Model\" highlighted banner
- [ ] Remove \"Quick Start\" and \"Connection Status\" cards
- [ ] Build **Provider Health** left panel with status-per-provider table (Healthy=green / Degraded=amber / Error=red)
- [ ] Build **Model Inventory** right panel with search input + All Providers dropdown
- [ ] Model inventory rows: icon + name + [Default] badge + provider + context size + status + ⋮ kebab menu
- [ ] Kebab menu: Set as Default, Test Connection, Set API Key, Remove
- [ ] Provider health derivation: group models by provider, derive aggregate from `testResults`
- [ ] Replace all blue colors with `var(--accent)` teal token system
- [ ] Connections sub-tab: move `connection_settings` form here
- [ ] Logs sub-tab: placeholder \"Coming soon\"

### Phase 7: Verification & Testing
- [ ] `npm run test` — all tests pass (0 failures)
- [ ] Manual: sidebar shows all 7 nav items with Lucide icons
- [ ] Manual: active nav item shows teal pill background
- [ ] Manual: sidebar collapse/expand works, persists on refresh
- [ ] Manual: top nav bar shows section tabs + active underline
- [ ] Manual: theme toggle works (light/dark), persists on refresh
- [ ] **Kanban**: columns show colored icon boxes + stage names + count
- [ ] **Kanban**: empty state shows correct icon + subtitle text per column
- [ ] **Kanban**: card shows badge row (tag, priority, confidence) + ⋮ menu
- [ ] **Kanban**: ACTION REQUIRED badge shows on review-stage cards
- [ ] **Kanban**: drag-and-drop still works
- [ ] **Kanban**: clicking card opens slide-in right drawer (not full-screen modal)
- [ ] **Kanban**: `+ Add idea` link at bottom of columns works
- [ ] **Studio**: 3-column layout renders correctly
- [ ] **Studio**: AI model selector populated from API
- [ ] **Studio**: Propose Step triggers step 2 expansion with proposal card
- [ ] **Studio**: Active Variables table shows TYPE column
- [ ] **Studio**: Current Path Sequence shows numbered timeline
- [ ] **Integrations**: card grid renders 4 per row
- [ ] **Integrations**: search/type/status filters work
- [ ] **Integrations**: card status badges show correct color
- [ ] **Integrations**: clicking card opens slide-in drawer
- [ ] **Integrations**: Add Connection CTA card opens add modal
- [ ] **AI Engine**: 5 stat cards render with correct computed values
- [ ] **AI Engine**: Provider Health panel shows Healthy/Degraded/Error per provider
- [ ] **AI Engine**: Model Inventory shows searchable/filterable list
- [ ] **AI Engine**: [Default] badge on default model row
- [ ] **AI Engine**: status colors (Ready=green, Needs Key=amber)
- [ ] **AI Engine**: ⋮ kebab menu works on model rows


## 9. Session Log

| Date | Summary |
|---|---|
| 2026-06-06 | Session 1: Phase 0 partial. Deleted `ui/ui/` duplicate. Fixed ArtifactViewer.test.tsx, App.polling.test.tsx, vite.config.ts, WorkflowArchitect.tsx/test, ManagementModals.test.tsx. Server restarted: backend :8006 ✅, frontend :5173 ✅. |
| 2026-06-06 | Session 1 continued: Added full screenshot-exact specs for all 4 screens — Integrations Hub (card grid + filters + CTA card), AI Engine (5-stat cards + Provider Health + Model Inventory panels), Lifecycle Orchestrator (column icon boxes + empty states + card badge layout), Automation Studio (3-column layout + numbered step workflow + Live Sandbox). Context file now fully documents the complete redesign scope. |
| 2026-06-06 | Session 1 final pass: Added testing rules (using `start_antikythera.sh` & `stop_antikythera.sh` to restart the server after changes) and instruction to implement views one at a time starting with the landing page. Mockups reviewed and fully documented. |
| 2026-06-06 | Session 1 audit: Full source-code-based UI functionality audit added as Section 10. Every button, modal, tab, API endpoint documented for Kanban, Studio, Workflows, Integrations, and AI Engine. Kanban board screenshots captured to brain dir. Functionality preservation checklist (Section 10.8) added with 29 items that must be verified after redesign. |

## 7. Design Token Reference

| Purpose | Light | Dark |
|---|---|---|
| Page background | `#f4f3ef` | `#161412` |
| Panel / card bg | `#fcfbf8` | `#1e1c18` |
| Sidebar / header bg | `#f1eee8` | `#252220` |
| Border color | `rgba(39,37,29,0.12)` | `rgba(255,255,255,0.09)` |
| Primary text | `#27251d` | `#f0ede6` |
| Secondary text | `#68645d` | `#9e9a93` |
| Accent (teal) | `#0b6b72` | `#14b8c4` |
| Accent hover | `#0a5c62` | `#12a4af` |
| Accent light (tint) | `#d5e7e6` | `rgba(20,184,196,0.15)` |
| Priority: high | bg `#fef3c7` / text `#92400e` | bg `#451a03` / text `#fbbf24` |
| Priority: medium | bg accent-light / text accent | same |
| Priority: low | bg `#f5f5f4` / text `#78716c` | bg `#292524` / text `#a8a29e` |
| Success | `#dcfce7` / `#166534` | `#052e16` / `#4ade80` |
| Error | `#fee2e2` / `#991b1b` | `#450a0a` / `#f87171` |

---

## 10. Current UI Functionality Audit (Pre-Redesign Baseline)

> **Purpose**: Documents every interactive element in the CURRENT UI. The redesign MUST preserve 100% of these behaviors. Audit performed via source code review of all components + screenshots captured at `brain/863c0bba-7ff5-4c1a-b56e-3f7cdf974f8b/`.

---

### 10.1 Global Navigation Bar (`App.tsx`)

**Location**: Top horizontal bar, always visible.

**Tabs (left to right)**:
| Tab Label | Type | What it renders |
|---|---|---|
| Lifecycle Orchestrator | `KANBAN` | 10-column drag-and-drop Kanban board |
| Automation Studio | `STUDIO` | `<AutomationStudio />` component |
| Workflows | `WORKFLOWS` | ⚠️ Currently just renders: `"Workflows section coming soon"` (placeholder text only) |
| Integrations | `INTEGRATIONS` | ⚠️ Currently just renders: `"Integrations section coming soon"` (placeholder text only) |
| AI Engine | `AI_ENGINE` | `<AIEngineSettings />` component |
| [Dynamic Pipeline tabs] | `PIPELINE` | One tab per pipeline fetched from `/api/pipelines`, each shows `<PipelineDashboard />` |

> **Note**: `WorkflowManager` and `IntegrationsManager` components exist and are fully implemented in the codebase, but they are NOT currently wired to their tabs. The tabs show "coming soon" text. The redesign must wire them properly.

**Right-side action buttons** (always visible in nav bar):
- **`+ New Idea`** (teal button) → opens `<CreateItemModal />`
- **`Refresh`** (border button, only visible on Kanban tab) → calls `fetchState()` to reload all items from API

**Other nav elements**:
- Refresh/reload icon button → calls `loadPipelines()` to refresh pipeline tab list
- Active pipeline tab shows green dot if `status === 'ACTIVE'`

**Keyboard shortcut**:
- `Escape` key → closes card detail modal, create modal, workflow modal, delete confirm modal

---

### 10.2 Lifecycle Orchestrator — Kanban Board

**Component**: `KanbanColumn.tsx` + DnD from `@dnd-kit`

**10 Stages (columns)**:
`INTAKE → REFINEMENT → REVIEW_SPEC → ARCHITECTURE → REVIEW_ARCH → TESTING → REVIEW_TEST → APPROVED → EXECUTING → DONE`

**Filters** (top of kanban — from `App.tsx` state):
- `searchQuery` — text search filtering cards by `id` or `title`
- `priorityFilter` — filter by priority: `all / high / medium / low`
- `stageFilter` — filter by stage

**Per-card actions** (via `KanbanColumn.tsx`):
- Click card → opens card detail modal (`ArtifactViewer`)
- `Edit` button on card → opens card in edit mode (`CardEditor`)
- `Delete` button (trash icon) on card → opens `<DeleteConfirmModal />`
- Drag-and-drop between columns via `@dnd-kit`

**Card Detail Modal** (`ArtifactViewer.tsx`) — tabs inside:
| Tab | Content |
|---|---|
| Overview | Title, stage, priority, confidence score, description, tags, metadata |
| Spec.md | Rendered markdown specification document |
| Architecture.md | Rendered markdown architecture document |
| Tests.md | Rendered markdown test plan document |
| Timeline | Execution timeline/audit log (expandable), shows timestamped events |
| Review | Comment textarea + `Submit Review` button → posts to `/api/` |

**Inside card modal — additional buttons**:
- `Edit Details` → switches to `CardEditor` inline view
- `✕` close button (top right) → closes modal

**`CardEditor` (edit mode inside modal)**:
- Fields: Title, Description, Priority dropdown, Confidence Score, Source Type, Source Value, Due Date, Blocked Reason
- Buttons: `Save`, `Delete Item`, `Cancel`

**`CreateItemModal` (via `+ New Idea`)**:
- Fields: Title, Description, Priority, Source Type, Source Value, Tags
- Buttons: `Create`, `Cancel`

**`DeleteConfirmModal`**:
- Shows item ID being deleted
- Buttons: `Confirm Delete`, `Cancel`

---

### 10.3 Automation Studio (`AutomationStudio.tsx`)

**Layout**: 2-column split (Left: Command Center | Right: Live Sandbox)

**Left Panel — Command Center**:
| Element | Behavior |
|---|---|
| `Your Instruction` textarea | Free-text input for automation instruction |
| `Propose Step` button (teal) | Calls `POST /api/automation/propose` with instruction + current sandbox state |
| **AI Proposal card** (appears after propose) | Shows reasoning text + operator_id + adapter_id |
| `Accept & Play` button (on proposal card) | Calls `POST /api/automation/accept` → executes step in sandbox |
| `Reject` button (on proposal card) | Clears proposal, hides the card |
| **Current Path Sequence** panel (bottom of left) | Shows numbered list of accepted steps (operator_id + adapter_id) |

**Right Panel — Live Sandbox State**:
| Element | Behavior |
|---|---|
| `Live Sandbox State` header | Static label |
| `Simulation Mode` amber badge | Static indicator |
| **Active Variables table** | Shows `Variable` | `Value` columns populated after accepting steps |
| Variable values | Support text highlighting — selecting text triggers `handleExtract` → calls `POST /api/skills/brainstorm` |
| **Skill Brainstormer panel** (conditional) | Appears when `isBrainstorming=true` after extraction |
| `Promote to Skill` button (in brainstormer) | Calls `POST /api/skills/save` to save extracted skill |
| `✕` button on brainstormer | Closes brainstormer panel |

**`AuthModal`** (triggered when `Accept & Play` returns `auth_required`):
- Service name in title (e.g., "Authenticate JIRA")
- Password input for Personal Access Token
- Buttons: `Cancel`, `Submit` → calls `POST /api/automation/store-token` then retries step

**API endpoints used**:
- `POST /api/automation/propose`
- `POST /api/automation/accept`
- `POST /api/automation/store-token`
- `POST /api/skills/brainstorm`
- `POST /api/skills/save`

---

### 10.4 Workflows (`WorkflowManager.tsx`)

> ⚠️ **Currently NOT wired** — `App.tsx` renders `"Workflows section coming soon"` text for this tab. The `WorkflowManager` component is fully implemented but unused in navigation.

**When wired, `WorkflowManager` provides**:

**Layout**: 2-column (Left sidebar: Templates list | Right: Template detail)

**Left Sidebar — Templates**:
| Element | Behavior |
|---|---|
| `Templates` header | Static label + `"Automation recipes"` subtitle |
| `+ New` button (teal) | Dispatches `CustomEvent('open-workflow-builder')` to open `BuilderModal` |
| Template list items | Click to select → shows detail in right panel |
| Trash icon on template (hover) | Calls `DELETE /api/workflows/templates/{id}` with confirm dialog |

**Right Panel — Template Detail** (when template selected):
| Element | Behavior |
|---|---|
| Template name heading | Static display |
| Version + trigger type badge | From template data |
| `▶ Run Workflow` button | Calls `POST /api/workflows/trigger` with `{ template_id, inputs: {} }` |
| Steps list | Shows each step with name + adapter info |

**Empty state** (no template selected): Centered icon + "Select a template" message

**`BuilderModal`** (`ManagementModals.tsx`):
- Full workflow builder UI
- Linked to `selectedId` (current card)

**API endpoints used**:
- `GET /api/workflows/templates`
- `DELETE /api/workflows/templates/{id}`
- `POST /api/workflows/trigger`

---

### 10.5 Integrations (`IntegrationsManager.tsx`)

> ⚠️ **Currently NOT wired** — `App.tsx` renders `"Integrations section coming soon"` text. `IntegrationsManager` is fully implemented but unused.

**When wired, `IntegrationsManager` provides**:

**Header area**:
| Button | Behavior |
|---|---|
| `Manage Secrets` | Opens Secret Vault modal |
| `+ Add Connection` | Opens Add Integration modal |

**Integration cards grid** (3-column on large screens):
| Element | Behavior |
|---|---|
| Card (per integration) | Shows: icon (🔌 MCP or 🛠️ native), name, type badge, created date |
| `Edit` link (bottom right of card) | Opens Edit Integration modal |
| `✕` delete button (hover, top right) | Calls `DELETE /api/integrations/{name}` with `window.confirm` |

**Edit Integration Modal**:
| Element | Behavior |
|---|---|
| Config JSON textarea | Editable JSON config |
| `Test Connection` button | Calls `POST /api/integrations/{name}/test` → shows result inline |
| `Show Logs` / `Hide Logs` toggle | Toggles raw logs display |
| `Save Changes` button | Calls `PATCH /api/integrations/{name}` |
| `Cancel` | Closes modal |
| **Available Tools section** (MCP only) | Shows tool list with `▶ Run` button per tool |
| `Refresh Tools` button | Calls `GET /api/integrations/{name}/tools` |
| `▶ Run` on tool | Calls `POST /api/integrations/{name}/call` |

**Add Integration Modal**:
| Element | Behavior |
|---|---|
| Connection Name input | Text field |
| Connector Type select | `Native Adapter` or `MCP Server` |
| Config (JSON) textarea | JSON input |
| `Add Connection` | Calls `POST /api/integrations/` |
| `Cancel` | Closes modal |

**Secret Vault Modal**:
| Element | Behavior |
|---|---|
| Profile ID input | Text field (e.g., "github_prod") |
| Secrets JSON textarea | JSON key-value pairs |
| `Save Secrets` | Calls `POST /api/integrations/secrets` |
| `Cancel` | Closes modal |

**API endpoints used**:
- `GET /api/integrations/`
- `POST /api/integrations/`
- `PATCH /api/integrations/{name}`
- `DELETE /api/integrations/{name}`
- `POST /api/integrations/{name}/test`
- `GET /api/integrations/{name}/tools`
- `POST /api/integrations/{name}/call`
- `POST /api/integrations/secrets`

---

### 10.6 AI Engine (`AIEngineSettings.tsx`)

**Header buttons** (always visible):
| Button | Behavior |
|---|---|
| `Refresh` (with RefreshCw icon) | Calls `GET /api/ai-engine/config` to reload config |
| `Add Model` (blue, Plus icon) | Sets `isAddingModel=true` to show add model form |

**4 Sub-tabs**: `Overview | Models | Providers | Settings`

**Overview Tab**:
| Element | Content |
|---|---|
| Stat cards (4) | Total Models, Default Model (name), Configured Providers (count), API Keys Set (x/total) |
| Current Default Model card (blue) | Model name + provider + context window tokens |
| Quick Start card | Bulleted tips (Ollama: no key needed, Cloud: set API keys, Test before use) |
| Connection Status card | List of providers with count of models per provider |

**Models Tab**:
| Element | Content/Behavior |
|---|---|
| Stat cards (4) | Total Models, Configured Keys, Default Provider, Default Model |
| Model cards grid | One card per model showing: name, provider, context window, temperature, max_tokens |
| `Set as Default` button per model | Calls `POST /api/ai-engine/set-default` |
| `Test Connection` button per model | Calls `POST /api/ai-engine/test-connection` → shows ✅/❌ inline |
| `Set API Key` button per model | Opens API key input modal |
| `Delete` button per model | Calls model delete endpoint |
| Test result indicator | Shows success/failure message inline under model card |

**API Key Modal** (per model):
| Element | Behavior |
|---|---|
| Password input | Enter API key |
| `Save Key` | Calls `POST /api/ai-engine/set-api-key` |
| `Cancel` | Closes modal |

**Providers Tab**: Shows provider catalog (Ollama, NVIDIA NIM, Google Gemma, IBM Bob) with features list

**Settings Tab**: Shows `connection_settings` form:
| Field | Current default |
|---|---|
| Timeout (seconds) | `timeout_seconds` |
| Max Retries | `max_retries` |
| Enable Fallback | toggle |
| Enable Caching | toggle |

**API endpoints used**:
- `GET /api/ai-engine/config`
- `POST /api/ai-engine/test-connection`
- `POST /api/ai-engine/set-default`
- `POST /api/ai-engine/set-api-key`

---

### 10.7 Screenshots Captured (Pre-Redesign Baseline)

| Screenshot File | What it shows |
|---|---|
| `kanban_board_main_1780766055653.png` | Full Kanban board with all columns |
| `card_detail_modal_1780766075405.png` | Card detail modal (Overview tab) |
| `card_detail_modal_expanded_timeline_1780766083944.png` | Card detail with Timeline expanded |
| `lifecycle_orchestrator_main_1780765739977.png` | Kanban board (earlier session) |
| `lifecycle_orchestrator_details_modal_1780765747935.png` | Card detail modal (earlier session) |
| `lifecycle_orchestrator_spec_md_1780765757512.png` | Spec.md tab in card modal |
| `lifecycle_orchestrator_architecture_md_1780765766706.png` | Architecture.md tab in card modal |
| `lifecycle_orchestrator_tests_md_1780765778687.png` | Tests.md tab in card modal |
| `lifecycle_orchestrator_timeline_expanded_1780765789150.png` | Timeline tab expanded |
| `lifecycle_orchestrator_timeline_end_1780765818323.png` | Timeline scrolled to end |
| `lifecycle_orchestrator_review_tab_1780765827416.png` | Review tab (comment form) |
| `review_comments_typed_1780765856503.png` | Review tab with comments typed |
| `review_submitted_modal_closed_1780765868070.png` | After review submit |

> **Note**: Screenshots for Automation Studio, Workflows, Integrations, and AI Engine tabs were not captured due to browser quota limits. Full functionality for those screens is documented above via source code audit.

---

### 10.8 Functionality Preservation Checklist

When the redesign is complete, verify **ALL** of the following still work:

- [ ] All 5 top nav tabs switch correctly (Kanban, Studio, Workflows, Integrations, AI Engine)
- [ ] Dynamic pipeline tabs still appear and work
- [ ] `+ New Idea` modal opens with all fields and submits
- [ ] `Refresh` button on Kanban tab reloads board
- [ ] `Escape` key closes modals
- [ ] Drag-and-drop cards between Kanban columns
- [ ] Card click opens detail modal with all 6 tabs (Overview, Spec.md, Architecture.md, Tests.md, Timeline, Review)
- [ ] `Edit Details` in card modal switches to CardEditor
- [ ] CardEditor saves/deletes correctly
- [ ] Delete card via trash icon opens confirm dialog
- [ ] Automation Studio: `Propose Step` → AI proposal card → `Accept & Play` / `Reject`
- [ ] Automation Studio: Auth modal appears when auth_required response
- [ ] Automation Studio: Active Variables table populates after steps accepted
- [ ] Automation Studio: Text selection triggers brainstormer
- [ ] Workflows: Template list loads from API
- [ ] Workflows: `+ New` opens BuilderModal
- [ ] Workflows: `▶ Run Workflow` triggers workflow
- [ ] Workflows: Delete template with confirm
- [ ] Integrations: Card grid shows all integrations
- [ ] Integrations: `Manage Secrets` opens Secret Vault modal
- [ ] Integrations: `+ Add Connection` opens Add modal with Name/Type/Config fields
- [ ] Integrations: Edit modal: Test Connection, Show Logs, Save Changes
- [ ] Integrations: MCP integrations show Available Tools with `▶ Run`
- [ ] AI Engine: All 4 sub-tabs work (Overview, Models, Providers, Settings)
- [ ] AI Engine: `Test Connection` per model shows inline result
- [ ] AI Engine: `Set as Default` updates default model
- [ ] AI Engine: `Set API Key` modal saves key
- [ ] AI Engine: `Add Model` button triggers add model flow
- [ ] AI Engine: `Refresh` reloads config


