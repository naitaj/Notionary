# Notionary — Complete Screen & Component Sitemap (Stitch Design Specification)

This document serves as the authoritative architectural sitemap, visual hierarchy, and component specification for **Notionary**. It specifies exactly what screens, sections, modals, drawers, and data-bound components exist, where they are placed in the application layout, and how Stitch should scaffold or generate each interface element.

---

## 1. Design System & Global Aesthetic Foundations

```
Primary Palette:
  Background:       slate-950 (#020617) & slate-900 (#0f172a)
  Borders:          slate-800 (#1e293b) & slate-700/60 (#334155)
  Accent / Brand:   indigo-600 (#4f46e5) / indigo-500 (#6366f1) / text-indigo-400
  Evidence Verified:emerald-500 (#10b981) / text-emerald-400 / bg-emerald-950/40
  Warning / Tier 2: amber-500 (#f59e0b) / text-amber-400 / bg-amber-950/40
  Contradiction/Risk:rose-500 (#f43f5e) / text-rose-400 / bg-rose-950/40
  Informational:    sky-500 (#0ea5e9) / text-sky-400 / purple-500 (#a855f7)

Typography:
  Body & Headings:  Geist Sans / Inter (-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto)
  Codes & Metrics:  Geist Mono / JetBrains Mono (monospace)

Global Layout Shell:
  +------------------------------------------------------------------------------------+
  | SIDEBAR (256px fixed)   | TOP HEADER (h-14 sticky, project reasoning layer banner) |
  | - Logo "N" Notionary    +----------------------------------------------------------+
  | - 11 Nav items + badges | MAIN VIEWPORT (flex-1 overflow-y-auto, max-w-6xl)        |
  | - Notion link indicator | - Tab Views 1-11                                         |
  | - Demo Reset Button     | - Slide-over Drawers & Interactive Modals                |
  +------------------------------------------------------------------------------------+
```

---

## 2. High-Level Sitemap Matrix

| Screen / Tab ID | Title & Role | Core Components | Primary API Bindings |
| :--- | :--- | :--- | :--- |
| **`overview`** | **Six-Dimension Health Radar** | Health score cards, 6 dimension radar lights, blocked tasks list, recent decisions | `GET /projects/{id}/health`<br>`GET /tasks/project/{id}/blocked` |
| **`inbox`** | **3-Tier Proposal Review Inbox** | Filter tabs, proposal queue cards, confidence tier badges, grounding excerpt drawer | `GET /proposals`<br>`POST /proposals/{id}/approve` |
| **`coverage`** | **Claim Coverage Sufficiency** | Coverage stat banner, claim taxonomy cards, 5-point sufficiency checklist accordion | `GET /coverage/projects/{id}`<br>`GET /coverage/claims/{id}` |
| **`reports`** | **Weekly Intelligence Reports** | Window selector, LLM toggle, executive digest viewer, risk flags, Notion sync action | `GET /reports/projects/{id}`<br>`POST /reports/projects/{id}/generate` |
| **`decisions`** | **Decision Lineage ("Why?")** | Horizontal decision selector, 3-column upstream/governing/downstream lineage, time travel | `GET /decisions?project_id={id}`<br>`GET /decisions/{id}/lineage` |
| **`tasks`** | **Tasks & Origin Derivation** | Task list/kanban, origin decision chips, blocked reasons, re-evaluation flags | `GET /tasks?project_id={id}`<br>`GET /tasks/{id}/origin` |
| **`radar`** | **Contradiction Radar** | Discrepancy detector cards, lab vs field comparison table, resolution modal | `GET /contradictions?project_id={id}`<br>`POST /contradictions/{id}/resolve` |
| **`impact`** | **What-If Impact Blast Simulator** | Decision target selector, blast radius metric cards, ranked cascade table, apply modal | `POST /impact/analyze`<br>`POST /impact/{id}/apply` |
| **`knowledge`** | **Knowledge & Document Ingestion**| Hybrid search bar (BM25 + Dense), document upload dropzone, chunks inspection drawer | `POST /projects/{id}/documents`<br>`GET /documents/{id}/chunks` |
| **`ask`** | **Ask Notionary (Graph-RAG)** | Natural language query box, prompt pills, provenance bar, cited answer, citation cards | `POST /ai/query`<br>`POST /ai/evaluate` |
| **`sync`** | **Notion Live Sync Center** | Heartbeat indicator, database connection status, sync event log, conflict proposal log | `GET /notion/status`<br>`POST /notion/sync/trigger` |

---

## 3. Detailed Screen & Component Specifications

### Screen 1: Overview & Health Radar (`tab: overview`)
- **Location:** `src/app/page.tsx` $\rightarrow$ View container `activeTab === "overview"`
- **Header:** Title *"Six-Dimension Project Health Radar"*, subtitle, quick-action buttons to *"Claim Coverage"* and *"Weekly Report"*.
- **Components to Add & Render:**
  1. **Health Score Hero Banner:**
     - Overall composite health percentage (`health.health_score`).
     - Summary lights pill cluster: Green count, Amber count, Red count.
  2. **Six Health Dimension Grid (`grid-cols-1 md:grid-cols-2 lg:grid-cols-3`):**
     - **Dimension 1: Execution Health** (due date slippage, blocked items).
     - **Dimension 2: Evidence Coverage** (percentage of claims backed by empirical experiments).
     - **Dimension 3: Documentation Health** (stale flags, missing architecture specs).
     - **Dimension 4: Decision Stability** (superseded decision velocity, churn).
     - **Dimension 5: Dependency Health** (critical path cycle protection, orphan tasks).
     - **Dimension 6: Knowledge Consistency** (active unresolved contradictions).
     - *Each card renders:* Traffic light dot (Green/Amber/Red), threshold rule explanation, metric breakdown pills, and clickable "Drill Down" drawer toggle.
  3. **Rule-Based Blocked Tasks Card:**
     - Surfaces tasks blocked by incomplete dependencies or missing ADRs (`blocked_reason`).
  4. **Recent Decisions Feed:**
     - Displays latest approved decisions (`D-17`, `D-16`) with status tags, rationale snippets, and quick link to lineage view.

---

### Screen 2: 3-Tier Proposal Review Inbox (`tab: inbox`)
- **Location:** `src/app/page.tsx` $\rightarrow$ View container `activeTab === "inbox"`
- **Header:** Title *"Review Inbox (Human-in-the-Loop Gate)"*, bulk approve button, refresh button.
- **Filter Tabs Bar:**
  - `All Proposals`, `Decisions`, `Tasks`, `Experiments`, `Claims` with pill counter badges.
- **Components to Add & Render:**
  1. **Proposal Queue Cards (`space-y-3`):**
     - Confidence Tier Badge:
       - **Tier 1 (High $\ge 0.85$):** Emerald badge *"High Confidence"*.
       - **Tier 2 (Medium $0.60 - 0.84$):** Amber badge *"Needs Attention"*.
       - **Tier 3 (Suspect $< 0.60$):** Rose badge *"Quarantined / Unreviewed"*.
     - Entity code or type badge (`D-17`, `T-14`, `EXP-06`).
     - Extracted title / statement.
     - Quick "Approve" and "Reject" buttons.
  2. **Slide-Over Proposal Detail Drawer (Right panel, 480px width):**
     - Opens when a proposal card is clicked.
     - **Verbatim Grounding Excerpt Box:** Highlighted exact quote from meeting transcript or design spec.
     - **Extracted Attributes Key-Value Grid:** Code, statement, rationale, owner, metric, dataset.
     - **Audit Action Footer:** "Reject" button (prompts for reason) and "Approve to Graph & Notion" button (triggers sync).

---

### Screen 3: Claim Coverage & Epistemic Sufficiency (`tab: coverage`)
- **Location:** `src/app/page.tsx` $\rightarrow$ View container `activeTab === "coverage"`
- **Header:** Title *"Claim Coverage & Sufficiency Engine"*, Coverage Percentage badge (`coverage_percentage%`), Ratio (`covered/total`).
- **Components to Add & Render:**
  1. **Claim Sufficiency Cards (`space-y-4`):**
     - Each card displays Claim ID, claim statement, and taxonomy badge:
       - `well_supported` (Emerald): Fully verified against empirical evidence.
       - `partially_supported` (Amber): Evidence incomplete (missing baseline or variance).
       - `potentially_contradicted` (Rose): Conflicts with another experiment result.
       - `potentially_stale` (Purple): Supporting document superseded.
       - `unsupported` (Slate): Bare assertion without linked experiments.
  2. **5-Dimension Sufficiency Checklist Accordion:**
     - Toggleable dropdown inside each card evaluating:
       1. `comparison_baseline`: Was a comparison baseline logged (e.g. ResNet-50)?
       2. `metric_value`: Explicit quantitative value and unit (e.g. 91.2%).
       3. `dataset_named`: Named dataset and split (e.g. PlantVillage Clean v2).
       4. `sample_size_runs`: Number of test runs recorded (e.g. 5 runs).
       5. `variance_or_statistical_test`: Standard deviation, variance, or p-value.

---

### Screen 4: Weekly Executive Intelligence Reports (`tab: reports`)
- **Location:** `src/app/page.tsx` $\rightarrow$ View container `activeTab === "reports"`
- **Header:** Time window selector (7 / 14 / 30 days), LLM reasoning toggle, "Generate Report" button with spinner.
- **Components to Add & Render:**
  1. **Executive Digest Reader Card:**
     - **Executive Paragraph:** High-level leadership synthesis of progress, blockers, and decisions.
     - **Section 1: Decisions Made & Superseded:** Chronological list of formal choices.
     - **Section 2: Active Contradictions:** Critical scientific and metric conflicts flagged.
     - **Section 3: Blocked & Re-evaluation Tasks:** Stalled deliverables and tasks needing scope review.
     - **Section 4: Milestone Risk Assessment:** Delivery risk analysis for upcoming roadmap deadlines.
  2. **Action Bar:** "Export Markdown", "Push to Notion Page".

---

### Screen 5: Decision Lineage & Provenance ("Why?") (`tab: decisions`)
- **Location:** `src/app/page.tsx` $\rightarrow$ View container `activeTab === "decisions"`
- **Decision Selector Bar:** Horizontal pill list of decisions (`D-17`, `D-16`).
- **Components to Add & Render:**
  1. **Interactive 3-Column Lineage Visualizer (`grid-cols-1 md:grid-cols-3`):**
     - **Column 1: Upstream Evidence:** Supporting experiments (`EXP-06`), benchmark metrics, architectural constraints (`DOC-01`).
     - **Column 2: Governing Decision:** Decision card with statement, rationale, decided by, version history, and "Simulate Change" button.
     - **Column 3: Downstream Work:** Direct tasks (`T-14`, `T-15`) and downstream deliverables (`DL-02`).
  2. **Temporal Time Travel ("As-Of") Control:** Date picker enabling the user to view the graph state at any historical moment.

---

### Screen 6: Tasks & Origin Derivation (`tab: tasks`)
- **Location:** `src/app/page.tsx` $\rightarrow$ View container `activeTab === "tasks"`
- **Components to Add & Render:**
  1. **Task Matrix / Table:**
     - Code (`T-14`), Title, Assignee, Priority, Status (`todo`, `in_progress`, `completed`).
     - **Origin Decision Link:** Chip linking to parent decision (`D-17`). Clicking reveals the exact rationale and meeting that birthed the task.
     - **Risk Status:** Flags for `is_blocked` (with reason popover) and `needs_reevaluation` (due to decision change).

---

### Screen 7: Contradiction Radar (`tab: radar`)
- **Location:** `src/app/page.tsx` $\rightarrow$ View container `activeTab === "radar"`
- **Header:** Radar sweep icon, active contradiction count badge, "Scan Project" button.
- **Components to Add & Render:**
  1. **Contradiction Cards Grid:**
     - Left pane: Claim / Result A (e.g. `EXP-06` 91.2% lab accuracy).
     - Right pane: Claim / Result B (e.g. `EXP-09` 76.4% sunlight field trial).
     - Discrepancy Explanation Banner: Highlighting conflicting conditions or metric values.
     - Status badge (`open`, `investigating`, `resolved`).
  2. **Resolution Action Modal:** Allows the team to resolve the conflict (e.g., mark lab claim superseded by field trial or schedule re-test).

---

### Screen 8: What-If Impact Blast Simulator (`tab: impact`)
- **Location:** `src/app/page.tsx` $\rightarrow$ View container `activeTab === "impact"`
- **Header:** Title *"What-If Impact Analysis & Invalidation Propagation"*, target decision picker.
- **Simulation Controls:**
  - Scenario Selector: `what_if` (modification), `revoke` (cancellation), `supersede`.
  - Proposed Change Input: Textarea describing the change (e.g. *"Switch to MobileNetV4 due to sunlight degradation"*).
  - "Simulate Blast Radius" action button.
- **Components to Add & Render:**
  1. **Blast Radius Metric Cards (`grid-cols-3`):**
     - Total Affected Items count.
     - 1st-Hop Direct Work (immediate tasks).
     - 2nd-Hop Cascading Risk (deliverables and downstream milestones).
  2. **Ranked Impact Cascade Table:**
     - Selection checkboxes for batch application.
     - Code, Title, Hop Distance, Relationship Class badge (`task_affected`, `deliverable_risk`, `stale_doc`).
     - Path Description (e.g. `D-17 ──resulted_in──> T-14 ──contributes_to──> DL-02`).
     - Suggested Action.
  3. **Apply Invalidation Action Bar:**
     - "Flag Selected Tasks for Re-evaluation" checkbox.
     - "Create Re-evaluation Action Items" toggle (`create_reevaluation_tasks`).
     - "Apply Impact Changes" button (executes atomic cascade).

---

### Screen 9: Knowledge & Document Ingestion (`tab: knowledge`)
- **Location:** `src/app/page.tsx` $\rightarrow$ View container `activeTab === "knowledge"`
- **Components to Add & Render:**
  1. **Hybrid Search Bar:**
     - Search input querying SQLite BM25 + dense semantic embeddings.
     - Real-time result cards showing matched chunk text, match type (`bm25`, `dense`, `hybrid`), match score %, and character offsets.
  2. **Ingest Document Card:**
     - File drag-and-drop zone (`.pdf`, `.md`, `.txt`, `.docx`).
     - Title input and document category selector (`design_doc`, `meeting_note`, `experiment_log`, `paper`).
     - Upload & parse button with SHA-256 validation spinner.
  3. **Document Registry Table:**
     - Title, Category, File Hash, Pipeline Status (`completed`, `processing`), Ingestion Date.
     - "View Chunks" button opening the chunk inspection drawer.

---

### Screen 10: Ask Notionary (Graph-RAG Q&A) (`tab: ask`)
- **Location:** `src/app/page.tsx` $\rightarrow$ View container `activeTab === "ask"`
- **Components to Add & Render:**
  1. **Suggested Question Pills:** Quick one-click prompt pills for demo flow.
  2. **Query Input Box:** Input field with keyboard shortcuts and synthesize button.
  3. **Contradiction Alert Callout:** Automatically surfaces if the query touches topics with open contradictions.
  4. **Evidence-Backed Answer Card:**
     - **Provenance Bar:** Proportional breakdown of knowledge source (`X% Human Authored`, `Y% System Derived`, `Z% AI Inferred`).
     - Synthesized response text.
     - Refusal card fallback when evidence is insufficient (with strict zero-hallucination explanation).
  5. **Verifiable Citation Cards Grid:**
     - Each citation displays source document title, chunk heading path, character offset, and excerpt text.
     - Clicking highlights the source document in the knowledge view.

---

### Screen 11: Notion Bi-Directional Sync Center (`tab: sync`)
- **Location:** `src/app/page.tsx` $\rightarrow$ View container `activeTab === "sync"`
- **Components to Add & Render:**
  1. **Live Connection Heartbeat Card:**
     - Notion live status dot (`Connected`, `Polling 30s`), last sync timestamp, workspace parent ID.
  2. **Database Mapping Matrix:**
     - Cards showing mapped Notion databases: Decisions DB, Tasks DB, Experiments DB, Reports DB.
  3. **Sync Queue & Event Stream:**
     - Real-time log of push jobs and remote updates.
     - Conflict resolution status drawer for concurrent edits.

---

## 4. Global Modals & Persistent Controls

1. **Top Header Bar (`sticky top-0 z-10`):**
   - **Tag:** `PROJECT REASONING LAYER` • `KBC-NOTION-02 Reference Scenario`.
   - **"Reset Demo" Button:** Triggers `POST /api/v1/seed/reset-demo` with confirmation modal and animated status indicator.
   - **Traceability Badge:** `Evidence Traceable` indicator.
2. **Left Sidebar (`w-64 fixed`):**
   - Logo and workspace title.
   - 11 Navigation buttons with real-time dynamic count badges (unreviewed proposals, blocked tasks, contradictions, report count).
   - Bottom status panel displaying Notion sync status.
3. **Reset Confirmation Modal:**
   - Warns user that M-04 and EXP-09 will be cleared to restart the clean demo narrative.

---

## 5. Stitch Code Generation & Assembly Guidelines

When Stitch creates or refactors components based on this sitemap:
1. **Component Placement:** All primary tab screens should reside or be imported into [`src/app/page.tsx`](file:///d:/Notionary/frontend/src/app/page.tsx). Reusable sub-components should be placed in `src/components/` (e.g. `src/components/lineage/`, `src/components/radar/`, `src/components/inbox/`).
2. **Design Tokens:** Always use Tailwind classes conforming to the dark slate aesthetic (`bg-slate-950`, `bg-slate-900/80`, `border-slate-800`, `text-slate-100`, `text-indigo-400`, `text-emerald-400`, `text-amber-400`, `text-rose-400`).
3. **Defensive Parsing:** Always use optional chaining on array access (`coverageData?.claims?.map(...)` and `impactData?.affected_items?.map(...)`) to prevent client hydration exceptions.
4. **Backend Base URL:** Standardize backend API calls to `http://localhost:8000/api/v1/`.
