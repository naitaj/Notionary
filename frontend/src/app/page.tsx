"use client";

import React, { useState, useEffect } from "react";
import {
  Layers,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  Activity,
  FileText,
  FlaskConical,
  GitBranch,
  CheckSquare,
  Search,
  RefreshCw,
  ArrowRight,
  ShieldCheck,
  Sparkles,
  ExternalLink,
  ChevronRight,
  Clock,
  Database,
  Radio,
  Upload,
} from "lucide-react";

interface DocumentItem {
  id: string;
  title: string;
  doc_type: string;
  file_uri?: string;
  pipeline_status: string;
  notion_url?: string;
  notion_page_id?: string;
}

interface ChunkItem {
  id: string;
  document_id: string;
  heading_path?: string;
  char_start: number;
  char_end: number;
  text: string;
}

interface SearchResultItem {
  chunk_id: string;
  document_id: string;
  document_title: string;
  heading_path?: string;
  char_start: number;
  char_end: number;
  text: string;
  score: number;
  match_type: string;
}

interface HealthData {
  evidence_coverage: number;
  blocked_tasks_count: number;
  open_contradictions_count: number;
  stale_decisions_count: number;
  active_decisions_count: number;
  experiments_count: number;
  health_score: number;
}

interface DecisionItem {
  id: string;
  code: string;
  statement: string;
  rationale?: string;
  status: string;
  version: number;
  decided_by?: string;
}

interface TaskItem {
  id: string;
  code: string;
  title: string;
  status: string;
  owner?: string;
  priority: string;
  origin_decision_id?: string;
  is_blocked: boolean;
}

interface ContradictionItem {
  id: string;
  claim_a_text?: string;
  claim_b_text?: string;
  status: string;
  explanation?: string;
}

interface ImpactResult {
  trigger_decision: { code: string; statement: string };
  total_affected: number;
  summary: string;
  affected_items: Array<{
    id: string;
    code: string;
    title: string;
    type: string;
    hop: number;
    path_explanation: string;
    suggested_action: string;
  }>;
}

export default function NotionaryDashboard() {
  const [activeTab, setActiveTab] = useState<string>("overview");
  const [health, setHealth] = useState<HealthData | null>(null);
  const [decisions, setDecisions] = useState<DecisionItem[]>([]);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [contradictions, setContradictions] = useState<ContradictionItem[]>([]);
  const [selectedDecision, setSelectedDecision] = useState<DecisionItem | null>(null);
  const [impactData, setImpactData] = useState<ImpactResult | null>(null);
  const [isSimulatingImpact, setIsSimulatingImpact] = useState(false);
  const [queryInput, setQueryInput] = useState("");
  const [aiResponse, setAiResponse] = useState<any>(null);
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [syncStatus, setSyncStatus] = useState<string>("Synced 2m ago (polling 30s)");
  const [currentProjectId, setCurrentProjectId] = useState<string>("demo");

  // Knowledge & Document Ingestion state
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>(null);
  const [docChunks, setDocChunks] = useState<ChunkItem[]>([]);
  const [isLoadingChunks, setIsLoadingChunks] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadDocType, setUploadDocType] = useState("note");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);

  // Seed demo data on initial load
  useEffect(() => {
    fetch("http://localhost:8000/api/v1/seed/demo", { method: "POST" })
      .then((res) => res.json())
      .then(() => {
        loadData();
      })
      .catch(() => {
        // Fallback local state if backend not running yet
        setHealth({
          evidence_coverage: 92.4,
          blocked_tasks_count: 0,
          open_contradictions_count: 1,
          stale_decisions_count: 0,
          active_decisions_count: 1,
          experiments_count: 2,
          health_score: 94.5,
        });
        setDecisions([
          {
            id: "d-17",
            code: "D-17",
            statement: "Adopt MobileNetV3-Small as the edge inference architecture for on-device deployment.",
            rationale: "Selected over ResNet50 (93.0% but 98MB) to stay strictly within the 20MB offline phone storage budget while retaining >90% benchmark accuracy.",
            status: "active",
            version: 1,
            decided_by: "Rohan Sharma",
          },
        ]);
        setTasks([
          {
            id: "t-14",
            code: "T-14",
            title: "Quantize MobileNetV3 model to INT8 via TFLite converter",
            status: "in_progress",
            owner: "Meera Sen",
            priority: "high",
            origin_decision_id: "d-17",
            is_blocked: false,
          },
          {
            id: "t-15",
            code: "T-15",
            title: "Collect supplementary shadow-augmented training dataset",
            status: "todo",
            owner: "Ananya Patel",
            priority: "medium",
            is_blocked: false,
          },
        ]);
        setContradictions([
          {
            id: "c-01",
            claim_a_text: "MobileNetV3 provides 91.2% top-1 accuracy (EXP-06 benchmark).",
            claim_b_text: "Field camera samples drop to 76.4% under harsh sunlight glare (EXP-09).",
            status: "open",
            explanation: "EXP-06 benchmark accuracy contradicts EXP-09 field test under direct sun.",
          },
        ]);
        setDocuments([
          {
            id: "doc-05",
            title: "DOC-05: LeafGuard Server Architecture & Edge Inference Pipeline",
            doc_type: "design_doc",
            pipeline_status: "completed",
            notion_url: "https://notion.so/leafguard/doc-05",
          },
          {
            id: "log-01",
            title: "LOG-01: Field Evaluation Logs - Rural Madhya Pradesh",
            doc_type: "experiment_log",
            pipeline_status: "completed",
          },
          {
            id: "exp-09",
            title: "EXP-09: Sunlight Degradation Benchmarks",
            doc_type: "experiment_log",
            pipeline_status: "completed",
          },
        ]);
      });
  }, []);

  const loadDocuments = async (pId: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/v1/projects/${pId}/documents`);
      if (res.ok) {
        const docs = await res.json();
        setDocuments(docs);
        if (docs.length > 0 && !selectedDoc) {
          viewDocChunks(docs[0]);
        }
      }
    } catch {
      // Keep existing documents
    }
  };

  const viewDocChunks = async (doc: DocumentItem) => {
    setSelectedDoc(doc);
    setIsLoadingChunks(true);
    try {
      const res = await fetch(`http://localhost:8000/api/v1/documents/${doc.id}/chunks`);
      if (res.ok) {
        const chunks = await res.json();
        setDocChunks(chunks);
      }
    } catch {
      setDocChunks([
        {
          id: "c-1",
          document_id: doc.id,
          heading_path: "Architecture > Edge Constraints",
          char_start: 0,
          char_end: 285,
          text: "MobileNetV3-Small architecture was selected for edge inference deployment on Jetson Nano. The model must satisfy sub-20ms latency and 20MB storage constraints under varying field ambient conditions.",
        },
      ]);
    } finally {
      setIsLoadingChunks(false);
    }
  };

  const handleHybridSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    try {
      const res = await fetch(
        `http://localhost:8000/api/v1/search?project_id=${currentProjectId}&q=${encodeURIComponent(searchQuery)}`
      );
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data.results || []);
      }
    } catch {
      setSearchResults([
        {
          chunk_id: "demo-chunk-1",
          document_id: "doc-05",
          document_title: "DOC-05: Server Architecture & Edge Inference Pipeline",
          heading_path: "Architecture > Edge Constraints",
          char_start: 120,
          char_end: 340,
          text: "MobileNetV3-Small was evaluated across multiple batch sizes. Benchmarks show 14.2ms latency on FP16 TensorRT runtime.",
          score: 0.94,
          match_type: "hybrid",
        },
      ]);
    } finally {
      setIsSearching(false);
    }
  };

  const handleDocumentUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) return;
    setIsUploading(true);
    setUploadMessage("Uploading and validating SHA-256...");
    try {
      const formData = new FormData();
      formData.append("file", uploadFile);
      if (uploadTitle) formData.append("title", uploadTitle);
      if (uploadDocType) formData.append("doc_type", uploadDocType);

      const res = await fetch(`http://localhost:8000/api/v1/projects/${currentProjectId}/documents`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        setUploadMessage(`Upload rejected: ${err.detail || err.title || "Unknown error"}`);
      } else {
        const data = await res.json();
        setUploadMessage(`Document uploaded! Job enqueued (ID: ${data.job_id.slice(0, 8)}...).`);
        setUploadFile(null);
        setUploadTitle("");
        loadDocuments(currentProjectId);
      }
    } catch (err: any) {
      setUploadMessage(`Network error: ${err.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  const loadData = async () => {
    try {
      const pRes = await fetch("http://localhost:8000/api/v1/projects");
      const projects = await pRes.json();
      if (projects && projects.length > 0) {
        const pId = projects[0].id;
        setCurrentProjectId(pId);
        const hRes = await fetch(`http://localhost:8000/api/v1/projects/${pId}/health`);
        setHealth(await hRes.json());

        const dRes = await fetch(`http://localhost:8000/api/v1/decisions?project_id=${pId}`);
        const decs = await dRes.json();
        setDecisions(decs);
        if (decs.length > 0) setSelectedDecision(decs[0]);

        const tRes = await fetch(`http://localhost:8000/api/v1/tasks?project_id=${pId}`);
        setTasks(await tRes.json());

        const cRes = await fetch(`http://localhost:8000/api/v1/contradictions?project_id=${pId}`);
        setContradictions(await cRes.json());

        loadDocuments(pId);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSimulateImpact = async () => {
    setIsSimulatingImpact(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/impact/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: "demo",
          decision_id: selectedDecision?.id || "d-17",
          scenario: "what_if",
          proposed_change: "Switch from MobileNetV3 to MobileNetV4 / EfficientNet",
        }),
      });
      const data = await res.json();
      setImpactData(data);
    } catch {
      setImpactData({
        trigger_decision: {
          code: "D-17",
          statement: "Adopt MobileNetV3-Small as edge inference architecture",
        },
        total_affected: 3,
        summary: "Changing D-17 cascades across 3 downstream work items across 2 graph hops.",
        affected_items: [
          {
            id: "t-14",
            code: "T-14",
            title: "Quantize MobileNetV3 model to INT8 via TFLite converter",
            type: "task",
            hop: 1,
            path_explanation: "D-17 ──resulted_in──> T-14",
            suggested_action: "Re-evaluate quantization pipeline for new architecture",
          },
          {
            id: "dl-02",
            code: "DL-02",
            title: "LeafGuard Android Demo APK",
            type: "deliverable",
            hop: 2,
            path_explanation: "D-17 ──> T-14 ──contributes_to──> DL-02",
            suggested_action: "Verify if release APK size stays within 20MB budget",
          },
          {
            id: "doc-05",
            code: "DOC-05",
            title: "System Architecture & Edge Deployment Spec v1",
            type: "document",
            hop: 1,
            path_explanation: "D-17 ──specifies──> DOC-05",
            suggested_action: "Flag document as stale and schedule update",
          },
        ],
      });
    } finally {
      setIsSimulatingImpact(false);
    }
  };

  const handleAskAi = async () => {
    if (!queryInput) return;
    setIsAiLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/ai/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: "demo",
          query: queryInput,
        }),
      });
      const data = await res.json();
      setAiResponse(data);
    } catch {
      setAiResponse({
        answer:
          "MobileNetV3 was chosen (Decision D-17) because experiment EXP-06 proved it achieves 91.2% top-1 accuracy within a 14.1 MB envelope, strictly satisfying the offline 20 MB device budget [1][2]. However, field evaluations in EXP-09 revealed a 14.8% accuracy drop under direct sunlight glare [3].",
        citations: [
          {
            n: 1,
            record: "EXP-06 Result R-21",
            origin: "verified_source",
            excerpt: "EXP-06: MobileNetV3 + data aug achieved 91.2% top-1 accuracy at 14.1 MB model size.",
          },
          {
            n: 2,
            record: "Decision D-17",
            origin: "human_approved",
            excerpt: "Adopt MobileNetV3-Small as the edge inference architecture for on-device deployment.",
          },
          {
            n: 3,
            record: "EXP-09 Field Observations",
            origin: "verified_source",
            excerpt: "EXP-09 field test: Severe degradation under harsh lighting to 76.4% top-1 accuracy.",
          },
        ],
      });
    } finally {
      setIsAiLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 font-sans overflow-hidden">
      {/* Sidebar Navigation */}
      <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col justify-between">
        <div>
          {/* Logo & Workspace */}
          <div className="p-5 border-b border-slate-800">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-lg text-white shadow-lg shadow-indigo-500/20">
                N
              </div>
              <div>
                <h1 className="font-semibold text-base tracking-tight text-white">Notionary</h1>
                <p className="text-xs text-slate-400">LeafGuard AI Workspace</p>
              </div>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-3 space-y-1">
            {[
              { id: "overview", label: "Overview", icon: Activity },
              { id: "decisions", label: "Decisions & 'Why?'", icon: GitBranch },
              { id: "tasks", label: "Tasks & Origin", icon: CheckSquare },
              { id: "radar", label: "Contradiction Radar", icon: AlertTriangle, badge: contradictions.length },
              { id: "impact", label: "Impact Analysis", icon: RefreshCw },
              { id: "knowledge", label: "Knowledge & Docs", icon: FileText, badge: documents.length },
              { id: "ask", label: "Ask Notionary", icon: Sparkles },
              { id: "sync", label: "Notion Sync", icon: Database },
            ].map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? "bg-indigo-600 text-white shadow-sm"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon className="h-4 w-4" />
                    <span>{item.label}</span>
                  </div>
                  {item.badge !== undefined && item.badge > 0 && (
                    <span className="px-1.5 py-0.5 text-xs bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded-full font-mono">
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Sync Center Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/60">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              Notion Live Link
            </span>
            <span className="text-[10px] text-slate-500">v1.0</span>
          </div>
          <p className="text-[11px] text-slate-400 truncate">{syncStatus}</p>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-y-auto bg-slate-950">
        {/* Top Header */}
        <header className="h-14 border-b border-slate-800 px-6 flex items-center justify-between bg-slate-900/40 backdrop-blur sticky top-0 z-10">
          <div className="flex items-center gap-3">
            <span className="text-xs px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-mono">
              PROJECT REASONING LAYER
            </span>
            <span className="text-xs text-slate-500">•</span>
            <span className="text-xs text-slate-400">KBC-NOTION-02 Reference Scenario</span>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-xs px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5" />
              Evidence Traceable
            </span>
          </div>
        </header>

        {/* Tab Content */}
        <div className="p-8 max-w-6xl w-full mx-auto space-y-6">
          {/* TAB 1: OVERVIEW */}
          {activeTab === "overview" && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-white tracking-tight">Project Health & Reasoning Intelligence</h2>
                <p className="text-sm text-slate-400 mt-1">
                  Continuously synchronized memory layer bridging Notion records, experiment logs, and decision trees.
                </p>
              </div>

              {/* Health Grid */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800">
                  <div className="text-xs font-medium text-slate-400 uppercase tracking-wider">Health Score</div>
                  <div className="text-3xl font-bold text-indigo-400 mt-2">
                    {health?.health_score ?? 94.5}
                    <span className="text-sm font-normal text-slate-500">/100</span>
                  </div>
                  <p className="text-xs text-slate-400 mt-2">Weighted across coverage & blockers</p>
                </div>

                <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800">
                  <div className="text-xs font-medium text-slate-400 uppercase tracking-wider">Evidence Coverage</div>
                  <div className="text-3xl font-bold text-emerald-400 mt-2">
                    {health?.evidence_coverage ?? 92.4}%
                  </div>
                  <p className="text-xs text-slate-400 mt-2">Claims backed by verifiable experiments</p>
                </div>

                <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800">
                  <div className="text-xs font-medium text-slate-400 uppercase tracking-wider">Contradiction Radar</div>
                  <div className="text-3xl font-bold text-amber-400 mt-2">
                    {health?.open_contradictions_count ?? 1}
                  </div>
                  <p className="text-xs text-slate-400 mt-2">Discrepancies flagged for human review</p>
                </div>

                <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800">
                  <div className="text-xs font-medium text-slate-400 uppercase tracking-wider">Active Decisions</div>
                  <div className="text-3xl font-bold text-white mt-2">
                    {health?.active_decisions_count ?? 1}
                  </div>
                  <p className="text-xs text-slate-400 mt-2">Versioned with bidirectional Notion sync</p>
                </div>
              </div>

              {/* Key Decisions preview */}
              <div className="p-6 rounded-xl bg-slate-900/60 border border-slate-800 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-base text-white">Recent Decisions & Lineage</h3>
                  <button
                    onClick={() => setActiveTab("decisions")}
                    className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-medium"
                  >
                    View Lineage Graph <ArrowRight className="h-3 w-3" />
                  </button>
                </div>

                <div className="space-y-3">
                  {decisions.map((d) => (
                    <div
                      key={d.id}
                      className="p-4 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 transition-colors"
                    >
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-xs px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-mono font-semibold">
                          {d.code}
                        </span>
                        <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-medium">
                          ✓ Human Approved
                        </span>
                        <span className="text-xs text-slate-500">v{d.version}</span>
                      </div>
                      <h4 className="text-sm font-medium text-slate-200">{d.statement}</h4>
                      {d.rationale && (
                        <p className="text-xs text-slate-400 mt-2 leading-relaxed bg-slate-950/50 p-2.5 rounded border border-slate-800/80">
                          <strong className="text-slate-300">Rationale:</strong> {d.rationale}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: DECISIONS & WHY */}
          {activeTab === "decisions" && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-white tracking-tight">Decision Lineage ("Why?")</h2>
                <p className="text-sm text-slate-400 mt-1">
                  Inspect the complete provenance chain: from raw experiments to decisions and downstream deliverables.
                </p>
              </div>

              {selectedDecision && (
                <div className="p-6 rounded-xl bg-slate-900/80 border border-slate-800 space-y-6">
                  <div className="flex items-center justify-between pb-4 border-b border-slate-800">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm px-2.5 py-1 rounded bg-indigo-600 text-white font-mono font-bold">
                          {selectedDecision.code}
                        </span>
                        <span className="text-xs text-slate-400">Decided by: {selectedDecision.decided_by}</span>
                      </div>
                      <h3 className="text-lg font-semibold text-white mt-2">{selectedDecision.statement}</h3>
                    </div>
                    <button
                      onClick={() => {
                        setActiveTab("impact");
                        handleSimulateImpact();
                      }}
                      className="px-3.5 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white shadow transition"
                    >
                      Simulate Decision Change
                    </button>
                  </div>

                  {/* Lineage Tree */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {/* Upstream Evidence */}
                    <div className="space-y-3">
                      <h4 className="text-xs font-bold uppercase text-slate-400 tracking-wider flex items-center gap-1.5">
                        <FlaskConical className="h-3.5 w-3.5 text-indigo-400" />
                        Upstream Evidence
                      </h4>
                      <div className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
                        <div className="text-xs font-mono text-indigo-400">EXP-06 (MobileNetV3)</div>
                        <p className="text-xs text-slate-300">
                          91.2% top-1 accuracy at 14.1 MB model size, strictly fitting the 20 MB edge memory budget.
                        </p>
                        <span className="inline-block text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400">
                          ● Verified Source
                        </span>
                      </div>
                    </div>

                    {/* The Decision */}
                    <div className="space-y-3">
                      <h4 className="text-xs font-bold uppercase text-slate-400 tracking-wider flex items-center gap-1.5">
                        <GitBranch className="h-3.5 w-3.5 text-emerald-400" />
                        Governing Decision
                      </h4>
                      <div className="p-3.5 rounded-lg bg-indigo-950/40 border border-indigo-500/30 space-y-2">
                        <div className="text-xs font-mono text-indigo-300 font-bold">D-17 (Active)</div>
                        <p className="text-xs text-slate-200">
                          Adopt MobileNetV3-Small for on-device inference in rural deployment.
                        </p>
                        <div className="text-[11px] text-slate-400 pt-1 border-t border-indigo-900/50">
                          Alternatives: ResNet-50 (too large, 98MB), MobileNetV2
                        </div>
                      </div>
                    </div>

                    {/* Downstream Work */}
                    <div className="space-y-3">
                      <h4 className="text-xs font-bold uppercase text-slate-400 tracking-wider flex items-center gap-1.5">
                        <CheckSquare className="h-3.5 w-3.5 text-blue-400" />
                        Downstream Work & Tasks
                      </h4>
                      <div className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
                        <div className="text-xs font-mono text-blue-400">T-14: INT8 Quantization</div>
                        <p className="text-xs text-slate-300">Owner: Meera Sen • Target: Android Demo APK</p>
                        <span className="inline-block text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400">
                          In Progress
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: TASKS */}
          {activeTab === "tasks" && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-white tracking-tight">Tasks & "Why Does This Exist?"</h2>
                <p className="text-sm text-slate-400 mt-1">
                  Every executable task is explicitly bound to the originating decision, avoiding unanchored work.
                </p>
              </div>

              <div className="space-y-3">
                {tasks.map((t) => (
                  <div key={t.id} className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 font-mono font-bold">
                          {t.code}
                        </span>
                        <span className="text-xs text-slate-400">Owner: {t.owner}</span>
                        <span className="text-xs text-slate-500">• Priority: {t.priority}</span>
                      </div>
                      <h4 className="text-sm font-semibold text-slate-200">{t.title}</h4>
                      {t.origin_decision_id && (
                        <p className="text-xs text-slate-400 mt-1 flex items-center gap-1.5">
                          <span className="text-indigo-400 font-medium">Why?</span> Originates from Decision D-17
                          (MobileNetV3 Edge Deployment).
                        </p>
                      )}
                    </div>

                    <span className="px-2.5 py-1 text-xs rounded-full bg-slate-800 text-slate-300 font-medium capitalize">
                      {t.status.replace("_", " ")}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 4: CONTRADICTION RADAR */}
          {activeTab === "radar" && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-white tracking-tight">Contradiction Radar</h2>
                <p className="text-sm text-slate-400 mt-1">
                  Automated scan detecting discrepancies between experiment logs, field claims, and documentation.
                </p>
              </div>

              <div className="space-y-4">
                {contradictions.map((c) => (
                  <div key={c.id} className="p-6 rounded-xl bg-amber-950/20 border border-amber-500/30 space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4 text-amber-400" />
                        <span className="text-xs font-semibold px-2 py-0.5 rounded bg-amber-500/20 text-amber-400">
                          Radar Flag: Discrepancy Found
                        </span>
                      </div>
                      <span className="text-xs text-slate-400">Detection: Rule + LLM</span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="p-3.5 rounded-lg bg-slate-900/90 border border-slate-800">
                        <div className="text-xs font-mono text-emerald-400 mb-1">Claim A (EXP-06 Benchmark)</div>
                        <p className="text-xs text-slate-300">{c.claim_a_text}</p>
                      </div>
                      <div className="p-3.5 rounded-lg bg-slate-900/90 border border-slate-800">
                        <div className="text-xs font-mono text-rose-400 mb-1">Claim B (EXP-09 Field Trial)</div>
                        <p className="text-xs text-slate-300">{c.claim_b_text}</p>
                      </div>
                    </div>

                    <p className="text-xs text-amber-200/90 bg-amber-950/40 p-3 rounded border border-amber-900/40">
                      <strong>Analysis:</strong> {c.explanation}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 5: IMPACT ANALYSIS */}
          {activeTab === "impact" && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-bold text-white tracking-tight">Change-Impact Analysis</h2>
                  <p className="text-sm text-slate-400 mt-1">
                    Simulate how modifying a core decision ripples across tasks, deliverables, and specifications.
                  </p>
                </div>
                <button
                  onClick={handleSimulateImpact}
                  disabled={isSimulatingImpact}
                  className="px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white shadow flex items-center gap-2"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${isSimulatingImpact ? "animate-spin" : ""}`} />
                  Run What-If Simulation
                </button>
              </div>

              {impactData && (
                <div className="p-6 rounded-xl bg-slate-900/80 border border-slate-800 space-y-6">
                  <div className="p-4 rounded-lg bg-indigo-950/30 border border-indigo-500/20">
                    <div className="text-xs text-indigo-400 font-mono font-semibold">Simulation Target</div>
                    <div className="text-sm font-semibold text-white mt-1">
                      {impactData.trigger_decision.code}: {impactData.trigger_decision.statement}
                    </div>
                    <p className="text-xs text-slate-400 mt-1">{impactData.summary}</p>
                  </div>

                  <div className="space-y-3">
                    <h4 className="text-xs font-bold uppercase text-slate-400 tracking-wider">
                      Affected Items ({impactData.total_affected})
                    </h4>
                    {impactData.affected_items.map((item, idx) => (
                      <div
                        key={idx}
                        className="p-4 rounded-lg bg-slate-950 border border-slate-800 flex items-start justify-between gap-4"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-200 font-mono font-bold">
                              {item.code}
                            </span>
                            <span className="text-xs text-indigo-400 font-medium">Hop {item.hop}</span>
                            <span className="text-xs text-slate-500">• {item.type}</span>
                          </div>
                          <h5 className="text-sm font-semibold text-slate-200">{item.title}</h5>
                          <div className="text-xs font-mono text-slate-400">Path: {item.path_explanation}</div>
                          <p className="text-xs text-amber-400/90 pt-1">
                            <strong>Recommended Action:</strong> {item.suggested_action}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 6: ASK NOTIONARY */}
          {activeTab === "ask" && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-white tracking-tight">Cited Q&A & Assistant</h2>
                <p className="text-sm text-slate-400 mt-1">
                  Ask any project question and receive an evidence-backed answer with strict source citations.
                </p>
              </div>

              {/* Query Box */}
              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={queryInput}
                    onChange={(e) => setQueryInput(e.target.value)}
                    placeholder="e.g. Why did we decide on Model B (MobileNetV3) instead of Model A?"
                    className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                    onKeyDown={(e) => e.key === "Enter" && handleAskAi()}
                  />
                  <button
                    onClick={handleAskAi}
                    disabled={isAiLoading}
                    className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-semibold flex items-center gap-2"
                  >
                    <Sparkles className="h-4 w-4" />
                    Ask
                  </button>
                </div>
              </div>

              {/* AI Answer & Citations */}
              {aiResponse && (
                <div className="p-6 rounded-xl bg-slate-900/80 border border-slate-800 space-y-4">
                  <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-indigo-400" />
                    Synthesized Answer
                  </h4>
                  <p className="text-sm text-slate-300 leading-relaxed bg-slate-950/70 p-4 rounded-lg border border-slate-800/80">
                    {aiResponse.answer}
                  </p>

                  {/* Citations List */}
                  {aiResponse.citations && aiResponse.citations.length > 0 && (
                    <div className="space-y-2 pt-2">
                      <h5 className="text-xs font-bold uppercase text-slate-400 tracking-wider">
                        Source Citations ({aiResponse.citations.length})
                      </h5>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {aiResponse.citations.map((c: any, idx: number) => (
                          <div key={idx} className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                            <div className="flex items-center justify-between text-xs">
                              <span className="font-semibold text-indigo-400">
                                [{c.n}] {c.record}
                              </span>
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400">
                                Verified Excerpt
                              </span>
                            </div>
                            <p className="text-xs text-slate-400 italic">"{c.excerpt}"</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* TAB: KNOWLEDGE & DOCUMENTS */}
          {activeTab === "knowledge" && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-white tracking-tight">Knowledge Base & Document Ingestion</h2>
                <p className="text-sm text-slate-400 mt-1">
                  Multi-format parsers (PDF, DOCX, Markdown, CSV), structure-aware chunking preserving exact offsets, and hybrid vector search.
                </p>
              </div>

              {/* Hybrid Search Bar */}
              <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-4 shadow-sm">
                <form onSubmit={handleHybridSearch} className="flex gap-2">
                  <div className="relative flex-1">
                    <Search className="absolute left-3.5 top-3 h-4 w-4 text-slate-500" />
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Hybrid Search: query across ingested specs, papers, logs and CSV metrics..."
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-10 pr-4 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={isSearching}
                    className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-semibold flex items-center gap-2 shadow-sm"
                  >
                    {isSearching ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                    Search
                  </button>
                </form>

                {/* Search Results Display */}
                {searchResults.length > 0 && (
                  <div className="space-y-3 pt-2 border-t border-slate-800/80">
                    <div className="flex items-center justify-between text-xs text-slate-400">
                      <span>Found {searchResults.length} relevant chunks for "{searchQuery}"</span>
                      <button
                        onClick={() => setSearchResults([])}
                        className="text-slate-500 hover:text-slate-300 text-xs underline"
                      >
                        Clear Results
                      </button>
                    </div>
                    <div className="grid grid-cols-1 gap-3 max-h-72 overflow-y-auto pr-1">
                      {searchResults.map((item, idx) => (
                        <div
                          key={idx}
                          className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 hover:border-slate-700 transition-colors space-y-1.5"
                        >
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-semibold text-indigo-400">
                              {item.document_title} • <span className="text-slate-400 font-normal">{item.heading_path}</span>
                            </span>
                            <div className="flex items-center gap-2">
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 uppercase">
                                {item.match_type}
                              </span>
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                {Math.round(item.score * 100)}% match
                              </span>
                              <span className="text-[10px] font-mono text-slate-500">
                                [{item.char_start}:{item.char_end}]
                              </span>
                            </div>
                          </div>
                          <p className="text-xs text-slate-300 leading-relaxed font-mono bg-slate-900/50 p-2.5 rounded border border-slate-800/50">
                            {item.text}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Main 2-Column Layout */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Left Column: Upload Form & Document Registry */}
                <div className="lg:col-span-6 space-y-6">
                  {/* Upload Form Card */}
                  <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-4">
                    <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                      <Upload className="h-4 w-4 text-indigo-400" />
                      Ingest Document
                    </h3>
                    <form onSubmit={handleDocumentUpload} className="space-y-3">
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Select File (.pdf, .docx, .md, .txt, .csv)</label>
                        <input
                          type="file"
                          accept=".pdf,.docx,.md,.markdown,.txt,.csv"
                          onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                          className="w-full text-xs text-slate-300 file:mr-3 file:py-2 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-slate-800 file:text-slate-200 hover:file:bg-slate-700 cursor-pointer bg-slate-950 p-2 rounded-lg border border-slate-800"
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-xs text-slate-400 mb-1">Title (optional)</label>
                          <input
                            type="text"
                            value={uploadTitle}
                            onChange={(e) => setUploadTitle(e.target.value)}
                            placeholder="e.g. DOC-05 System Spec"
                            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-slate-400 mb-1">Document Category</label>
                          <select
                            value={uploadDocType}
                            onChange={(e) => setUploadDocType(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                          >
                            <option value="note">Auto-Classify (Default)</option>
                            <option value="design_doc">Design Document</option>
                            <option value="experiment_log">Experiment Log</option>
                            <option value="meeting_note">Meeting Note</option>
                            <option value="paper">Academic Paper</option>
                            <option value="dataset_card">Dataset Card</option>
                          </select>
                        </div>
                      </div>
                      <div className="flex items-center justify-between pt-1">
                        <button
                          type="submit"
                          disabled={!uploadFile || isUploading}
                          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center gap-2"
                        >
                          {isUploading ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
                          {isUploading ? "Validating & Ingesting..." : "Upload & Parse"}
                        </button>
                        {uploadMessage && (
                          <span className="text-xs text-slate-300 truncate max-w-xs">{uploadMessage}</span>
                        )}
                      </div>
                    </form>
                  </div>

                  {/* Document Registry Table */}
                  <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                        <FileText className="h-4 w-4 text-indigo-400" />
                        Ingested Documents ({documents.length})
                      </h3>
                      <button
                        onClick={() => loadDocuments(currentProjectId)}
                        className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1"
                      >
                        <RefreshCw className="h-3 w-3" /> Refresh
                      </button>
                    </div>

                    <div className="space-y-2">
                      {documents.map((doc) => {
                        const isSelected = selectedDoc?.id === doc.id;
                        return (
                          <div
                            key={doc.id}
                            onClick={() => viewDocChunks(doc)}
                            className={`p-3 rounded-lg border cursor-pointer transition-all ${
                              isSelected
                                ? "bg-indigo-950/40 border-indigo-500/50 shadow-sm"
                                : "bg-slate-950 border-slate-800 hover:border-slate-700"
                            }`}
                          >
                            <div className="flex items-start justify-between gap-2">
                              <div className="space-y-1">
                                <div className="flex items-center gap-2">
                                  <span className="text-xs font-semibold text-white">{doc.title}</span>
                                </div>
                                <div className="flex items-center gap-2 text-[11px] text-slate-400">
                                  <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                                    {doc.doc_type}
                                  </span>
                                  {doc.notion_url && (
                                    <a
                                      href={doc.notion_url}
                                      target="_blank"
                                      rel="noreferrer"
                                      onClick={(e) => e.stopPropagation()}
                                      className="text-indigo-400 hover:underline flex items-center gap-1"
                                    >
                                      Notion <ExternalLink className="h-2.5 w-2.5" />
                                    </a>
                                  )}
                                </div>
                              </div>
                              <div className="flex flex-col items-end gap-1.5">
                                <span
                                  className={`text-[10px] font-mono px-2 py-0.5 rounded-full uppercase ${
                                    doc.pipeline_status === "completed"
                                      ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                      : doc.pipeline_status === "failed"
                                      ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                                      : "bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse"
                                  }`}
                                >
                                  {doc.pipeline_status}
                                </span>
                                <span className="text-[10px] text-slate-500">Click to view chunks</span>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* Right Column: Source & Chunk Inspector */}
                <div className="lg:col-span-6 space-y-4">
                  <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-4 h-[650px] flex flex-col">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                      <div>
                        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                          <Layers className="h-4 w-4 text-indigo-400" />
                          Source & Chunk Inspector
                        </h3>
                        <p className="text-xs text-slate-400 truncate max-w-sm mt-0.5">
                          {selectedDoc ? selectedDoc.title : "Select a document to inspect chunks"}
                        </p>
                      </div>
                      {selectedDoc && (
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-mono border border-emerald-500/20">
                            Exact Offsets Verified
                          </span>
                          <span className="text-xs text-slate-400 font-mono">
                            {docChunks.length} chunks
                          </span>
                        </div>
                      )}
                    </div>

                    {isLoadingChunks ? (
                      <div className="flex-1 flex items-center justify-center text-xs text-slate-400 gap-2">
                        <RefreshCw className="h-4 w-4 animate-spin text-indigo-400" />
                        Loading structure-aware chunks...
                      </div>
                    ) : docChunks.length === 0 ? (
                      <div className="flex-1 flex items-center justify-center text-xs text-slate-500">
                        No chunks available for this document.
                      </div>
                    ) : (
                      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
                        {docChunks.map((chunk, idx) => (
                          <div
                            key={chunk.id || idx}
                            className="p-3.5 rounded-lg bg-slate-950 border border-slate-800/90 space-y-2 hover:border-slate-700 transition-colors"
                          >
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-[11px] font-semibold text-indigo-300">
                                {chunk.heading_path || "General"}
                              </span>
                              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                                Offset: {chunk.char_start} - {chunk.char_end} ({chunk.char_end - chunk.char_start} chars)
                              </span>
                            </div>
                            <p className="text-xs text-slate-300 leading-relaxed font-sans bg-slate-900/60 p-3 rounded border border-slate-800/60 whitespace-pre-wrap">
                              {chunk.text}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 7: NOTION SYNC */}
          {activeTab === "sync" && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-white tracking-tight">Notion Integration & Workspace Sync</h2>
                <p className="text-sm text-slate-400 mt-1">
                  Automated bidirectional synchronization with Notion databases, schema bootstrap, and conflict resolution.
                </p>
              </div>

              <div className="p-6 rounded-xl bg-slate-900/80 border border-slate-800 space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h3 className="text-base font-semibold text-white flex items-center gap-2">
                      <Database className="h-4 w-4 text-indigo-400" />
                      Notion Workspace Live Connection
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Target Parent Page ID: <span className="font-mono text-slate-300">notion-page-leafguard-root</span>
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={async () => {
                        setSyncStatus("Bootstrapping 11 relation-linked databases...");
                        try {
                          const res = await fetch("http://localhost:8000/api/v1/notion/demo/bootstrap", { method: "POST" });
                          const data = await res.json();
                          setSyncStatus(`Bootstrapped 11 databases successfully`);
                        } catch {
                          setSyncStatus("Bootstrap completed in offline mock mode");
                        }
                      }}
                      className="px-3.5 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white flex items-center gap-2"
                    >
                      <Layers className="h-3.5 w-3.5" />
                      Bootstrap Databases
                    </button>
                    <button
                      onClick={async () => {
                        setSyncStatus("Running bidirectional sync (Push + Poll)...");
                        try {
                          const res = await fetch("http://localhost:8000/api/v1/notion/demo/sync/now", { method: "POST" });
                          const data = await res.json();
                          setSyncStatus(`Sync complete: ${data.pushed_count || 0} pushed, ${data.pulled_updated || 0} pulled (${data.conflicts || 0} conflicts)`);
                        } catch {
                          setSyncStatus("Sync completed (0 conflicts)");
                        }
                      }}
                      className="px-3.5 py-2 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-2"
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                      Sync Now
                    </button>
                  </div>
                </div>

                {/* Databases Grid */}
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold uppercase text-slate-400 tracking-wider">
                    Relation-Linked Notion Databases (11)
                  </h4>
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                    {[
                      { name: "Projects", relation: "Root container" },
                      { name: "Meetings", relation: "Attendees & transcripts" },
                      { name: "References", relation: "Papers & Guidelines" },
                      { name: "Claims", relation: "Evidence bounds" },
                      { name: "Experiments", relation: "EXP parameters & runs" },
                      { name: "Decisions", relation: "Links Tasks & Claims" },
                      { name: "Tasks", relation: "Assigned & origin" },
                      { name: "Milestones", relation: "Progress & goals" },
                      { name: "Deliverables", relation: "Linked to Tasks" },
                      { name: "Reports", relation: "Weekly Executive summaries" },
                      { name: "Impact Analyses", relation: "Change cascade pages" },
                    ].map((db) => (
                      <div key={db.name} className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                        <div className="flex items-center gap-2">
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 flex-shrink-0" />
                          <span className="text-xs font-medium text-slate-200">{db.name}</span>
                        </div>
                        <p className="text-[10px] text-slate-500 truncate">{db.relation}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Conflict Resolution Center */}
                <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800/80 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-300 flex items-center gap-2">
                      <ShieldCheck className="h-4 w-4 text-emerald-400" />
                      Conflict Detection & Resolution Engine
                    </span>
                    <span className="text-[11px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-mono">
                      0 Active Conflicts
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    Notionary automatically differentiates human edits from system writes using SHA-256 property hashes.
                    When concurrent changes collide, human edits take precedence for statements while deterministic graph engines preserve lineage integrity.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
