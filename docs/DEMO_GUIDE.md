# Notionary Presenter Guide & Demo Runbook

## 1. Demo Overview & Strategy

This guide provides the complete, scene-by-scene presenter script for the **Notionary** live demonstration.
The demo walks through the realistic lifecycle of an edge AI engineering project (**LeafGuard**), showing how Notionary acts as an active **reasoning layer** over unstructured team discussions and Notion databases.

- **Total Duration:** 10 – 12 minutes.
- **Reference Scenario:** KBC-NOTION-02 (LeafGuard Edge Disease Detector).
- **Core Narrative:** From unstructured meeting transcript $\rightarrow$ structured graph $\rightarrow$ bidirectional Notion sync $\rightarrow$ instant "Why?" provenance $\rightarrow$ proactive contradiction detection $\rightarrow$ what-if impact blast simulation $\rightarrow$ automated executive reporting.

---

## 2. Pre-Flight Checklist (T-minus 5 Minutes)

1. **Start Backend Server:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
2. **Start Frontend Server:**
   ```bash
   cd frontend && npm run dev
   ```
3. **Verify Environment:**
   - Open browser to `http://localhost:3000`.
   - In the top header bar, click **"Reset Demo"** and confirm.
   - Verify that the toast appears: `Demo state reset to canonical baseline!`.
   - This sets the workspace to the clean pre-meeting state (M-04 transcript not yet ingested, EXP-09 not yet registered).

---

## 3. Scene-by-Scene Presenter Script

### SCENE 1: Ingest Meeting M-04 Transcript
- **Duration:** 1:30
- **UI Location:** Sidebar $\rightarrow$ **"Knowledge & Docs"** tab.
- **Action:**
  1. Show the uploaded design specification `DOC-01: LeafGuard System Architecture Spec`. Point out the strict hardware constraints: $\le 20\text{ MB}$ model budget, $\le 20\text{ ms}$ latency ceiling.
  2. Upload or select the meeting transcript `M-04-Architecture-Sync.txt`.
  3. Highlight that the background indexing worker parses headings, computes character offsets, and runs SHA-256 deduplication.
- **Presenter Talk Track:**
  > *"Every engineering team produces dozens of meeting transcripts and chat logs that disappear into the void. Here, we upload our Architecture Sync #4. In this meeting, the team discusses experimental results and decides to switch to MobileNetV3. Instead of treating this as dumb text, Notionary immediately triggers its extraction pipeline."*

---

### SCENE 2: Proposal Inbox & 3-Tier Confidence Routing
- **Duration:** 1:30
- **UI Location:** Sidebar $\rightarrow$ **"Review Inbox"** tab.
- **Action:**
  1. Show the pending proposal for **Decision D-17**: *"Adopt MobileNetV3-Small as the edge inference architecture"*.
  2. Click on the proposal to view the side drawer. Point out the extracted statement, the rationale, and the **highlighted source text excerpt** from M-04.
  3. Point out the **Confidence Badge** (High Confidence, Tier 1) and click **"Approve"**.
- **Presenter Talk Track:**
  > *"To ensure human governance and zero hallucination risk, Notionary never blindly writes to production. Extracted items enter the Review Inbox categorized by a 3-tier confidence gateway. As the project lead, I can see the exact excerpt from the meeting transcript that justified this proposal. With one click, I approve D-17, promoting it into the canonical evidence graph."*

---

### SCENE 3: Notion Database Relations & Bidirectional Sync
- **Duration:** 1:15
- **UI Location:** Sidebar $\rightarrow$ **"Notion Sync"** tab.
- **Action:**
  1. Show the live sync status indicator: `Synced (polling 30s)`.
  2. Demonstrate how approving D-17 in Notionary automatically enqueues a sync job that creates or updates the corresponding Notion page.
  3. Emphasize that relations (e.g. D-17 pointing to Experiment EXP-06 and downstream Tasks T-14 and T-15) are preserved as relational Notion database properties.
- **Presenter Talk Track:**
  > *"Notionary doesn't replace Notion; it supercharges it. The moment D-17 was approved, an asynchronous sync job mapped it directly into our team's Notion Decisions database, establishing bidirectional links with our Tasks and Experiments databases. If an engineer updates a task in Notion, Notionary detects the content hash change and mirrors it locally without conflict."*

---

### SCENE 4: Interactive Evidence Graph & Lineage Traversal
- **Duration:** 1:30
- **UI Location:** Sidebar $\rightarrow$ **"Decisions & 'Why?'"** tab.
- **Action:**
  1. Select **D-17** from the decisions list.
  2. Inspect the **Lineage View**:
     - **Upstream Evidence:** Points to `EXP-06` (MobileNetV3 benchmark showing 91.2% accuracy) and `DOC-01` constraints.
     - **Downstream Consequences:** Points to `T-14` (INT8 Quantization) and `T-15` (Shadow Data Collection).
     - **Alternatives Considered:** ResNet-50 (rejected for exceeding storage limit).
- **Presenter Talk Track:**
  > *"When a new engineer joins the team 6 months from now and asks: 'Why did we pick MobileNetV3 instead of ResNet-50?', they don't have to excavate Slack channels. Notionary renders the complete provenance graph in sub-millisecond time. We can trace all upstream supporting experiments and every downstream task that resulted from this decision."*

---

### SCENE 5: Natural Language "Why?" Query (Graph-RAG)
- **Duration:** 1:30
- **UI Location:** Sidebar $\rightarrow$ **"Ask Notionary"** tab.
- **Action:**
  1. In the query box, enter: `Why did we choose MobileNetV3?` and submit.
  2. Observe the answer stream: it explains that MobileNetV3 clocked 14.2ms at 91.2% accuracy, staying within the 20ms constraint.
  3. Click on the inline citations: note how clicking a citation highlights the exact chunk in `DOC-01` and `EXP-06`.
- **Presenter Talk Track:**
  > *"Notice what just happened. Notionary didn't just perform a keyword search. Its Graph-RAG pipeline performed reciprocal rank fusion over dense vector embeddings and BM25 full-text chunks, expanded the graph 2 hops to pull structured experiment metrics, and synthesized an answer where every claim is tied to an auditable, verifiable citation."*

---

### SCENE 5b: Claim Coverage Checklist & Missing Evidence
- **Duration:** 1:00
- **UI Location:** Sidebar $\rightarrow$ **"Claim Coverage"** tab.
- **Action:**
  1. View the claims sufficiency matrix.
  2. Point out claims marked as `Well-Supported` vs `Incompletely Supported` (missing baseline comparison or variance metrics).
- **Presenter Talk Track:**
  > *"Scientific and technical engineering requires rigorous proof. Notionary continuously grades every technical claim against an epistemic checklist: Does it have an empirical result? Was a baseline comparison specified? What was the variance over multiple runs? It flags unsubstantiated assertions before they reach production."*

---

### SCENE 6: Contradiction Radar (Field vs Lab Accuracy)
- **Duration:** 1:30
- **UI Location:** Sidebar $\rightarrow$ **"Contradiction Radar"** tab.
- **Action:**
  1. Point out the active contradiction surfaced on the radar:
     - **Claim A (EXP-06):** MobileNetV3 achieves 91.2% accuracy under benchmark conditions.
     - **Claim B (EXP-09):** Field camera accuracy drops to 76.4% under harsh direct sunlight.
  2. Emphasize that the radar automatically detected that both claims evaluate the same model (`MobileNetV3-Small`) on accuracy, but yield divergent results.
- **Presenter Talk Track:**
  > *"Here is Notionary's proactive superpower: the Contradiction Radar. In the lab, MobileNetV3 looked flawless at 91.2%. But once field trial EXP-09 came in showing a steep degradation to 76.4% under direct sunlight, Notionary immediately flagged the conflict. This surfaces hidden technical debt before shipping broken models to farmers."*

---

### SCENE 7: What-If Impact Blast Simulator & Invalidation
- **Duration:** 1:45
- **UI Location:** Sidebar $\rightarrow$ **"Impact Analysis"** tab.
- **Action:**
  1. Select **D-17** as the target decision.
  2. Select scenario: **"What-If Modification"** with proposed change: *"Switch to MobileNetV4 due to sunlight degradation"*.
  3. Click **"Simulate Blast Radius"**.
  4. Show the visual impact tree:
     - `T-14` (INT8 Quantization): Flagged for re-evaluation.
     - `T-15` (Shadow Data): Flagged for re-evaluation.
     - `DL-02` (Android Demo APK): Flagged as high-risk deliverable.
  5. Click **"Apply Impact & Flag Tasks"**. Notice that tasks are atomically flagged `needs_reevaluation = true`.
- **Presenter Talk Track:**
  > *"When a core decision changes, what happens to the work in flight? Usually, teams spend days in panic meetings trying to figure out what broke. In Notionary, we run a What-If Impact Simulation. The graph computes the exact blast radius: Task T-14 is working on the old model, T-15 needs realignment, and our Android demo deliverable is at risk. With one click, Notionary flags these tasks in Notion and creates re-evaluation tickets for the assignees."*

---

### SCENE 8: Weekly Executive Intelligence Report
- **Duration:** 1:15
- **UI Location:** Sidebar $\rightarrow$ **"Weekly Reports"** tab.
- **Action:**
  1. Click **"Generate Report"** (7-day window).
  2. Walk through the generated executive digest:
     - **Executive Paragraph:** High-level summary of decisions and risks.
     - **Decisions Made & Superseded:** D-17 timeline.
     - **Active Contradictions:** Lab vs field sunlight degradation alert.
     - **Blocked & Re-evaluation Tasks:** T-14 and T-15 flagged.
     - **Milestone Risk Assessment:** Field Pilot release risk flags.
- **Presenter Talk Track:**
  > *"Finally, for leadership, Notionary synthesizes a weekly intelligence report straight from the ground truth of the graph. It isn't a fluffy text summary; it is a deterministic audit of decisions made, active contradictions discovered, blocked tasks, and roadmap risks, formatted and ready to sync to Notion."*

---

## 4. Emergency Fallback & Resilience Procedures

| Scenario | System Behavior | Presenter Action |
| :--- | :--- | :--- |
| **External LLM API Down / Throttled** | `ResilientLLMProvider` automatically falls back to deterministic in-memory mock responses. | Continue presentation normally. Answers and extraction will remain 100% coherent. |
| **Network Timeout (> 15s)** | Async timeout guard halts waiting and returns pre-computed golden response. | No intervention required; UI will render cached golden answer. |
| **Need to Restart Flow Mid-Demo** | Clicking **"Reset Demo"** in header resets all database tables to pre-meeting state in $< 100\text{ ms}$. | Click **"Reset Demo"**, wait for green confirmation badge, and proceed with Scene 1. |
| **Terminal CLI Rehearsal Demo** | Want to demonstrate headless automated verification to technical judges. | Run `python scripts/demo_rehearsal.py --runs 1` in terminal. Shows colored step-by-step verification and latency scorecard. |
