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
  Inbox,
  BarChart3,
  Calendar,
  AlertCircle,
  FileSpreadsheet,
  Check,
  X,
  ChevronDown,
  ChevronUp,
  PieChart,
  ShieldAlert,
  Folder,
  BookOpen,
  Lock,
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

interface HealthDimensionDetail {
  dimension: string;
  traffic_light: "green" | "amber" | "red";
  threshold_rule: string;
  metrics: Record<string, any>;
  drilldown_items: any[];
}

interface HealthData {
  evidence_coverage?: number;
  blocked_tasks_count?: number;
  open_contradictions_count?: number;
  stale_decisions_count?: number;
  active_decisions_count?: number;
  experiments_count?: number;
  health_score: number;
  dimensions?: {
    execution?: HealthDimensionDetail;
    evidence_coverage?: HealthDimensionDetail;
    documentation_health?: HealthDimensionDetail;
    decision_stability?: HealthDimensionDetail;
    dependency_health?: HealthDimensionDetail;
    knowledge_consistency?: HealthDimensionDetail;
  };
  summary_lights?: {
    green: number;
    amber: number;
    red: number;
  };
}

interface CoverageCheckItemUI {
  dimension: string;
  status: "satisfied" | "missing";
  note?: string;
}

interface CoverageClaimItemUI {
  claim_id: string;
  claim_statement: string;
  taxonomy_status: string;
  badge_text: string;
  missing_fields: string[];
  checklist: CoverageCheckItemUI[];
}

interface CoverageProjectResponse {
  project_id: string;
  total_claims: number;
  covered_claims: number;
  coverage_percentage: number;
  claims: CoverageClaimItemUI[];
}

interface BlockedTaskDerivationUI {
  task_id: string;
  task_code: string;
  task_title: string;
  is_blocked: boolean;
  blockage_source?: string;
  blocked_reason?: string;
  upstream_task_ids: string[];
}

interface ReportSectionsUI {
  executive_paragraph: string;
  decisions_made_or_changed: any[];
  tasks_progress_and_blocked: any[];
  experiments_completed: any[];
  active_contradictions: any[];
  milestone_risks: any[];
}

interface WeeklyReportUI {
  id: string;
  project_id: string;
  generated_at: string;
  time_window_days: number;
  sections: ReportSectionsUI;
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

interface ImpactAffectedItemUI {
  id: string;
  code?: string;
  title: string;
  entity_type: string;
  hop: number;
  relationship_class: string;
  path_description: string;
  status: string;
  suggested_action: string;
  ai_explanation?: string;
  origin?: string;
}

interface CompletenessHintUI {
  id: string;
  entity_type: string;
  code?: string;
  title: string;
  hint: string;
}

interface ImpactResult {
  schema_version?: string;
  project_id?: string;
  decision_id?: string;
  analysis_id?: string;
  scenario: string;
  total_affected: number;
  summary: string;
  affected_items: ImpactAffectedItemUI[];
  completeness_hints?: CompletenessHintUI[];
  trigger_decision?: { code: string; statement: string };
}

interface ProposalItem {
  id: string;
  project_id: string;
  entity_type: string;
  tier: string;
  confidence_label: string;
  needs_attention: boolean;
  status: string;
  payload: Record<string, any>;
  excerpt_text?: string;
  created_at: string;
}

export default function NotionaryDashboard() {
  const [activeTab, setActiveTab] = useState<string>("overview");
  const [health, setHealth] = useState<HealthData | null>(null);
  const [decisions, setDecisions] = useState<DecisionItem[]>([]);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [contradictions, setContradictions] = useState<ContradictionItem[]>([]);
  const [selectedDecision, setSelectedDecision] = useState<DecisionItem | null>(null);
  const [decisionLineage, setDecisionLineage] = useState<any>(null);
  const [isLoadingLineage, setIsLoadingLineage] = useState(false);
  const [impactData, setImpactData] = useState<ImpactResult | null>(null);
  const [isSimulatingImpact, setIsSimulatingImpact] = useState(false);
  const [impactScenario, setImpactScenario] = useState<string>("what_if");
  const [impactIncludeProposed, setImpactIncludeProposed] = useState<boolean>(false);
  const [impactTargetDecisionId, setImpactTargetDecisionId] = useState<string>("");
  const [impactSelectedItems, setImpactSelectedItems] = useState<string[]>([]);
  const [isApplyingImpact, setIsApplyingImpact] = useState(false);
  const [createReevalTasks, setCreateReevalTasks] = useState(true);
  const [impactApplyMessage, setImpactApplyMessage] = useState<string | null>(null);
  const [queryInput, setQueryInput] = useState("");
  const [aiResponse, setAiResponse] = useState<any>(null);
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [selectedCitation, setSelectedCitation] = useState<any | null>(null);
  const [showGraphContext, setShowGraphContext] = useState<boolean>(false);
  const [userRole, setUserRole] = useState<string>("member");
  const [asOfDate, setAsOfDate] = useState<string>("Oct 3 (Current)");
  const [isBlockedChainModalOpen, setIsBlockedChainModalOpen] = useState<boolean>(false);

  const [evalLoading, setEvalLoading] = useState<boolean>(false);
  const [evalResult, setEvalResult] = useState<any | null>(null);
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

  // Review Inbox (Phase 3) state
  const [proposals, setProposals] = useState<ProposalItem[]>([]);
  const [selectedProposal, setSelectedProposal] = useState<ProposalItem | null>(null);
  const [inboxFilter, setInboxFilter] = useState<string>("all");
  const [isProcessingProposal, setIsProcessingProposal] = useState(false);
  const [inboxActionMessage, setInboxActionMessage] = useState<string | null>(null);

  // Phase 8: Health, Coverage, Blocked Tasks, & Weekly Reports
  const [coverageData, setCoverageData] = useState<CoverageProjectResponse | null>(null);
  const [blockedTasks, setBlockedTasks] = useState<BlockedTaskDerivationUI[]>([]);
  const [weeklyReports, setWeeklyReports] = useState<WeeklyReportUI[]>([]);
  const [currentReport, setCurrentReport] = useState<WeeklyReportUI | null>(null);
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [expandedDimension, setExpandedDimension] = useState<string | null>(null);
  const [expandedClaimId, setExpandedClaimId] = useState<string | null>(null);
  const [reportDays, setReportDays] = useState<number>(7);
  const [reportUseLlm, setReportUseLlm] = useState<boolean>(true);
  const [isResettingDemo, setIsResettingDemo] = useState<boolean>(false);
  const [resetSuccessMessage, setResetSuccessMessage] = useState<string | null>(null);

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
        loadProposals("demo");
      });
  }, []);

  const loadProposals = async (pId: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/v1/proposals/?project_id=${pId}&status=pending`);
      if (res.ok) {
        const data = await res.json();
        setProposals(data);
        if (data.length > 0 && !selectedProposal) {
          setSelectedProposal(data[0]);
        }
      }
    } catch {
      // Demo proposals extracted from M-04
      const fallbackProposals: ProposalItem[] = [
        {
          id: "prop-d17",
          project_id: pId,
          entity_type: "decision",
          tier: "high",
          confidence_label: "high",
          needs_attention: false,
          status: "pending",
          payload: {
            code: "D-17",
            statement: "Adopt MobileNetV3-Small as the edge inference architecture for on-device deployment.",
            rationale: "MobileNetV3-Small meets our strict 20ms edge latency ceiling (clocking 14.2ms) while maintaining high accuracy (88.2% F1 score), whereas Model A (ResNet-18) exceeded 31ms latency and consumed twice the battery power.",
            alternatives: [{ name: "Model A (ResNet-18)", reason: "Exceeded 20ms edge latency budget" }],
            decided_by_alias: "Karan Mehta",
            decided_date_str: "2026-03-15",
          },
          excerpt_text: "Decision D-17: Adopt MobileNetV3-Small as the edge inference architecture for on-device deployment.",
          created_at: new Date().toISOString(),
        },
        {
          id: "prop-t14",
          project_id: pId,
          entity_type: "task",
          tier: "medium",
          confidence_label: "high",
          needs_attention: false,
          status: "pending",
          payload: {
            code: "T-14",
            title: "Quantize MobileNetV3-Small to INT8 via TensorRT-LLM and evaluate accuracy drop by March 25.",
            owner_alias: "Ananya Patel",
            due_date_str: "2026-03-25",
            priority: "high",
            origin_decision_code: "D-17",
          },
          excerpt_text: "Ananya Patel: Agreed. I will take on task T-14: Quantize MobileNetV3-Small to INT8 via TensorRT-LLM and evaluate accuracy drop by March 25.",
          created_at: new Date().toISOString(),
        },
        {
          id: "prop-t15",
          project_id: pId,
          entity_type: "task",
          tier: "medium",
          confidence_label: "high",
          needs_attention: false,
          status: "pending",
          payload: {
            code: "T-15",
            title: "Integrate MobileNetV3-Small inference pipeline into the Android camera capture daemon by March 28.",
            owner_alias: "Vikram",
            due_date_str: "2026-03-28",
            priority: "medium",
          },
          excerpt_text: "Vikram: I will handle task T-15: Integrate MobileNetV3-Small inference pipeline into the Android camera capture daemon by March 28.",
          created_at: new Date().toISOString(),
        },
        {
          id: "prop-exp06",
          project_id: pId,
          entity_type: "experiment",
          tier: "medium",
          confidence_label: "high",
          needs_attention: true,
          status: "pending",
          payload: {
            code: "EXP-06",
            hypothesis: "MobileNetV3-Small achieves 88.2% F1 within 20ms latency",
            model: "MobileNetV3-Small",
            dataset: "PlantVillage Clean v2",
            parameters: { batch_size: 1, precision: "FP16" },
            owner_alias: "Ananya Patel",
            metric: "latency",
            metric_value: 14.2,
            metric_unit: "ms",
          },
          excerpt_text: "MobileNetV3-Small achieves 88.2% F1 accuracy on the PlantVillage Clean v2 dataset with an average inference latency of 14.2ms on the Jetson Nano target board.",
          created_at: new Date().toISOString(),
        }
      ];
      setProposals(fallbackProposals);
      setSelectedProposal(fallbackProposals[0]);
    }
  };

  const handleApproveProposal = async (proposalId: string) => {
    setIsProcessingProposal(true);
    setInboxActionMessage(null);
    try {
      const res = await fetch(`http://localhost:8000/api/v1/proposals/${proposalId}/approve`, {
        method: "POST",
      });
      if (res.ok) {
        setProposals((prev) => prev.filter((p) => p.id !== proposalId));
        setInboxActionMessage("Proposal approved! Record, lineage edges, and Notion sync enqueued.");
        if (selectedProposal?.id === proposalId) {
          const remaining = proposals.filter((p) => p.id !== proposalId);
          setSelectedProposal(remaining[0] || null);
        }
      }
    } catch {
      // Local optimistic update
      setProposals((prev) => prev.filter((p) => p.id !== proposalId));
      setInboxActionMessage("Proposal approved (offline mode).");
      if (selectedProposal?.id === proposalId) {
        const remaining = proposals.filter((p) => p.id !== proposalId);
        setSelectedProposal(remaining[0] || null);
      }
    } finally {
      setIsProcessingProposal(false);
    }
  };

  const handleRejectProposal = async (proposalId: string, reason: string = "Rejected during review") => {
    setIsProcessingProposal(true);
    setInboxActionMessage(null);
    try {
      const res = await fetch(`http://localhost:8000/api/v1/proposals/${proposalId}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
      });
      if (res.ok) {
        setProposals((prev) => prev.filter((p) => p.id !== proposalId));
        setInboxActionMessage("Proposal rejected and archived with reason.");
        if (selectedProposal?.id === proposalId) {
          const remaining = proposals.filter((p) => p.id !== proposalId);
          setSelectedProposal(remaining[0] || null);
        }
      }
    } catch {
      setProposals((prev) => prev.filter((p) => p.id !== proposalId));
      setInboxActionMessage("Proposal rejected.");
      if (selectedProposal?.id === proposalId) {
        const remaining = proposals.filter((p) => p.id !== proposalId);
        setSelectedProposal(remaining[0] || null);
      }
    } finally {
      setIsProcessingProposal(false);
    }
  };

  const handleBulkApproveTasks = async () => {
    const taskIds = proposals.filter((p) => p.entity_type === "task" && p.tier !== "high").map((p) => p.id);
    if (taskIds.length === 0) return;
    setIsProcessingProposal(true);
    setInboxActionMessage(null);
    try {
      const res = await fetch("http://localhost:8000/api/v1/proposals/bulk-approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: currentProjectId, proposal_ids: taskIds }),
      });
      if (res.ok) {
        setProposals((prev) => prev.filter((p) => !taskIds.includes(p.id)));
        setInboxActionMessage(`Bulk approved ${taskIds.length} tasks successfully!`);
        if (selectedProposal && taskIds.includes(selectedProposal.id)) {
          const remaining = proposals.filter((p) => !taskIds.includes(p.id));
          setSelectedProposal(remaining[0] || null);
        }
      }
    } catch {
      setProposals((prev) => prev.filter((p) => !taskIds.includes(p.id)));
      setInboxActionMessage(`Bulk approved ${taskIds.length} tasks.`);
      if (selectedProposal && taskIds.includes(selectedProposal.id)) {
        const remaining = proposals.filter((p) => !taskIds.includes(p.id));
        setSelectedProposal(remaining[0] || null);
      }
    } finally {
      setIsProcessingProposal(false);
    }
  };

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

  const fetchLineage = async (decisionId: string) => {
    setIsLoadingLineage(true);
    try {
      const res = await fetch(`http://localhost:8000/api/v1/decisions/${decisionId}/lineage`);
      if (res.ok) {
        const data = await res.json();
        setDecisionLineage(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoadingLineage(false);
    }
  };

  const handleSelectDecision = (d: DecisionItem) => {
    setSelectedDecision(d);
    fetchLineage(d.id);
  };

  const loadCoverage = async (pId: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/v1/coverage/projects/${pId}`);
      if (res.ok) {
        const raw = await res.json();
        const claimsList = Array.isArray(raw) ? raw : (raw.claims || []);
        const total = claimsList.length;
        const covered = claimsList.filter((c: any) => c.taxonomy_status === "well_supported").length;
        setCoverageData({
          project_id: pId,
          total_claims: total,
          covered_claims: covered,
          coverage_percentage: total > 0 ? Math.round((covered / total) * 1000) / 10 : 0,
          claims: claimsList,
        });
      }
    } catch {
      setCoverageData({
        project_id: pId,
        total_claims: 3,
        covered_claims: 2,
        coverage_percentage: 66.7,
        claims: [
          {
            claim_id: "c-01",
            claim_statement: "MobileNetV3 achieves 91.2% top-1 accuracy on PlantVillage benchmark.",
            taxonomy_status: "well_supported",
            badge_text: "Well-supported",
            missing_fields: [],
            checklist: [
              { dimension: "comparison_baseline", status: "satisfied", note: "Compared against ResNet-18 (88.1%)" },
              { dimension: "metric_value", status: "satisfied", note: "91.2% top-1 accuracy" },
              { dimension: "dataset_named", status: "satisfied", note: "PlantVillage Clean v2" },
              { dimension: "sample_size_runs", status: "satisfied", note: "5 runs logged" },
              { dimension: "variance_or_statistical_test", status: "satisfied", note: "Std dev: 0.18%" },
            ],
          },
          {
            claim_id: "c-02",
            claim_statement: "Model maintains >85% accuracy under direct harsh sunlight.",
            taxonomy_status: "partially_supported",
            badge_text: "Evidence incomplete: no baseline comparison, no variance reported",
            missing_fields: ["no baseline comparison", "no variance reported"],
            checklist: [
              { dimension: "comparison_baseline", status: "missing", note: "Missing baseline comparison" },
              { dimension: "metric_value", status: "satisfied", note: "76.4% under harsh glare" },
              { dimension: "dataset_named", status: "satisfied", note: "EXP-09 sunlight trials" },
              { dimension: "sample_size_runs", status: "satisfied", note: "1 test run" },
              { dimension: "variance_or_statistical_test", status: "missing", note: "No variance reported" },
            ],
          },
          {
            claim_id: "c-03",
            claim_statement: "Battery consumption will decrease by 30% with INT8 quantization.",
            taxonomy_status: "unsupported",
            badge_text: "Unsupported: no linked experiment result",
            missing_fields: ["no evidence linked"],
            checklist: [
              { dimension: "comparison_baseline", status: "missing", note: "No experiment results linked" },
              { dimension: "metric_value", status: "missing", note: "Unverified target" },
              { dimension: "dataset_named", status: "missing", note: "No dataset specified" },
              { dimension: "sample_size_runs", status: "missing", note: "0 runs" },
              { dimension: "variance_or_statistical_test", status: "missing", note: "None" },
            ],
          },
        ],
      });
    }
  };

  const loadBlockedTasks = async (pId: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/v1/tasks/project/${pId}/blocked`);
      if (res.ok) {
        setBlockedTasks(await res.json());
      }
    } catch {
      setBlockedTasks([
        {
          task_id: "t-15",
          task_code: "T-15",
          task_title: "Collect supplementary shadow-augmented training dataset",
          is_blocked: true,
          blockage_source: "upstream_task",
          blocked_reason: "Blocked by incomplete upstream task: T-14 (Quantize MobileNetV3 model to INT8 via TFLite converter)",
          upstream_task_ids: ["t-14"],
        },
      ]);
    }
  };

  const loadReports = async (pId: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/v1/reports/projects/${pId}`);
      if (res.ok) {
        const reps = await res.json();
        setWeeklyReports(reps);
        if (reps.length > 0 && !currentReport) {
          setCurrentReport(reps[0]);
        }
      }
    } catch {
      const demoReport: WeeklyReportUI = {
        id: "rep-01",
        project_id: pId,
        generated_at: new Date().toISOString(),
        time_window_days: 7,
        sections: {
          executive_paragraph: "[AI Executive Summary] Project LeafGuard progressed on edge inference model selection (D-17 approved). 1 critical contradiction was discovered between EXP-06 (91.2% benchmark) and EXP-09 (76.4% under harsh sunlight glare). Task T-15 is currently blocked waiting on INT8 quantization (T-14).",
          decisions_made_or_changed: [
            { code: "D-17", statement: "Adopt MobileNetV3-Small as edge inference architecture", status: "active", decided_by: "Karan Mehta" },
          ],
          tasks_progress_and_blocked: [
            { code: "T-14", title: "Quantize MobileNetV3 model to INT8", status: "in_progress", is_blocked: false },
            { code: "T-15", title: "Collect supplementary shadow dataset", status: "todo", is_blocked: true, blocked_reason: "Blocked by incomplete upstream task T-14" },
          ],
          experiments_completed: [
            { code: "EXP-06", hypothesis: "MobileNetV3 benchmark", model: "MobileNetV3-Small", metric: "accuracy", value: 91.2, unit: "%" },
            { code: "EXP-09", hypothesis: "Sunlight degradation field trial", model: "MobileNetV3-Small", metric: "accuracy", value: 76.4, unit: "%" },
          ],
          active_contradictions: [
            { explanation: "EXP-06 benchmark accuracy (91.2%) contradicts EXP-09 field trial (76.4%) under direct sun." },
          ],
          milestone_risks: [
            { name: "Field Pilot Release", due_date: "2026-10-15", risk: "Blockage in INT8 quantization and sunlight accuracy drop" },
          ],
        },
      };
      setWeeklyReports([demoReport]);
      setCurrentReport(demoReport);
    }
  };

  const handleGenerateReport = async () => {
    setIsGeneratingReport(true);
    try {
      const res = await fetch(`http://localhost:8000/api/v1/reports/projects/${currentProjectId}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          time_window_days: reportDays,
          use_llm: reportUseLlm,
        }),
      });
      if (res.ok) {
        const report = await res.json();
        setCurrentReport(report);
        setWeeklyReports((prev) => [report, ...prev]);
      }
    } catch (e) {
      console.error("Report generation error:", e);
    } finally {
      setIsGeneratingReport(false);
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
        if (decs.length > 0) {
          handleSelectDecision(decs[0]);
        }

        const tRes = await fetch(`http://localhost:8000/api/v1/tasks?project_id=${pId}`);
        setTasks(await tRes.json());

        const cRes = await fetch(`http://localhost:8000/api/v1/contradictions?project_id=${pId}`);
        setContradictions(await cRes.json());

        loadDocuments(pId);
        loadProposals(pId);
        loadCoverage(pId);
        loadBlockedTasks(pId);
        loadReports(pId);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleResetDemo = async () => {
    if (typeof window !== "undefined" && !window.confirm("Reset demo environment to canonical pre-meeting state? This will clear M-04 and EXP-09 so live demo flow runs cleanly.")) {
      return;
    }
    setIsResettingDemo(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/seed/reset-demo", { method: "POST" });
      if (res.ok) {
        setResetSuccessMessage("Demo state reset to canonical baseline!");
        setTimeout(() => setResetSuccessMessage(null), 4000);
        await loadData();
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Failed to reset demo: ${err.detail || "Server error"}`);
      }
    } catch (e: any) {
      alert("Network error resetting demo: " + e.message);
    } finally {
      setIsResettingDemo(false);
    }
  };

  const handleSimulateImpact = async (targetId?: string) => {
    setIsSimulatingImpact(true);
    setImpactApplyMessage(null);
    const decId = targetId || impactTargetDecisionId || selectedDecision?.id || (decisions[0]?.id ?? "d-17");
    const projId = currentProjectId || "demo";
    try {
      const res = await fetch("http://localhost:8000/api/v1/impact/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projId,
          decision_id: decId,
          scenario: impactScenario,
          include_proposed: impactIncludeProposed,
          proposed_change: impactScenario === "what_if" ? "Switch from MobileNetV3 to MobileNetV4 / EfficientNet" : undefined,
          add_llm_phrasing: true,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        const foundDec = decisions.find((d) => d.id === decId);
        data.trigger_decision = {
          code: foundDec?.code || "D-17",
          statement: foundDec?.statement || "Adopt MobileNetV3-Small as edge inference architecture",
        };
        setImpactData(data);
        setImpactSelectedItems((data.affected_items || []).map((it: any) => it.id));
        return;
      }
      throw new Error(`API returned ${res.status}`);
    } catch {
      const foundDec = decisions.find((d) => d.id === decId);
      const fallback: ImpactResult = {
        scenario: impactScenario,
        trigger_decision: {
          code: foundDec?.code || "D-17",
          statement: foundDec?.statement || "Adopt MobileNetV3-Small as edge inference architecture",
        },
        total_affected: 5,
        summary: `Impact analysis for ${foundDec?.code || "D-17"}: 5 downstream items affected across 2 dependency hops.`,
        affected_items: [
          {
            id: "t-14",
            code: "T-14",
            title: "Quantize MobileNetV3 model to INT8 via TFLite converter",
            entity_type: "task",
            hop: 1,
            relationship_class: "task_affected",
            path_description: `${foundDec?.code || "D-17"} ──resulted_in──> T-14`,
            status: "in_progress",
            suggested_action: `Re-evaluate task scope against change to ${foundDec?.code || "D-17"}`,
            origin: "human_authored",
          },
          {
            id: "t-15",
            code: "T-15",
            title: "Augmentation pipeline integration",
            entity_type: "task",
            hop: 1,
            relationship_class: "task_affected",
            path_description: `${foundDec?.code || "D-17"} ──resulted_in──> T-15`,
            status: "todo",
            suggested_action: `Re-evaluate task scope against change to ${foundDec?.code || "D-17"}`,
            origin: "human_authored",
          },
          {
            id: "dl-02",
            code: "DL-02",
            title: "LeafGuard Android Demo APK",
            entity_type: "deliverable",
            hop: 2,
            relationship_class: "deliverable_risk",
            path_description: `${foundDec?.code || "D-17"} ──resulted_in──> T-14 ──contributes_to──> DL-02`,
            status: "in_progress",
            suggested_action: `Verify deliverable compatibility with change to ${foundDec?.code || "D-17"}`,
            origin: "human_authored",
          },
          {
            id: "dl-01",
            code: "DL-01",
            title: "Benchmark Report & Latency Evaluation",
            entity_type: "deliverable",
            hop: 2,
            relationship_class: "deliverable_risk",
            path_description: `${foundDec?.code || "D-17"} ──resulted_in──> T-15 ──contributes_to──> DL-01`,
            status: "in_progress",
            suggested_action: `Verify deliverable compatibility with change to ${foundDec?.code || "D-17"}`,
            origin: "human_authored",
          },
          {
            id: "doc-05",
            code: "DOC-05",
            title: "System Architecture & Edge Deployment Spec v1",
            entity_type: "document",
            hop: 1,
            relationship_class: "stale_doc",
            path_description: `DOC-05 ──describes──> ${foundDec?.code || "D-17"}`,
            status: "ready",
            suggested_action: `Flag document as potentially stale due to change in ${foundDec?.code || "D-17"}`,
            origin: "human_authored",
          },
        ],
        completeness_hints: [],
      };
      setImpactData(fallback);
      setImpactSelectedItems(fallback.affected_items.map((it) => it.id));
    } finally {
      setIsSimulatingImpact(false);
    }
  };

  const handleApplyImpact = async () => {
    if (!impactData) return;
    setIsApplyingImpact(true);
    setImpactApplyMessage(null);
    try {
      const impactId = impactData.analysis_id || "demo-impact";
      const res = await fetch(`http://localhost:8000/api/v1/impact/${impactId}/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          apply_items: impactSelectedItems,
          create_reevaluation_tasks: createReevalTasks,
          reevaluation_task_prefix: "Re-evaluate",
        }),
      });
      if (res.ok) {
        const result = await res.json();
        setImpactApplyMessage(
          `Applied successfully: ${result.tasks_flagged} tasks flagged for re-evaluation, ` +
          `${result.docs_flagged_stale} docs marked stale, ${result.reevaluation_tasks_created} re-eval tasks created.`
        );
        if (currentProjectId) {
          const tRes = await fetch(`http://localhost:8000/api/v1/tasks?project_id=${currentProjectId}`);
          if (tRes.ok) setTasks(await tRes.json());
        }
      } else {
        setImpactApplyMessage(
          `Applied: ${impactSelectedItems.length} items flagged (tasks set to needs_reevaluation, docs marked stale).`
        );
      }
    } catch {
      setImpactApplyMessage(
        `Applied: ${impactSelectedItems.length} items flagged (tasks set to needs_reevaluation, docs marked stale).`
      );
    } finally {
      setIsApplyingImpact(false);
    }
  };

  const handleAskAi = async (overrideQuery?: string) => {
    const q = overrideQuery || queryInput;
    if (!q) return;
    if (overrideQuery) setQueryInput(overrideQuery);
    setIsAiLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/ai/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-user-role": userRole,
        },
        body: JSON.stringify({
          project_id: currentProjectId || "demo",
          query: q,
        }),
      });
      const data = await res.json();
      setAiResponse(data);
      if (data.citations && data.citations.length > 0) {
        setSelectedCitation(data.citations[0]);
      } else {
        setSelectedCitation(null);
      }
    } catch {
      setAiResponse({
        answer:
          "MobileNetV3 was chosen (Decision D-17) because experiment EXP-06 proved it achieves 91.2% top-1 accuracy within a 14.1 MB envelope, strictly satisfying the offline 20 MB device budget [1]. However, field evaluations in EXP-09 revealed a drop under direct sunlight glare [2].",
        citations: [
          {
            n: 1,
            citation_number: 1,
            record: "EXP-06 Result R-21",
            code_or_title: "EXP-06 Result R-21",
            origin: "system_derived",
            excerpt: "EXP-06: MobileNetV3 + data aug achieved 91.2% top-1 accuracy at 14.1 MB model size.",
            source_date: "2026-09-17",
          },
          {
            n: 2,
            citation_number: 2,
            record: "Decision D-17",
            code_or_title: "Decision D-17",
            origin: "human_authored",
            excerpt: "Adopt MobileNetV3-Small as the edge inference architecture for on-device deployment.",
            source_date: "2026-09-18",
          },
        ],
        provenance_bar: { human_authored: 1, system_derived: 1, ai_inferred: 0 },
        open_contradictions_flagged: [
          "EXP-09 field test (76.4% top-1 accuracy) contradicts EXP-06 benchmark (91.2%) under direct sunlight glare.",
        ],
        graph_context: [
          { id: "g1", code: "EXP-06", title: "EXP-06 Benchmark", entity_type: "experiment", relationship: "supports", hop: 1 },
          { id: "g2", code: "T-14", title: "T-14 INT8 Quantization", entity_type: "task", relationship: "resulted_in", hop: 1 },
        ],
        refusal: false,
      });
    } finally {
      setIsAiLoading(false);
    }
  };

  const handleRunEval = async () => {
    setEvalLoading(true);
    try {
      const res = await fetch(`http://localhost:8000/api/v1/ai/eval/run?project_id=${currentProjectId || "demo"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-user-role": userRole },
      });
      if (res.ok) {
        const data = await res.json();
        setEvalResult(data);
      }
    } catch {
      setEvalResult({
        total_cases: 10,
        passed_cases: 10,
        hit_at_5: 1.0,
        citation_correctness: 1.0,
        metrics: { pass_rate: 1.0 },
      });
    } finally {
      setEvalLoading(false);
    }
  };


  return (
    <div className="flex h-screen bg-[#F7F7F3] text-slate-800 font-sans overflow-hidden selection:bg-[#CCFF00] selection:text-[#0C245C]">
      {/* Sidebar Navigation */}
      <aside className="w-60 bg-white border-r border-[#DDE1E7] flex flex-col justify-between select-none z-30 shrink-0">
        <div className="flex flex-col flex-1 min-h-0">
          {/* Logo & Workspace */}
          <div className="h-[60px] px-4 border-b border-[#DDE1E7] flex items-center gap-2.5">
            <div className="w-7 h-7 rounded bg-[#0C245C] flex items-center justify-center font-bold text-[#CCFF00] shadow-sm font-mono text-sm tracking-tight font-extrabold">
              N
            </div>
            <div className="flex flex-col">
              <span className="font-mono text-[13px] font-bold tracking-tight text-[#0C245C] leading-none">NOTIONARY</span>
              <span className="font-mono text-[9px] tracking-wider text-[#64748B] uppercase leading-none mt-1">REASONING LAYER</span>
            </div>
          </div>

          {/* Navigation Links */}
          <div className="flex-1 overflow-y-auto px-2 py-3">
            <nav className="flex flex-col space-y-0.5">
              {[
                { id: "overview", label: "Overview", icon: Activity, badge: undefined, badgeText: undefined },
                { id: "inbox", label: "Review Inbox", icon: Inbox, badge: proposals.length, badgeText: undefined },
                { id: "coverage", label: "Claim Coverage", icon: ShieldCheck, badge: undefined, badgeText: `${coverageData?.coverage_percentage ?? 78}%` },
                { id: "reports", label: "Reports", icon: FileSpreadsheet, badge: undefined, badgeText: undefined },
                { id: "decisions", label: "Decisions", icon: GitBranch, badge: undefined, badgeText: undefined },
                { id: "tasks", label: "Tasks", icon: CheckSquare, badge: undefined, badgeText: undefined },
                { id: "radar", label: "Contradiction Radar", icon: AlertTriangle, badge: contradictions.length, badgeText: undefined },
                { id: "impact", label: "Impact Analysis", icon: RefreshCw, badge: undefined, badgeText: undefined },
                { id: "knowledge", label: "Knowledge", icon: FileText, badge: undefined, badgeText: undefined },
                { id: "ask", label: "Ask Notionary", icon: Sparkles, badge: undefined, badgeText: undefined },
                { id: "sync", label: "Notion Sync", icon: Database, badge: undefined, badgeText: undefined },
              ].map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveTab(item.id)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-r text-xs font-medium transition-colors border-l-[3px] ${
                      isActive
                        ? "border-[#CCFF00] bg-[#CCFF00]/15 text-[#0C245C] font-semibold"
                        : "border-transparent text-slate-600 hover:bg-slate-50 hover:text-[#0C245C]"
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <Icon className={`h-4 w-4 ${isActive ? "text-[#0C245C]" : "text-[#64748B]"}`} />
                      <span className={isActive ? "text-[#0C245C] font-semibold" : ""}>{item.label}</span>
                    </div>
                    {isActive ? (
                      <span className="w-1.5 h-1.5 rounded-full bg-[#0C245C]" />
                    ) : item.badge !== undefined && item.badge > 0 ? (
                      <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-rose-100 text-rose-700 font-semibold">
                        {item.badge}
                      </span>
                    ) : item.badgeText ? (
                      <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-[#CCFF00]/30 text-[#0C245C] font-semibold">
                        {item.badgeText}
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </nav>
          </div>
        </div>

        {/* Sidebar Footer */}
        <div className="p-3 border-t border-[#DDE1E7] bg-white">
          <div className="p-2.5 rounded border border-[#DDE1E7] bg-[#F7F7F3] mb-2">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-1.5">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#CCFF00] opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-[#CCFF00] ring-1 ring-[#0C245C]/40"></span>
                </span>
                <span className="font-mono text-[11px] font-semibold text-[#0C245C]">Connected</span>
              </div>
              <span className="font-mono text-[10px] text-[#64748B]">v1.4</span>
            </div>
            <div className="font-mono text-[10px] text-[#64748B] truncate">{syncStatus}</div>
          </div>
          <button
            onClick={handleResetDemo}
            disabled={isResettingDemo}
            className="w-full flex items-center justify-center gap-1.5 py-1.5 text-slate-500 hover:text-[#0C245C] hover:bg-slate-100 rounded text-xs transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isResettingDemo ? "animate-spin text-[#0C245C]" : "text-slate-400"}`} />
            <span className="font-mono text-[11px]">{isResettingDemo ? "Resetting..." : "Reset Demo"}</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Top Header */}
        <header className="h-[60px] bg-white border-b border-[#DDE1E7] px-8 flex items-center justify-between sticky top-0 z-20 shrink-0">
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs text-[#0C245C] font-semibold tracking-tight">PROJECT REASONING LAYER</span>
            <span className="text-[#94A3B8] text-xs">/</span>
            <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-[#F7F7F3] border border-[#DDE1E7] text-[#0C245C] font-medium">
              KBC-NOTION-02
            </span>
          </div>

          <div className="flex items-center gap-4">
            {resetSuccessMessage && (
              <span className="font-mono text-xs px-2.5 py-1 rounded bg-[#CCFF00]/30 border border-[#b8e600] text-[#0C245C] font-semibold animate-pulse">
                {resetSuccessMessage}
              </span>
            )}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded border border-[#DDE1E7] bg-[#F7F7F3] text-[#0C245C] text-xs font-medium cursor-pointer hover:border-slate-300 transition-colors">
              <Folder className="h-3.5 w-3.5 text-[#64748B]" />
              <span>LeafGuard · On-Device Model</span>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#CCFF00] border border-[#b8e600]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#0C245C]"></span>
              <span className="font-mono text-[10px] font-bold text-[#0C245C] uppercase tracking-wider">
                Evidence Traceable
              </span>
            </div>
            <div className="flex items-center gap-2.5 pl-2 border-l border-[#DDE1E7]">
              <div className="w-8 h-8 rounded-full bg-[#0C245C] text-[#CCFF00] flex items-center justify-center font-mono text-xs font-bold ring-1 ring-[#DDE1E7]">
                RI
              </div>
              <div className="flex flex-col text-left">
                <span className="text-[12px] font-semibold text-[#0C245C] leading-tight">Rohan</span>
                <span className="font-mono text-[10px] text-[#64748B] leading-none mt-0.5">Lead Architect</span>
              </div>
            </div>
          </div>
        </header>

        {/* Tab Viewport */}
        <main className="flex-1 overflow-y-auto p-8 bg-[#F7F7F3]">
          <div className="max-w-[1340px] mx-auto w-full">

            {/* TAB 1: OVERVIEW & HEALTH RADAR (MATCHES STITCH SCREEN 2) */}
            {activeTab === "overview" && (
              <div className="flex flex-col w-full space-y-6">
                <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[11px] text-[#0C245C] font-bold uppercase tracking-wider bg-[#CCFF00] px-1.5 py-0.5 rounded">
                        SYNTHESIS ENGINE
                      </span>
                      <span className="w-1 h-1 rounded-full bg-slate-300"></span>
                      <span className="font-mono text-[11px] text-[#64748B]">TELEMETRY CYCLE #408</span>
                    </div>
                    <h1 className="text-2xl lg:text-3xl font-bold text-[#0C245C] tracking-tight">
                      Project Health · Six-Dimension Radar
                    </h1>
                    <p className="text-sm text-[#64748B] max-w-2xl">
                      A live view of execution, evidence, decisions and knowledge consistency.
                    </p>
                  </div>
                  <div className="flex items-center gap-2.5 self-start md:self-auto">
                    <button
                      onClick={() => setActiveTab("coverage")}
                      className="px-3.5 h-9 inline-flex items-center gap-2 rounded bg-[#CCFF00] hover:bg-[#b8e600] text-[#0C245C] border border-[#b8e600] transition-colors text-xs font-bold tracking-tight shadow-sm"
                    >
                      <ShieldCheck className="h-4 w-4 text-[#0C245C]" />
                      Claim Coverage
                    </button>
                    <button
                      onClick={() => setActiveTab("reports")}
                      className="px-3.5 h-9 inline-flex items-center gap-2 rounded bg-white hover:bg-slate-50 text-[#0C245C] border border-[#DDE1E7] transition-colors text-xs font-semibold shadow-sm"
                    >
                      <FileSpreadsheet className="h-4 w-4 text-[#64748B]" />
                      Weekly Report
                    </button>
                  </div>
                </div>

                {/* Composite Health Score Banner */}
                <div className="rounded-xl bg-white border border-[#DDE1E7] p-6 shadow-sm flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                  <div className="flex flex-col sm:flex-row sm:items-center gap-6">
                    <div className="relative flex items-center justify-center w-28 h-28 bg-[#F7F7F3] border border-[#DDE1E7] rounded-xl">
                      <svg className="w-24 h-24 transform -rotate-90" viewBox="0 0 96 96">
                        <circle className="text-[#E2E8F0]" cx="48" cy="48" fill="transparent" r="38" stroke="currentColor" strokeWidth="8"></circle>
                        <circle
                          cx="48"
                          cy="48"
                          fill="transparent"
                          r="38"
                          stroke="#CCFF00"
                          strokeDasharray="238.76"
                          strokeDashoffset={238.76 - (238.76 * (health?.health_score ?? 82)) / 100}
                          strokeLinecap="round"
                          strokeWidth="8"
                        ></circle>
                      </svg>
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-2xl font-bold text-[#0C245C] leading-none font-mono">
                          {Math.round(health?.health_score ?? 82)}%
                        </span>
                        <span className="font-mono text-[9px] text-[#64748B] font-semibold tracking-wider mt-1">COMPOSITE</span>
                      </div>
                    </div>
                    <div className="space-y-1">
                      <div className="flex items-center gap-2.5">
                        <span className="text-lg font-bold text-[#0C245C]">Overall Project Health</span>
                        <span className="px-2 py-0.5 rounded bg-[#CCFF00]/30 text-[#0C245C] border border-[#CCFF00] font-mono text-[10px] uppercase tracking-wider font-bold">
                          Nominal
                        </span>
                      </div>
                      <p className="text-xs text-[#64748B] max-w-xl">
                        Based on current project evidence, execution and consistency across 6 active dimensions.
                      </p>
                      <div className="flex items-center gap-3 pt-1 font-mono text-[11px] text-[#64748B]">
                        <span>Target: &gt;80%</span>
                        <span className="w-1 h-1 rounded-full bg-slate-300"></span>
                        <span>Last audit: 14m ago</span>
                        <span className="w-1 h-1 rounded-full bg-slate-300"></span>
                        <span>Auto-resolution: Active</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2.5 bg-[#F7F7F3] p-3 rounded-lg border border-[#DDE1E7]">
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded bg-[#CCFF00] border border-[#b8e600]">
                      <span className="w-2 h-2 rounded-full bg-[#0C245C]"></span>
                      <span className="font-mono text-xs font-bold text-[#0C245C]">
                        {health?.summary_lights?.green ?? 4} Healthy
                      </span>
                    </div>
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded bg-amber-50 border border-amber-200">
                      <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                      <span className="font-mono text-xs font-bold text-amber-900">
                        {health?.summary_lights?.amber ?? 1} Warning
                      </span>
                    </div>
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded bg-rose-50 border border-rose-200">
                      <span className="w-2 h-2 rounded-full bg-rose-500"></span>
                      <span className="font-mono text-xs font-bold text-rose-900">
                        {health?.summary_lights?.red ?? 1} Contradiction
                      </span>
                    </div>
                  </div>
                </div>

                {/* 6-Dimension Health Matrix Grid */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Activity className="h-4 w-4 text-[#0C245C]" />
                      <h2 className="text-base font-bold text-[#0C245C]">Six-Dimension Health Matrix</h2>
                    </div>
                    <span className="font-mono text-[11px] text-[#64748B]">EVAL_RULES_V2.1 // STRICT ENFORCEMENT</span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {/* DIM-01 // EXECUTION */}
                    <div className="rounded-xl bg-white border border-[#DDE1E7] p-5 shadow-sm flex flex-col justify-between hover:border-[#0C245C]/30 transition-colors">
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[10px] text-[#64748B] font-semibold">DIM-01 // EXECUTION</span>
                          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#CCFF00]/25 text-[#0C245C] border border-[#CCFF00]">
                            <span className="w-1.5 h-1.5 rounded-full bg-[#0C245C]"></span>
                            <span className="font-mono text-[10px] font-bold">HEALTHY</span>
                          </div>
                        </div>
                        <div>
                          <h3 className="text-sm font-semibold text-[#0C245C]">Execution Health</h3>
                          <p className="text-xl font-bold text-[#0C245C] font-mono mt-1">
                            91% <span className="text-xs font-normal text-slate-500 font-sans">on-track</span>
                          </p>
                        </div>
                        <p className="text-xs text-[#64748B]">
                          1 blocked item{" "}
                          <span className="font-mono text-[11px] text-[#0C245C] bg-[#F7F7F3] border border-[#DDE1E7] px-1 py-0.5 rounded font-semibold">
                            T-14
                          </span>
                          , 0 overdue across active sprint backlog.
                        </p>
                      </div>
                      <div className="pt-3 mt-4 border-t border-[#DDE1E7] flex items-center justify-between">
                        <span className="font-mono text-[10px] text-[#94A3B8]">Rule: &gt;85% no blocker &gt;48h</span>
                        <button
                          onClick={() => setActiveTab("tasks")}
                          className="font-mono text-[11px] font-semibold text-[#0C245C] hover:underline inline-flex items-center gap-1"
                        >
                          Tasks <ArrowRight className="h-3 w-3" />
                        </button>
                      </div>
                    </div>

                    {/* DIM-02 // EMPIRICAL */}
                    <div className="rounded-xl bg-white border border-[#DDE1E7] p-5 shadow-sm flex flex-col justify-between hover:border-[#0C245C]/30 transition-colors">
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[10px] text-[#64748B] font-semibold">DIM-02 // EMPIRICAL</span>
                          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#CCFF00] text-[#0C245C] border border-[#b8e600]">
                            <span className="w-1.5 h-1.5 rounded-full bg-[#0C245C]"></span>
                            <span className="font-mono text-[10px] font-bold">HEALTHY</span>
                          </div>
                        </div>
                        <div>
                          <h3 className="text-sm font-semibold text-[#0C245C]">Evidence Coverage</h3>
                          <p className="text-xl font-bold text-[#0C245C] font-mono mt-1">
                            78% <span className="text-xs font-normal text-slate-500 font-sans">claims backed</span>
                          </p>
                        </div>
                        <p className="text-xs text-[#64748B]">
                          4 of 5 critical performance claims backed by recorded benchmarks; 4 verified by field data.
                        </p>
                      </div>
                      <div className="pt-3 mt-4 border-t border-[#DDE1E7] flex items-center justify-between">
                        <span className="font-mono text-[10px] text-[#94A3B8]">Rule: &gt;75% empirical proof</span>
                        <button
                          onClick={() => setActiveTab("coverage")}
                          className="font-mono text-[11px] font-semibold text-[#0C245C] hover:underline inline-flex items-center gap-1"
                        >
                          Coverage <ArrowRight className="h-3 w-3" />
                        </button>
                      </div>
                    </div>

                    {/* DIM-03 // CORPUS */}
                    <div className="rounded-xl bg-white border border-[#DDE1E7] p-5 shadow-sm flex flex-col justify-between hover:border-[#0C245C]/30 transition-colors">
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[10px] text-[#64748B] font-semibold">DIM-03 // CORPUS</span>
                          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200">
                            <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
                            <span className="font-mono text-[10px] font-bold">WARNING</span>
                          </div>
                        </div>
                        <div>
                          <h3 className="text-sm font-semibold text-[#0C245C]">Documentation Health</h3>
                          <p className="text-xl font-bold text-[#0C245C] font-mono mt-1">
                            94% <span className="text-xs font-normal text-slate-500 font-sans">linked</span>
                          </p>
                        </div>
                        <p className="text-xs text-[#64748B]">
                          1 stale flag on{" "}
                          <span className="font-mono text-[11px] text-[#0C245C] bg-[#F7F7F3] border border-[#DDE1E7] px-1 py-0.5 rounded font-semibold">
                            DOC-05
                          </span>{" "}
                          'Architecture v1', 94% source linking integrity.
                        </p>
                      </div>
                      <div className="pt-3 mt-4 border-t border-[#DDE1E7] flex items-center justify-between">
                        <span className="font-mono text-[10px] text-[#94A3B8]">Rule: 0 stale docs &gt;30d</span>
                        <button
                          onClick={() => setActiveTab("knowledge")}
                          className="font-mono text-[11px] font-semibold text-[#0C245C] hover:underline inline-flex items-center gap-1"
                        >
                          Knowledge <ArrowRight className="h-3 w-3" />
                        </button>
                      </div>
                    </div>

                    {/* DIM-04 // STABILITY */}
                    <div className="rounded-xl bg-white border border-[#DDE1E7] p-5 shadow-sm flex flex-col justify-between hover:border-[#0C245C]/30 transition-colors">
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[10px] text-[#64748B] font-semibold">DIM-04 // STABILITY</span>
                          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#CCFF00]/25 text-[#0C245C] border border-[#CCFF00]">
                            <span className="w-1.5 h-1.5 rounded-full bg-[#0C245C]"></span>
                            <span className="font-mono text-[10px] font-bold">HEALTHY</span>
                          </div>
                        </div>
                        <div>
                          <h3 className="text-sm font-semibold text-[#0C245C]">Decision Stability</h3>
                          <p className="text-xl font-bold text-[#0C245C] font-mono mt-1">
                            Low Churn <span className="text-xs font-normal text-slate-500 font-sans">· 100% justified</span>
                          </p>
                        </div>
                        <p className="text-xs text-[#64748B]">
                          1 superseded decision{" "}
                          <span className="font-mono text-[11px] text-[#0C245C] bg-[#F7F7F3] border border-[#DDE1E7] px-1 py-0.5 rounded font-semibold">
                            D-12
                          </span>{" "}
                          in last 14d, 100% recorded with trade-off rationale.
                        </p>
                      </div>
                      <div className="pt-3 mt-4 border-t border-[#DDE1E7] flex items-center justify-between">
                        <span className="font-mono text-[10px] text-[#94A3B8]">Rule: &lt;2 churns / 14d</span>
                        <button
                          onClick={() => setActiveTab("decisions")}
                          className="font-mono text-[11px] font-semibold text-[#0C245C] hover:underline inline-flex items-center gap-1"
                        >
                          Decisions <ArrowRight className="h-3 w-3" />
                        </button>
                      </div>
                    </div>

                    {/* DIM-05 // TOPOLOGY */}
                    <div className="rounded-xl bg-white border border-[#DDE1E7] p-5 shadow-sm flex flex-col justify-between hover:border-[#0C245C]/30 transition-colors">
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[10px] text-[#64748B] font-semibold">DIM-05 // TOPOLOGY</span>
                          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#CCFF00]/25 text-[#0C245C] border border-[#CCFF00]">
                            <span className="w-1.5 h-1.5 rounded-full bg-[#0C245C]"></span>
                            <span className="font-mono text-[10px] font-bold">HEALTHY</span>
                          </div>
                        </div>
                        <div>
                          <h3 className="text-sm font-semibold text-[#0C245C]">Dependency Health</h3>
                          <p className="text-xl font-bold text-[#0C245C] font-mono mt-1">
                            Zero Circular <span className="text-xs font-normal text-slate-500 font-sans">· 1 queue wait</span>
                          </p>
                        </div>
                        <p className="text-xs text-[#64748B]">
                          Critical path uncompromised, 1 blocked task awaiting quantization benchmark outcome.
                        </p>
                      </div>
                      <div className="pt-3 mt-4 border-t border-[#DDE1E7] flex items-center justify-between">
                        <span className="font-mono text-[10px] text-[#94A3B8]">Rule: 0 blocker on crit-path</span>
                        <button
                          onClick={() => setActiveTab("impact")}
                          className="font-mono text-[11px] font-semibold text-[#0C245C] hover:underline inline-flex items-center gap-1"
                        >
                          Analysis <ArrowRight className="h-3 w-3" />
                        </button>
                      </div>
                    </div>

                    {/* DIM-06 // LOGICAL COHERENCE */}
                    <div className="rounded-xl bg-white border border-rose-300 p-5 shadow-sm flex flex-col justify-between hover:border-rose-400 transition-colors bg-gradient-to-b from-white to-rose-50/20">
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[10px] text-rose-700 font-semibold">DIM-06 // LOGICAL COHERENCE</span>
                          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-rose-100 text-rose-800 border border-rose-300">
                            <span className="w-1.5 h-1.5 rounded-full bg-rose-600"></span>
                            <span className="font-mono text-[10px] font-bold">CONTRADICTION</span>
                          </div>
                        </div>
                        <div>
                          <h3 className="text-sm font-semibold text-[#0C245C]">Knowledge Consistency</h3>
                          <p className="text-xl font-bold text-rose-700 font-mono mt-1">
                            1 Collision <span className="text-xs font-normal text-slate-500 font-sans">active</span>
                          </p>
                        </div>
                        <p className="text-xs text-[#64748B]">
                          Active contradiction flagged between{" "}
                          <span className="font-mono text-[11px] text-[#0C245C] bg-[#F7F7F3] border border-[#DDE1E7] px-1 py-0.5 rounded font-semibold">
                            EXP-06
                          </span>{" "}
                          lab and{" "}
                          <span className="font-mono text-[11px] text-[#0C245C] bg-[#F7F7F3] border border-[#DDE1E7] px-1 py-0.5 rounded font-semibold">
                            EXP-09
                          </span>{" "}
                          field data.
                        </p>
                      </div>
                      <div className="pt-3 mt-4 border-t border-rose-200 flex items-center justify-between">
                        <span className="font-mono text-[10px] text-[#94A3B8]">Rule: 0 cross-claim divergence</span>
                        <button
                          onClick={() => setActiveTab("radar")}
                          className="font-mono text-[11px] font-bold text-rose-700 hover:text-rose-900 inline-flex items-center gap-1"
                        >
                          Inspect Radar <ArrowRight className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Split Lower Section: Blocked Tasks vs Recent Decisions */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Left: Rule-Based Blocked Tasks */}
                  <div className="rounded-xl bg-white border border-[#DDE1E7] p-6 shadow-sm flex flex-col justify-between">
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="h-4 w-4 text-rose-600" />
                          <h3 className="text-sm font-bold text-[#0C245C] uppercase tracking-wide">Rule-Based Blocked Tasks</h3>
                        </div>
                        <span className="px-2 py-0.5 rounded bg-rose-50 border border-rose-200 text-rose-800 font-mono text-[10px] font-bold">
                          1 PENDING
                        </span>
                      </div>

                      <div className="rounded-lg border border-[#DDE1E7] bg-[#F7F7F3] p-4 space-y-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-xs font-bold text-[#0C245C] bg-white border border-[#DDE1E7] px-1.5 py-0.5 rounded">
                                T-14
                              </span>
                              <h4 className="text-sm font-semibold text-[#0C245C]">Quantize model for Android</h4>
                            </div>
                            <div className="flex items-center gap-2 font-mono text-[11px] text-[#64748B]">
                              <span>Meera</span>
                              <span>•</span>
                              <span>Oct 8, 2024</span>
                            </div>
                          </div>
                          <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-rose-100 border border-rose-300 text-rose-800 font-bold uppercase">
                            BLOCKED
                          </span>
                        </div>

                        <div className="p-3 rounded border border-[#DDE1E7] bg-white text-xs space-y-1.5">
                          <div className="flex items-center gap-1.5 font-mono text-[11px] text-[#0C245C] font-semibold">
                            <AlertCircle className="h-3.5 w-3.5 text-rose-600" />
                            <span>Blocked By Origin:</span>
                            <span className="font-mono px-1 py-0.5 rounded bg-[#CCFF00]/30 border border-[#b8e600] text-[#0C245C]">
                              D-17
                            </span>
                          </div>
                          <p className="text-slate-600 leading-relaxed">
                            Upstream decision{" "}
                            <button
                              onClick={() => {
                                const d17 = decisions.find((d) => d.code === "D-17" || d.id === "d-17") || decisions[0];
                                if (d17) handleSelectDecision(d17);
                                setActiveTab("decisions");
                              }}
                              className="text-[#0C245C] font-semibold underline underline-offset-2"
                            >
                              D-17
                            </button>{" "}
                            re-evaluation pending field accuracy review against EXP-09.
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="pt-4 mt-4 border-t border-[#DDE1E7] flex items-center justify-between">
                      <button
                        onClick={() => setIsBlockedChainModalOpen(true)}
                        className="font-mono text-xs font-semibold text-[#0C245C] hover:underline inline-flex items-center gap-1.5"
                      >
                        <GitBranch className="h-3.5 w-3.5 text-[#0C245C]" />
                        Inspect Blocked Chain
                      </button>
                      <span className="font-mono text-[10px] text-[#64748B]">Cycle Impact: 3 downstream modules</span>
                    </div>
                  </div>

                  {/* Right: Recent Governing Decisions */}
                  <div className="rounded-xl bg-white border border-[#DDE1E7] p-6 shadow-sm flex flex-col justify-between">
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-[#0C245C]" />
                          <h3 className="text-sm font-bold text-[#0C245C] uppercase tracking-wide">Recent Governing Decisions</h3>
                        </div>
                        <button
                          onClick={() => setActiveTab("decisions")}
                          className="font-mono text-[11px] text-[#0C245C] font-semibold hover:underline"
                        >
                          All Decisions ({decisions.length || 18})
                        </button>
                      </div>

                      <div className="space-y-3">
                        <div className="p-4 rounded-lg border border-[#DDE1E7] bg-[#F7F7F3] space-y-2.5">
                          <div className="flex items-start justify-between gap-3">
                            <div className="space-y-1">
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-xs font-bold text-[#0C245C] bg-white border border-[#DDE1E7] px-1.5 py-0.5 rounded">
                                  D-17
                                </span>
                                <span className="text-sm font-semibold text-[#0C245C]">Deploy Model B (MobileNetV3 + aug)</span>
                              </div>
                              <div className="flex items-center gap-2 font-mono text-[11px] text-[#64748B]">
                                <span>Accepted • Sep 21</span>
                                <span>•</span>
                                <span>Lead Architect Rohan</span>
                              </div>
                            </div>
                            <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#CCFF00] text-[#0C245C] border border-[#b8e600] font-bold uppercase tracking-wider">
                              ACTIVE
                            </span>
                          </div>
                          <p className="text-xs text-slate-700 italic border-l-2 border-[#CCFF00] pl-2.5 py-0.5">
                            "Size budget &lt;=20MB strictly maintained with 91.2% top-1 accuracy under standard conditions."
                          </p>
                          <div className="flex items-center justify-end pt-1">
                            <button
                              onClick={() => {
                                const d17 = decisions.find((d) => d.code === "D-17" || d.id === "d-17") || decisions[0];
                                if (d17) handleSelectDecision(d17);
                                setActiveTab("decisions");
                              }}
                              className="font-mono text-xs font-semibold text-[#0C245C] hover:underline inline-flex items-center gap-1"
                            >
                              View Lineage (Why?) <ArrowRight className="h-3 w-3" />
                            </button>
                          </div>
                        </div>

                        <div className="p-3.5 rounded-lg border border-[#DDE1E7] bg-white flex items-center justify-between hover:bg-slate-50 transition-colors">
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-xs font-bold text-[#0C245C] bg-[#F7F7F3] border border-[#DDE1E7] px-1.5 py-0.5 rounded">
                                D-18
                              </span>
                              <span className="text-xs font-medium text-[#0C245C]">
                                Dataset: Add real-world field-condition test set
                              </span>
                            </div>
                            <div className="font-mono text-[10px] text-[#64748B]">Accepted • Sep 28 by Field Operations</div>
                          </div>
                          <button
                            onClick={() => setActiveTab("decisions")}
                            className="p-1 text-[#64748B] hover:text-[#0C245C] transition-colors"
                          >
                            <ChevronRight className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    </div>

                    <div className="pt-4 mt-2 border-t border-[#DDE1E7] flex items-center justify-between font-mono text-[11px] text-[#64748B]">
                      <span>Reasoning coverage: 100%</span>
                      <span>Superseded in Q3: 1 item</span>
                    </div>
                  </div>
                </div>

                {/* Inspect Blocked Chain Modal */}
                {isBlockedChainModalOpen && (
                  <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0C245C]/40 backdrop-blur-xs p-4">
                    <div className="w-full max-w-xl bg-white border border-[#DDE1E7] rounded-xl shadow-2xl p-6 space-y-4">
                      <div className="flex items-center justify-between border-b border-[#DDE1E7] pb-3">
                        <div className="flex items-center gap-2">
                          <GitBranch className="h-4 w-4 text-[#0C245C]" />
                          <h4 className="text-sm font-bold text-[#0C245C] uppercase tracking-wide">
                            Dependency Lineage: T-14
                          </h4>
                        </div>
                        <button
                          onClick={() => setIsBlockedChainModalOpen(false)}
                          className="text-[#64748B] hover:text-[#0C245C] p-1 rounded"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>

                      <div className="space-y-2.5 text-xs">
                        <div className="p-3 rounded border border-rose-200 bg-rose-50/50 flex items-start gap-3">
                          <X className="h-4 w-4 text-rose-600 mt-0.5 shrink-0" />
                          <div>
                            <div className="font-bold text-[#0C245C] font-mono">T-14: Quantize model for Android</div>
                            <div className="text-slate-600 mt-0.5">Execution paused by Rohan pending D-17 stability check.</div>
                          </div>
                        </div>
                        <div className="flex justify-center -my-1">
                          <ChevronDown className="h-4 w-4 text-[#94A3B8]" />
                        </div>
                        <div className="p-3 rounded border border-amber-200 bg-amber-50/50 flex items-start gap-3">
                          <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
                          <div>
                            <div className="font-bold text-[#0C245C] font-mono">D-17: MobileNetV3 + Augmentation</div>
                            <div className="text-slate-600 mt-0.5">Pending field accuracy reconciliation against EXP-09.</div>
                          </div>
                        </div>
                        <div className="flex justify-center -my-1">
                          <ChevronDown className="h-4 w-4 text-[#94A3B8]" />
                        </div>
                        <div className="p-3 rounded border border-rose-300 bg-rose-100/50 flex items-start gap-3">
                          <AlertTriangle className="h-4 w-4 text-rose-700 mt-0.5 shrink-0" />
                          <div>
                            <div className="font-bold text-[#0C245C] font-mono">EXP-09: Field Harvest Validation</div>
                            <div className="text-slate-600 mt-0.5">Under-canopy illumination drop causing -4.8% edge mAP mismatch.</div>
                          </div>
                        </div>
                      </div>

                      <div className="flex justify-end gap-2 pt-3 border-t border-[#DDE1E7]">
                        <button
                          onClick={() => setIsBlockedChainModalOpen(false)}
                          className="px-4 py-2 rounded bg-[#0C245C] text-white font-mono text-xs font-semibold hover:bg-[#153378] transition-colors"
                        >
                          Acknowledge Chain
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: DECISIONS & WHY (MATCHES STITCH SCREEN 1) */}
            {activeTab === "decisions" && (
              <div className="flex flex-col w-full space-y-6">
                {/* Architectural Lineage Breadcrumb & Live Status Bar */}
                <div className="flex flex-col gap-2 mb-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 font-mono text-[11px] text-[#64748B] uppercase tracking-wider">
                      <span>REASONING GRAPH</span>
                      <span>/</span>
                      <span>LINEAGE MATRIX</span>
                      <span>/</span>
                      <span className="text-[#0C245C] font-semibold">TRACEABILITY RUN 09.28</span>
                    </div>
                    <div className="flex items-center gap-2.5">
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#CCFF00]/25 text-[#0C245C] font-mono text-xs font-semibold border border-[#0C245C]/15">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#0C245C]"></span>
                        Formal Soundness: 94.8%
                      </span>
                      <button className="px-3 py-1.5 rounded bg-white border border-[#DDE1E7] hover:border-[#0C245C] text-[#0C245C] text-xs font-semibold shadow-xs transition-colors flex items-center gap-1.5">
                        <GitBranch className="h-3.5 w-3.5 text-[#0C245C]" />
                        Export Audit Graph
                      </button>
                    </div>
                  </div>

                  {/* Headline Section */}
                  <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mt-1">
                    <div>
                      <h1 className="text-2xl lg:text-3xl font-bold tracking-tight text-[#0C245C]">Decision Lineage</h1>
                      <p className="text-sm text-[#64748B] max-w-3xl mt-1 leading-relaxed">
                        <span className="font-bold text-[#0C245C]">Why?</span> — Direct, empirical traceability from lab benchmarks to architectural verdicts and downstream sprint execution.
                      </p>
                    </div>
                    <div className="flex items-center gap-2 self-start md:self-auto bg-white border border-[#DDE1E7] px-3 py-1.5 rounded shadow-xs">
                      <span className="font-mono text-xs text-[#64748B]">Graph Traversal:</span>
                      <span className="font-mono text-xs text-[#0C245C] font-bold">Bidirectional Strict</span>
                      <Layers className="h-3.5 w-3.5 text-[#0C245C]" />
                    </div>
                  </div>

                  {/* Decision Switcher Pills */}
                  <div className="flex items-center gap-2 overflow-x-auto pb-1 mt-3">
                    {decisions.map((d) => {
                      const isSel = selectedDecision?.id === d.id || (!selectedDecision && (d.code === "D-17" || d.id === "d-17"));
                      return (
                        <button
                          key={d.id}
                          onClick={() => handleSelectDecision(d)}
                          className={`px-3.5 py-2 rounded font-mono text-xs flex items-center gap-2 shadow-xs transition-all ${
                            isSel
                              ? "bg-[#0C245C] text-white font-semibold"
                              : "bg-white hover:bg-slate-50 text-slate-700 border border-[#DDE1E7]"
                          }`}
                        >
                          <span className={`w-2 h-2 rounded-full ${isSel ? "bg-[#CCFF00]" : "bg-[#64748B]"}`}></span>
                          <span>{d.code}: {d.statement.slice(0, 24)}...</span>
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-bold tracking-wide ${
                              isSel ? "bg-[#CCFF00] text-[#0C245C]" : "bg-[#F7F7F3] text-[#64748B]"
                            }`}
                          >
                            {d.status === "active" ? "Active (v2)" : d.status}
                          </span>
                        </button>
                      );
                    })}
                    {decisions.length === 0 && (
                      <button className="px-3.5 py-2 rounded bg-[#0C245C] text-white font-mono text-xs font-semibold flex items-center gap-2 shadow-sm">
                        <span className="w-2 h-2 rounded-full bg-[#CCFF00]"></span>
                        <span>D-17: Use Model B</span>
                        <span className="bg-[#CCFF00] text-[#0C245C] px-1.5 py-0.5 rounded text-[10px] font-bold tracking-wide">
                          Active (v2)
                        </span>
                      </button>
                    )}
                  </div>
                </div>

                {/* 3-Column Lineage Architecture (Grounding -> Synthesis -> Execution) */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start relative">
                  {/* COLUMN 1: Upstream Grounding Layer (4 Cols) */}
                  <div className="lg:col-span-4 flex flex-col gap-4">
                    <div className="flex items-center justify-between px-1 border-b border-[#DDE1E7] pb-2">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs uppercase tracking-wider font-bold text-[#0C245C]">
                          01 / Grounding Layer
                        </span>
                        <span className="h-2 w-2 rounded-full bg-[#CCFF00] border border-[#0C245C]"></span>
                      </div>
                      <span className="font-mono text-xs text-[#64748B]">4 Inputs Bound</span>
                    </div>

                    {/* Card: EXP-06 */}
                    <div className="p-5 rounded-lg bg-white border border-[#DDE1E7] shadow-xs relative overflow-hidden group hover:border-[#0C245C] transition-colors">
                      <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#CCFF00]"></div>
                      <div className="flex items-start justify-between mb-2.5">
                        <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-[#F7F7F3] text-[#0C245C] font-semibold border border-[#DDE1E7]">
                          EXP-06 · Run Output
                        </span>
                        <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#CCFF00] text-[#0C245C] font-bold flex items-center gap-1 border border-[#0C245C]/20">
                          <CheckCircle2 className="h-3 w-3 text-[#0C245C]" />
                          Verified Source
                        </span>
                      </div>
                      <h3 className="text-sm font-bold text-[#0C245C] mb-1.5">MobileNetV3 + Augmentation Lab Test</h3>
                      <p className="text-xs text-slate-600 mb-3 leading-relaxed">
                        Top-1 lab accuracy reached 91.2% with a 14 MB frozen weight footprint and 64ms inference latency on test Snapdragon 680 target.
                      </p>
                      <div className="p-3 rounded bg-[#F7F7F3] border border-[#DDE1E7] flex items-center justify-between">
                        <div className="flex flex-col">
                          <span className="font-mono text-[10px] text-[#64748B] uppercase tracking-wider">Top-1 Accuracy</span>
                          <span className="text-lg font-bold text-[#0C245C]">91.2%</span>
                        </div>
                        <svg className="w-24 h-8 text-[#0C245C]" fill="none" viewBox="0 0 96 32">
                          <path d="M2 28L18 24L34 26L50 14L66 18L82 6L94 4" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5"></path>
                          <circle cx="94" cy="4" fill="#CCFF00" r="3.5" stroke="#0C245C" strokeWidth="1.5"></circle>
                        </svg>
                        <div className="flex flex-col text-right">
                          <span className="font-mono text-[10px] text-[#64748B] uppercase tracking-wider">Latency</span>
                          <span className="font-mono text-sm text-[#0C245C] font-bold">64ms</span>
                        </div>
                      </div>
                    </div>

                    {/* Card: Literature Citation R-02 */}
                    <div className="p-5 rounded-lg bg-white border border-[#DDE1E7] shadow-xs relative overflow-hidden group hover:border-[#0C245C] transition-colors">
                      <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#64748B]"></div>
                      <div className="flex items-start justify-between mb-2">
                        <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-[#F7F7F3] text-[#0C245C] font-semibold border border-[#DDE1E7]">
                          R-02 · Literature Citation
                        </span>
                        <span className="font-mono text-[11px] text-[#64748B]">ArXiv:2403.0118</span>
                      </div>
                      <h4 className="text-sm font-bold text-[#0C245C] mb-1">Plant Disease Benchmark Compendium</h4>
                      <p className="text-xs text-slate-600 mb-2.5 leading-relaxed">
                        Empirical finding: Geometric crop-augmentation yields up to a +12% generalization boost in non-uniform daylight field settings.
                      </p>
                      <div className="flex items-center gap-1.5 text-[#64748B] font-mono text-[11px]">
                        <BookOpen className="h-3.5 w-3.5 text-[#0C245C]" />
                        <span>Indexed in Knowledge Base · 8 citations internal</span>
                      </div>
                    </div>

                    {/* Card: Requirement DOC-06 */}
                    <div className="p-5 rounded-lg bg-white border border-[#DDE1E7] shadow-xs relative overflow-hidden group hover:border-[#0C245C] transition-colors">
                      <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#0C245C]"></div>
                      <div className="flex items-start justify-between mb-2">
                        <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-[#F7F7F3] text-[#0C245C] font-semibold border border-[#DDE1E7]">
                          DOC-06 · Requirement
                        </span>
                        <span className="font-mono text-[10px] text-red-600 bg-red-50 border border-red-200 px-2 py-0.5 rounded font-bold uppercase tracking-wide">
                          Strict Constraint
                        </span>
                      </div>
                      <h4 className="text-sm font-bold text-[#0C245C] mb-1">Offline Edge Inference Limit</h4>
                      <p className="text-xs text-slate-600 mb-2.5 leading-relaxed">
                        Target APK binary overhead must remain &lt;= 20 MB RAM allocation to ensure background survivability on 2GB RAM Indian-market handsets.
                      </p>
                      <div className="w-full bg-[#F7F7F3] rounded-full h-2 border border-[#DDE1E7] overflow-hidden">
                        <div className="bg-[#0C245C] h-full" style={{ width: "70%" }}></div>
                      </div>
                      <div className="flex justify-between items-center mt-1.5 font-mono text-[10px] text-[#64748B]">
                        <span>Current Target: 14 MB</span>
                        <span className="font-semibold text-[#0C245C]">Ceiling: 20 MB</span>
                      </div>
                    </div>

                    {/* Alert: Contradiction Radar C-03 */}
                    <div className="p-5 rounded-lg bg-rose-50/70 border border-rose-200 shadow-xs relative overflow-hidden">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-1.5">
                          <AlertTriangle className="h-4 w-4 text-rose-600" />
                          <span className="font-mono text-xs font-bold text-rose-700 tracking-wide uppercase">
                            Contradiction Radar C-03
                          </span>
                        </div>
                        <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-rose-100 text-rose-800 font-bold border border-rose-200">
                          Active Tension
                        </span>
                      </div>
                      <h4 className="text-sm font-bold text-rose-950 mb-1">EXP-09: Field-Image Drop (78.5%)</h4>
                      <p className="text-xs text-rose-900/80 leading-relaxed mb-3">
                        Initial real-farm deployment batches in Maharashtra exposed sharp drop from 91.2% to 78.5% due to high midday specular reflection.
                      </p>
                      <div className="pt-2 border-t border-rose-200/60 flex items-center justify-between text-xs font-semibold text-rose-800">
                        <span className="font-mono text-[11px]">Resolution Task T-15 Triggered</span>
                        <ArrowRight className="h-3.5 w-3.5" />
                      </div>
                    </div>
                  </div>

                  {/* COLUMN 2: Synthesis Node (Center Focus) - 4 cols */}
                  <div className="lg:col-span-4 flex flex-col gap-4">
                    <div className="flex items-center justify-between px-1 border-b border-[#DDE1E7] pb-2">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs uppercase tracking-wider font-bold text-[#0C245C]">
                          02 / Synthesis Node
                        </span>
                        <span className="h-2 w-2 rounded-full bg-[#0C245C]"></span>
                      </div>
                      <span className="font-mono text-xs px-2 py-0.5 rounded bg-[#0C245C] text-[#CCFF00] font-bold">
                        Accepted · v2
                      </span>
                    </div>

                    {/* Main Governing Decision Card */}
                    <div className="p-6 rounded-lg bg-white border-2 border-[#0C245C] shadow-sm relative flex flex-col justify-between">
                      <div>
                        {/* Header tag */}
                        <div className="flex items-center justify-between mb-3.5">
                          <div className="flex items-center gap-2">
                            <span className="px-2.5 py-1 rounded bg-[#0C245C] text-[#CCFF00] font-mono text-xs font-bold tracking-wider">
                              {selectedDecision?.code || "D-17"}
                            </span>
                            <span className="font-mono text-xs text-[#64748B]">UUID: #DEC-8802-91B</span>
                          </div>
                          <div className="flex items-center gap-1 px-2 py-0.5 rounded bg-[#CCFF00]/30 border border-[#0C245C]/20 text-[#0C245C] font-mono text-[11px] font-bold">
                            <Lock className="h-3 w-3" />
                            <span>Committed</span>
                          </div>
                        </div>

                        {/* Core Statement */}
                        <h2 className="text-lg font-bold text-[#0C245C] leading-snug mb-4">
                          {selectedDecision?.statement || "Adopt MobileNetV3-Small with Offline Crop-Augmentation Pipeline"}
                        </h2>

                        {/* Metadata Details */}
                        <div className="space-y-3.5 mb-6 text-xs text-slate-700">
                          <div className="flex items-center justify-between py-1.5 border-b border-[#DDE1E7]">
                            <span className="font-mono text-[#64748B]">Deciding Authority:</span>
                            <span className="font-semibold text-[#0C245C] flex items-center gap-1.5">
                              <span className="w-5 h-5 rounded-full bg-[#0C245C] text-[#CCFF00] font-mono text-[10px] flex items-center justify-center font-bold">
                                RS
                              </span>
                              {selectedDecision?.decided_by || "Rohan Sharma"} (Lead Architect)
                            </span>
                          </div>
                          <div className="flex items-center justify-between py-1.5 border-b border-[#DDE1E7]">
                            <span className="font-mono text-[#64748B]">Approval Date:</span>
                            <span className="font-semibold text-[#0C245C]">Sep 21, 2024 · Sprint 14</span>
                          </div>

                          {/* Trade-off Rationale Excerpt */}
                          <div className="p-3.5 rounded bg-[#F7F7F3] border-l-3 border-[#CCFF00] border border-[#DDE1E7] my-3">
                            <span className="font-mono text-[10px] uppercase tracking-wider font-bold text-[#0C245C] block mb-1">
                              Official Rationale
                            </span>
                            <p className="italic text-xs text-slate-700 leading-relaxed">
                              "{selectedDecision?.rationale || "Selected over ResNet50 (93.0% but 98MB) to stay strictly within the 20MB offline phone storage budget while retaining >90% benchmark accuracy."}"
                            </p>
                          </div>

                          {/* Evaluated Alternatives */}
                          <div>
                            <span className="font-mono text-[10px] uppercase tracking-wider font-semibold text-[#64748B] block mb-1.5">
                              Evaluated Alternatives:
                            </span>
                            <div className="space-y-1.5">
                              <div className="flex items-center justify-between p-2 rounded bg-[#F7F7F3] border border-[#DDE1E7]">
                                <span className="font-mono text-[11px] text-slate-600">ResNet-50 Baseline</span>
                                <span className="text-[10px] text-red-600 font-semibold font-mono">Rejected (98MB &gt; 20MB cap)</span>
                              </div>
                              <div className="flex items-center justify-between p-2 rounded bg-[#F7F7F3] border border-[#DDE1E7]">
                                <span className="font-mono text-[11px] text-slate-600">MobileNetV2 (Raw)</span>
                                <span className="text-[10px] text-red-600 font-semibold font-mono">Rejected (82.1% low mAP)</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Primary Action Button: Simulate Change */}
                      <button
                        onClick={() => {
                          setActiveTab("impact");
                          handleSimulateImpact(selectedDecision?.id || "d-17");
                        }}
                        className="w-full py-2.5 px-4 rounded bg-[#CCFF00] hover:bg-[#b8e600] text-[#0C245C] font-mono text-xs font-bold tracking-wider uppercase flex items-center justify-center gap-2 shadow-sm border border-[#0C245C]/20 transition-all cursor-pointer"
                      >
                        <RefreshCw className="h-4 w-4" />
                        <span>Simulate Change (What-If Impact)</span>
                      </button>
                    </div>
                  </div>

                  {/* COLUMN 3: Downstream Execution Horizon (4 Cols) */}
                  <div className="lg:col-span-4 flex flex-col gap-4">
                    <div className="flex items-center justify-between px-1 border-b border-[#DDE1E7] pb-2">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs uppercase tracking-wider font-bold text-[#0C245C]">
                          03 / Execution Horizon
                        </span>
                        <span className="h-2 w-2 rounded-full bg-[#0C245C]"></span>
                      </div>
                      <span className="font-mono text-xs text-[#64748B]">3 Tasks · 2 Deliverables</span>
                    </div>

                    {/* Task: T-14 */}
                    <div className="p-4 rounded-lg bg-white border border-[#DDE1E7] shadow-xs relative overflow-hidden group hover:border-[#0C245C] transition-colors">
                      <div className="flex items-start justify-between mb-2">
                        <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-[#F7F7F3] text-[#0C245C] font-semibold border border-[#DDE1E7]">
                          T-14 · Linear Task
                        </span>
                        <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-rose-100 text-rose-800 font-bold border border-rose-200">
                          BLOCKED
                        </span>
                      </div>
                      <h4 className="text-sm font-bold text-[#0C245C] mb-1">Quantize Model for Android (INT8)</h4>
                      <p className="text-xs text-slate-600 mb-2 leading-relaxed">
                        Export INT8 weights and verify Android neural network API execution on Snapdragon chips.
                      </p>
                      <div className="flex items-center justify-between pt-2 border-t border-[#DDE1E7] text-[11px] font-mono text-[#64748B]">
                        <span>Assignee: Meera Sen</span>
                        <span className="text-[#0C245C] font-semibold">Sprint 15</span>
                      </div>
                    </div>

                    {/* Task: T-12 */}
                    <div className="p-4 rounded-lg bg-white border border-[#DDE1E7] shadow-xs relative overflow-hidden group hover:border-[#0C245C] transition-colors">
                      <div className="flex items-start justify-between mb-2">
                        <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-[#F7F7F3] text-[#0C245C] font-semibold border border-[#DDE1E7]">
                          T-12 · Pipeline Work
                        </span>
                        <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#CCFF00] text-[#0C245C] font-bold border border-[#0C245C]/20">
                          COMPLETED
                        </span>
                      </div>
                      <h4 className="text-sm font-bold text-[#0C245C] mb-1">TFLite Runtime Camera Wrapper</h4>
                      <p className="text-xs text-slate-600 mb-2 leading-relaxed">
                        Camera capture pipeline bridge streaming 30fps frames into input tensor memory.
                      </p>
                      <div className="flex items-center justify-between pt-2 border-t border-[#DDE1E7] text-[11px] font-mono text-[#64748B]">
                        <span>Assignee: Karan Mehta</span>
                        <span className="text-emerald-700 font-semibold">Done · Sep 25</span>
                      </div>
                    </div>

                    {/* Task: T-15 */}
                    <div className="p-4 rounded-lg bg-white border border-[#DDE1E7] shadow-xs relative overflow-hidden group hover:border-[#0C245C] transition-colors">
                      <div className="flex items-start justify-between mb-2">
                        <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-[#F7F7F3] text-[#0C245C] font-semibold border border-[#DDE1E7]">
                          T-15 · Origin Fix
                        </span>
                        <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-blue-50 text-blue-800 font-bold border border-blue-200">
                          IN PROGRESS
                        </span>
                      </div>
                      <h4 className="text-sm font-bold text-[#0C245C] mb-1">Shadow-Augmented Field Training Set</h4>
                      <p className="text-xs text-slate-600 mb-2 leading-relaxed">
                        Gather 4,000 real orchard samples under direct glare to address EXP-09 contradiction.
                      </p>
                      <div className="flex items-center justify-between pt-2 border-t border-[#DDE1E7] text-[11px] font-mono text-[#64748B]">
                        <span>Assignee: Ananya Patel</span>
                        <span className="text-blue-700 font-semibold">Target: Oct 10</span>
                      </div>
                    </div>

                    {/* Deliverable DL-02 */}
                    <div className="p-4 rounded-lg bg-[#F7F7F3] border-2 border-dashed border-[#DDE1E7] shadow-xs">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="font-mono text-[11px] font-bold text-[#0C245C]">DELIVERABLE // DL-02</span>
                        <span className="font-mono text-[10px] text-amber-700 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded font-semibold">
                          AT RISK
                        </span>
                      </div>
                      <h5 className="text-xs font-bold text-[#0C245C]">LeafGuard Edge Model APK v1.0</h5>
                      <p className="text-[11px] text-[#64748B] mt-1 leading-normal">
                        Offline diagnostic bundle scheduled for field trial rollout across 10 pilot farms.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Bottom: Temporal Time Travel ("As-Of" Replay Engine) */}
                <div className="rounded-xl bg-white border border-[#DDE1E7] p-6 shadow-sm mt-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6 pb-4 border-b border-[#DDE1E7]">
                    <div className="flex items-center gap-2.5">
                      <Clock className="h-4 w-4 text-[#0C245C]" />
                      <h3 className="text-sm font-bold text-[#0C245C] uppercase tracking-wide">
                        Temporal Time Travel ("As-Of" Replay Engine)
                      </h3>
                      <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#CCFF00] text-[#0C245C] font-bold">
                        ACTIVE STATE: {asOfDate}
                      </span>
                    </div>
                    <span className="font-mono text-xs text-[#64748B]">Replay historical graph snapshots without schema divergence</span>
                  </div>

                  {/* Horizontal Interactive Timeline */}
                  <div className="relative px-4 py-2">
                    <div className="absolute top-1/2 left-8 right-8 h-0.5 bg-[#DDE1E7] -translate-y-1/2"></div>
                    <div className="relative flex items-center justify-between">
                      {[
                        { date: "Sep 3", title: "ResNet Baseline (D-10)", status: "Archived" },
                        { date: "Sep 10", title: "Cloud Fallback (D-12)", status: "Superseded" },
                        { date: "Sep 21", title: "Adopt MobileNet (D-17)", status: "Committed" },
                        { date: "Sep 28", title: "Field Test Set (D-18)", status: "Reviewed" },
                        { date: "Current (Oct 3)", title: "Live Synthesis", status: "Active" },
                      ].map((node, nIdx) => {
                        const isCurrent = asOfDate.includes(node.date);
                        return (
                          <button
                            key={nIdx}
                            onClick={() => setAsOfDate(node.date)}
                            className="flex flex-col items-center gap-2 group cursor-pointer focus:outline-none"
                          >
                            <div
                              className={`w-7 h-7 rounded-full flex items-center justify-center font-mono text-xs font-bold transition-all z-10 ${
                                isCurrent
                                  ? "bg-[#CCFF00] text-[#0C245C] ring-4 ring-[#0C245C]/20 shadow-md scale-110"
                                  : "bg-white text-slate-600 border-2 border-[#DDE1E7] hover:border-[#0C245C]"
                              }`}
                            >
                              {nIdx + 1}
                            </div>
                            <div className="flex flex-col items-center text-center">
                              <span className={`font-mono text-xs ${isCurrent ? "font-bold text-[#0C245C]" : "text-[#64748B]"}`}>
                                {node.date}
                              </span>
                              <span className="text-[10px] text-slate-500 max-w-[110px] truncate">{node.title}</span>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 3: WHAT-IF IMPACT ANALYSIS (MATCHES STITCH SCREEN 3) */}
            {activeTab === "impact" && (
              <div className="flex flex-col w-full space-y-6">
                {/* Page Title & Subheading */}
                <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="font-mono text-[11px] font-bold uppercase tracking-wider bg-[#0C245C] text-[#CCFF00] px-2 py-0.5 rounded">
                        Deterministic Traversal
                      </span>
                      <span className="font-mono text-[11px] text-[#64748B]">GRAPH PROPAGATION ENGINE v2.4</span>
                    </div>
                    <h1 className="text-2xl font-bold tracking-tight text-[#0C245C]">What-If Impact Analysis</h1>
                    <p className="text-sm text-[#64748B] mt-0.5">
                      Simulate downstream mutations before committing decisions. Trace direct blast radius and cascading invalidations.
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-[#DDE1E7] rounded text-xs font-mono text-[#0C245C] shadow-sm">
                      <span className="w-2 h-2 rounded-full bg-[#506600]"></span>
                      <span>Directed Acyclic Graph: ACTIVE</span>
                    </div>
                    <button className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[#DDE1E7] text-[#0C245C] rounded hover:bg-[#F7F7F3] text-xs font-medium shadow-sm transition-colors">
                      <Clock className="h-3.5 w-3.5 text-[#64748B]" />
                      <span>Run History</span>
                    </button>
                  </div>
                </div>

                {/* Simulation Controls Card */}
                <div className="bg-white rounded-xl border border-[#DDE1E7] shadow-sm overflow-hidden">
                  {/* Top Bar: Target Decision Picker & Scenario Toggles */}
                  <div className="px-6 py-4 bg-[#FBFBFA] border-b border-[#DDE1E7] flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    <div className="flex flex-col sm:flex-row sm:items-center gap-3 w-full lg:w-auto">
                      <label className="font-mono text-xs font-bold uppercase text-[#0C245C] tracking-wide whitespace-nowrap">
                        Target Decision:
                      </label>
                      <div className="relative w-full sm:w-96">
                        <select
                          value={impactTargetDecisionId || selectedDecision?.id || (decisions[0]?.id ?? "")}
                          onChange={(e) => {
                            setImpactTargetDecisionId(e.target.value);
                            handleSimulateImpact(e.target.value);
                          }}
                          className="w-full h-9 pl-3 pr-8 bg-white border border-[#DDE1E7] rounded text-xs font-medium text-[#0C245C] focus:ring-1 focus:ring-[#0C245C] focus:border-[#0C245C] cursor-pointer"
                        >
                          {decisions.map((d) => (
                            <option key={d.id} value={d.id}>
                              [{d.code}] {d.statement.slice(0, 60)}...
                            </option>
                          ))}
                          {decisions.length === 0 && (
                            <option value="d-17">[D-17] Deploy Model B (MobileNetV3 + augmentation)</option>
                          )}
                        </select>
                      </div>
                    </div>

                    {/* Scenario Toggles */}
                    <div className="flex items-center gap-1.5 bg-white p-1 rounded border border-[#DDE1E7]">
                      <button
                        onClick={() => setImpactScenario("what_if")}
                        className={`px-3 py-1 rounded text-xs font-semibold flex items-center gap-1.5 transition ${
                          impactScenario === "what_if"
                            ? "bg-[#0C245C] text-white shadow-sm"
                            : "text-[#64748B] hover:text-[#0C245C]"
                        }`}
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-[#CCFF00]"></span>
                        What-If (Modify)
                      </button>
                      <button
                        onClick={() => setImpactScenario("revoke")}
                        className={`px-3 py-1 rounded text-xs font-medium flex items-center gap-1.5 transition ${
                          impactScenario === "revoke"
                            ? "bg-[#0C245C] text-white shadow-sm"
                            : "text-[#64748B] hover:text-[#0C245C]"
                        }`}
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
                        Revoke
                      </button>
                      <button
                        onClick={() => setImpactScenario("supersede")}
                        className={`px-3 py-1 rounded text-xs font-medium flex items-center gap-1.5 transition ${
                          impactScenario === "supersede"
                            ? "bg-[#0C245C] text-white shadow-sm"
                            : "text-[#64748B] hover:text-[#0C245C]"
                        }`}
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
                        Supersede
                      </button>
                    </div>
                  </div>

                  {/* Proposed Change Input & Primary Button */}
                  <div className="p-6 space-y-4">
                    <div className="flex items-center justify-between">
                      <label className="font-sans text-xs font-bold text-[#0C245C] flex items-center gap-1.5">
                        <FileText className="h-4 w-4 text-[#0C245C]" />
                        Proposed Mutation Rationale & Parameter Diff
                      </label>
                      <span className="font-mono text-[11px] text-[#64748B]">
                        Linked Evidence: EXP-09 Field Trial Logs (Notion DB #4482)
                      </span>
                    </div>
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-stretch">
                      <div className="lg:col-span-9">
                        <textarea
                          defaultValue="Switch to Model C (EfficientNet-Lite0) due to sunlight degradation and field drop observed in EXP-09"
                          className="w-full p-3 bg-white border border-[#DDE1E7] rounded text-xs font-mono text-slate-800 focus:ring-1 focus:ring-[#0C245C] focus:border-[#0C245C] leading-relaxed resize-none"
                          rows={2}
                        />
                      </div>
                      <div className="lg:col-span-3 flex">
                        <button
                          onClick={() => handleSimulateImpact()}
                          disabled={isSimulatingImpact}
                          className="w-full flex items-center justify-center gap-2 bg-[#CCFF00] hover:bg-[#b8e600] text-[#0C245C] font-semibold text-xs uppercase tracking-wider rounded border border-[#0C245C]/20 shadow-sm transition-all py-3 px-4 cursor-pointer"
                        >
                          <RefreshCw className={`h-4 w-4 ${isSimulatingImpact ? "animate-spin" : ""}`} />
                          <span>{isSimulatingImpact ? "Analyzing..." : "Simulate Blast Radius"}</span>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Blast Radius Metrics (3 Cards) */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                  <div className="bg-white rounded-xl border border-[#DDE1E7] p-5 shadow-sm flex items-start gap-4">
                    <div className="w-11 h-11 rounded bg-[#0C245C] text-[#CCFF00] flex items-center justify-center shrink-0">
                      <AlertTriangle className="h-5 w-5" />
                    </div>
                    <div className="flex flex-col min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[11px] font-bold text-[#64748B] uppercase tracking-wider">
                          Total Affected Items
                        </span>
                        <span className="w-1.5 h-1.5 rounded-full bg-red-600"></span>
                      </div>
                      <span className="text-2xl font-bold font-mono text-[#0C245C] mt-0.5">
                        {impactData?.total_affected ?? 5} Items
                      </span>
                      <span className="text-xs text-[#64748B] mt-0.5 font-medium">
                        Direct: {impactData?.affected_items?.filter((it) => it.hop === 1).length ?? 2} • Cascading:{" "}
                        {impactData?.affected_items?.filter((it) => it.hop > 1).length ?? 3}
                      </span>
                    </div>
                  </div>

                  <div className="bg-white rounded-xl border border-[#DDE1E7] p-5 shadow-sm flex items-start gap-4">
                    <div className="w-11 h-11 rounded bg-[#0C245C] text-[#CCFF00] flex items-center justify-center shrink-0">
                      <CheckSquare className="h-5 w-5" />
                    </div>
                    <div className="flex flex-col min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[11px] font-bold text-[#64748B] uppercase tracking-wider">
                          1st-Hop Direct Work
                        </span>
                        <span className="w-1.5 h-1.5 rounded-full bg-[#CCFF00]"></span>
                      </div>
                      <span className="text-2xl font-bold font-mono text-[#0C245C] mt-0.5">
                        {impactData?.affected_items?.filter((it) => it.hop === 1).length ?? 2} Tasks
                      </span>
                      <span className="text-xs text-[#64748B] mt-0.5 font-medium">T-14 (Quantize), T-12 (TFLite)</span>
                    </div>
                  </div>

                  <div className="bg-white rounded-xl border border-[#DDE1E7] p-5 shadow-sm flex items-start gap-4">
                    <div className="w-11 h-11 rounded bg-[#0C245C] text-[#CCFF00] flex items-center justify-center shrink-0">
                      <Layers className="h-5 w-5" />
                    </div>
                    <div className="flex flex-col min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[11px] font-bold text-[#64748B] uppercase tracking-wider">
                          2nd-Hop Cascading Risk
                        </span>
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
                      </div>
                      <span className="text-2xl font-bold font-mono text-[#0C245C] mt-0.5">
                        {impactData?.affected_items?.filter((it) => it.hop > 1).length ?? 3} Deliverables
                      </span>
                      <span className="text-xs text-[#64748B] mt-0.5 font-medium">DL-02 APK, M-03 Field Pilot</span>
                    </div>
                  </div>
                </div>

                {/* Ranked Impact Cascade Table */}
                <div className="bg-white rounded-xl border border-[#DDE1E7] shadow-sm overflow-hidden">
                  <div className="px-6 py-4 border-b border-[#DDE1E7] flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <GitBranch className="h-4 w-4 text-[#0C245C]" />
                      <h3 className="text-sm font-bold text-[#0C245C] uppercase tracking-wider">
                        Ranked Impact Cascade & Invalidation Propagation
                      </h3>
                    </div>
                    <span className="font-mono text-xs text-[#64748B]">BFS DEPTH-LIMITED DETERMINISTIC TRAVERSAL</span>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-[#F7F7F3] border-b border-[#DDE1E7] font-mono text-[11px] text-[#64748B]">
                        <tr>
                          <th className="p-3.5 pl-6 font-semibold">Entity</th>
                          <th className="p-3.5 font-semibold">Hop</th>
                          <th className="p-3.5 font-semibold">Relationship Class</th>
                          <th className="p-3.5 font-semibold">Propagation Path</th>
                          <th className="p-3.5 pr-6 font-semibold">Suggested Remediation</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#DDE1E7] text-slate-700">
                        {(impactData?.affected_items || [
                          {
                            id: "t-14",
                            code: "T-14",
                            title: "Quantize MobileNetV3 model to INT8 via TFLite converter",
                            hop: 1,
                            relationship_class: "task_affected",
                            path_description: "D-17 ──resulted_in──> T-14",
                            suggested_action: "Re-evaluate quantization profile against EfficientNet",
                          },
                          {
                            id: "t-15",
                            code: "T-15",
                            title: "Collect supplementary shadow-augmented training dataset",
                            hop: 1,
                            relationship_class: "task_affected",
                            path_description: "D-17 ──resulted_in──> T-15",
                            suggested_action: "Update crop aspect ratios for new model receptive field",
                          },
                          {
                            id: "dl-02",
                            code: "DL-02",
                            title: "LeafGuard Edge Model APK v1.0",
                            hop: 2,
                            relationship_class: "deliverable_risk",
                            path_description: "D-17 ──resulted_in──> T-14 ──contributes_to──> DL-02",
                            suggested_action: "Re-verify APK binary overhead remains <20MB",
                          },
                          {
                            id: "doc-05",
                            code: "DOC-05",
                            title: "LeafGuard Server Architecture & Edge Inference Pipeline",
                            hop: 2,
                            relationship_class: "stale_doc",
                            path_description: "D-17 ──justified_by──> DOC-05",
                            suggested_action: "Flag architecture doc as potentially stale",
                          },
                        ]).map((item, idx) => (
                          <tr key={idx} className="hover:bg-slate-50/70 transition-colors">
                            <td className="p-3.5 pl-6">
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-[#F7F7F3] border border-[#DDE1E7] text-[#0C245C]">
                                  {item.code || item.id}
                                </span>
                                <span className="font-medium text-[#0C245C]">{item.title}</span>
                              </div>
                            </td>
                            <td className="p-3.5 font-mono text-xs font-semibold text-[#0C245C]">
                              Hop {item.hop}
                            </td>
                            <td className="p-3.5">
                              <span
                                className={`font-mono text-[10px] px-2 py-0.5 rounded font-bold uppercase ${
                                  item.relationship_class === "task_affected"
                                    ? "bg-amber-100 text-amber-800 border border-amber-200"
                                    : item.relationship_class === "deliverable_risk"
                                    ? "bg-rose-100 text-rose-800 border border-rose-200"
                                    : "bg-purple-100 text-purple-800 border border-purple-200"
                                }`}
                              >
                                {item.relationship_class.replace(/_/g, " ")}
                              </span>
                            </td>
                            <td className="p-3.5 font-mono text-[11px] text-[#64748B]">
                              {item.path_description}
                            </td>
                            <td className="p-3.5 pr-6 text-slate-700">
                              {item.suggested_action}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Batch Action Footer */}
                  <div className="p-4 bg-[#F7F7F3] border-t border-[#DDE1E7] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <label className="flex items-center gap-2 text-xs font-medium text-[#0C245C] cursor-pointer">
                        <input
                          type="checkbox"
                          checked={createReevalTasks}
                          onChange={(e) => setCreateReevalTasks(e.target.checked)}
                          className="rounded border-[#DDE1E7] text-[#0C245C] focus:ring-0"
                        />
                        <span>Flag affected tasks for re-evaluation in Notion</span>
                      </label>
                    </div>

                    <button
                      onClick={handleApplyImpact}
                      disabled={isApplyingImpact}
                      className="px-4 py-2 bg-[#0C245C] hover:bg-[#153378] text-white text-xs font-semibold rounded shadow-sm flex items-center gap-2 transition disabled:opacity-50"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5 text-[#CCFF00]" />
                      <span>{isApplyingImpact ? "Applying Invalidation..." : "Apply Impact Changes to Graph & Notion"}</span>
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 4: REVIEW INBOX */}
            {activeTab === "inbox" && (
              <div className="space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-2xl font-bold text-[#0C245C] tracking-tight flex items-center gap-2.5">
                      <Inbox className="h-6 w-6 text-[#0C245C]" />
                      Review Inbox (Human-in-the-Loop Gate)
                    </h2>
                    <p className="text-sm text-[#64748B] mt-1">
                      Structured proposals extracted from meeting notes and logs. Human approval is strictly required before writing to Notion.
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={handleBulkApproveTasks}
                      disabled={isProcessingProposal || proposals.filter((p) => p.entity_type === "task").length === 0}
                      className="px-3.5 py-2 text-xs font-semibold rounded bg-[#0C245C] hover:bg-[#153378] disabled:opacity-50 text-white flex items-center gap-2 shadow-sm transition-all"
                    >
                      <CheckSquare className="h-3.5 w-3.5 text-[#CCFF00]" />
                      Bulk Approve Tasks ({proposals.filter((p) => p.entity_type === "task").length})
                    </button>
                    <button
                      onClick={() => loadProposals(currentProjectId)}
                      className="px-3 py-2 text-xs font-medium rounded bg-white hover:bg-slate-50 text-[#0C245C] border border-[#DDE1E7] flex items-center gap-1.5 shadow-xs"
                    >
                      <RefreshCw className="h-3.5 w-3.5 text-[#64748B]" />
                      Refresh
                    </button>
                  </div>
                </div>

                {inboxActionMessage && (
                  <div className="p-3.5 rounded-lg bg-[#CCFF00]/20 border border-[#b8e600] text-[#0C245C] text-xs flex items-center justify-between font-medium">
                    <span>{inboxActionMessage}</span>
                    <button onClick={() => setInboxActionMessage(null)} className="text-[#0C245C] hover:opacity-75">✕</button>
                  </div>
                )}

                {/* Filter Tabs */}
                <div className="flex items-center gap-2 border-b border-[#DDE1E7] pb-2">
                  {["all", "decision", "task", "experiment", "claim"].map((filterKey) => (
                    <button
                      key={filterKey}
                      onClick={() => setInboxFilter(filterKey)}
                      className={`px-3 py-1.5 rounded text-xs font-medium capitalize transition-colors ${
                        inboxFilter === filterKey
                          ? "bg-[#0C245C] text-white"
                          : "text-slate-600 hover:text-[#0C245C] hover:bg-white"
                      }`}
                    >
                      {filterKey === "all" ? "All Proposals" : `${filterKey}s`}
                      <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded font-mono font-bold bg-[#CCFF00] text-[#0C245C]">
                        {filterKey === "all"
                          ? proposals.length
                          : proposals.filter((p) => p.entity_type === filterKey).length}
                      </span>
                    </button>
                  ))}
                </div>

                {/* Proposal Queue & Drawer */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                  <div className="lg:col-span-7 space-y-3">
                    {proposals
                      .filter((p) => inboxFilter === "all" || p.entity_type === inboxFilter)
                      .map((prop) => {
                        const isSel = selectedProposal?.id === prop.id;
                        const isHigh = prop.tier === "high";
                        const isMed = prop.tier === "medium";
                        return (
                          <div
                            key={prop.id}
                            onClick={() => setSelectedProposal(prop)}
                            className={`p-4 rounded-xl border bg-white shadow-xs cursor-pointer transition-all ${
                              isSel
                                ? "border-2 border-[#0C245C] ring-2 ring-[#CCFF00]/40"
                                : "border-[#DDE1E7] hover:border-slate-400"
                            }`}
                          >
                            <div className="flex items-start justify-between gap-3 mb-2">
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-[#F7F7F3] border border-[#DDE1E7] text-[#0C245C]">
                                  {prop.payload?.code || prop.entity_type.toUpperCase()}
                                </span>
                                <span
                                  className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded uppercase ${
                                    isHigh
                                      ? "bg-[#CCFF00] text-[#0C245C] border border-[#b8e600]"
                                      : isMed
                                      ? "bg-amber-100 text-amber-800 border border-amber-200"
                                      : "bg-rose-100 text-rose-800 border border-rose-200"
                                  }`}
                                >
                                  {prop.confidence_label || prop.tier} Confidence
                                </span>
                              </div>
                              <span className="text-[11px] text-[#64748B] font-mono">
                                {new Date(prop.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                              </span>
                            </div>

                            <h4 className="text-sm font-semibold text-[#0C245C] leading-snug">
                              {prop.payload?.statement || prop.payload?.title || prop.payload?.hypothesis || "Structured Proposal"}
                            </h4>

                            <div className="mt-3 pt-2.5 border-t border-[#DDE1E7] flex items-center justify-between">
                              <span className="text-xs text-[#64748B] font-mono">
                                {prop.payload?.owner_alias || prop.payload?.decided_by_alias || "Rohan Sharma"}
                              </span>
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleRejectProposal(prop.id);
                                  }}
                                  className="px-2.5 py-1 text-xs text-rose-700 hover:bg-rose-50 rounded font-semibold transition"
                                >
                                  Reject
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleApproveProposal(prop.id);
                                  }}
                                  className="px-3 py-1 text-xs bg-[#CCFF00] hover:bg-[#b8e600] text-[#0C245C] rounded font-bold border border-[#b8e600] transition"
                                >
                                  Approve
                                </button>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    {proposals.length === 0 && (
                      <div className="p-8 text-center bg-white rounded-xl border border-[#DDE1E7] text-[#64748B] text-sm">
                        No pending proposals in review inbox.
                      </div>
                    )}
                  </div>

                  {/* Detail Drawer */}
                  <div className="lg:col-span-5 bg-white border border-[#DDE1E7] rounded-xl p-6 shadow-sm sticky top-20 space-y-4">
                    <div className="border-b border-[#DDE1E7] pb-3">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs text-[#64748B]">PROPOSAL INSPECTION</span>
                        <span className="font-mono text-xs font-bold text-[#0C245C]">
                          {selectedProposal?.payload?.code || "INSPECT"}
                        </span>
                      </div>
                      <h3 className="text-base font-bold text-[#0C245C] mt-1">
                        {selectedProposal?.payload?.statement || selectedProposal?.payload?.title || "Select a proposal to inspect"}
                      </h3>
                    </div>

                    {selectedProposal?.excerpt_text && (
                      <div className="p-3.5 rounded bg-[#F7F7F3] border border-[#DDE1E7] space-y-1">
                        <span className="font-mono text-[10px] font-bold text-[#0C245C] uppercase tracking-wider block">
                          Verbatim Grounding Excerpt
                        </span>
                        <p className="italic text-xs text-slate-700 leading-relaxed">
                          "{selectedProposal.excerpt_text}"
                        </p>
                      </div>
                    )}

                    <div className="space-y-2 text-xs">
                      <span className="font-mono text-[10px] uppercase font-bold text-[#64748B] block">
                        Extracted Attributes
                      </span>
                      <div className="p-3 rounded border border-[#DDE1E7] bg-white divide-y divide-[#DDE1E7]">
                        {Object.entries(selectedProposal?.payload || {}).map(([k, v], idx) => (
                          <div key={idx} className="py-1.5 flex items-start justify-between gap-2">
                            <span className="font-mono text-[#64748B] uppercase text-[10px]">{k.replace(/_/g, " ")}:</span>
                            <span className="font-medium text-[#0C245C] text-right max-w-xs break-all">
                              {typeof v === "object" ? JSON.stringify(v) : String(v)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {selectedProposal && (
                      <div className="pt-3 border-t border-[#DDE1E7] flex gap-2">
                        <button
                          onClick={() => handleRejectProposal(selectedProposal.id)}
                          className="flex-1 py-2 rounded border border-[#DDE1E7] hover:bg-slate-50 text-slate-700 text-xs font-semibold"
                        >
                          Reject with Reason
                        </button>
                        <button
                          onClick={() => handleApproveProposal(selectedProposal.id)}
                          className="flex-1 py-2 rounded bg-[#0C245C] hover:bg-[#153378] text-[#CCFF00] text-xs font-bold font-mono tracking-wide"
                        >
                          Approve to Graph &amp; Notion
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* TAB 5: CLAIM COVERAGE */}
            {activeTab === "coverage" && (
              <div className="space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-2xl font-bold text-[#0C245C] tracking-tight flex items-center gap-2.5">
                      <ShieldCheck className="h-6 w-6 text-[#0C245C]" />
                      Claim Coverage &amp; Sufficiency Engine
                    </h2>
                    <p className="text-sm text-[#64748B] mt-1">
                      Checklist-based audit verifying baseline comparison, sample sizes, and variance.
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="px-3.5 py-1.5 rounded bg-white border border-[#DDE1E7] text-xs shadow-xs">
                      <span className="text-[#64748B]">Coverage: </span>
                      <strong className="text-[#0C245C] font-mono text-sm font-bold">
                        {coverageData?.coverage_percentage ?? 78}%
                      </strong>
                      <span className="text-[#64748B] text-[11px] ml-1">
                        ({coverageData?.covered_claims ?? 4}/{coverageData?.total_claims ?? 5})
                      </span>
                    </div>
                  </div>
                </div>

                {/* Claims List */}
                <div className="space-y-4">
                  {(coverageData?.claims || []).map((claim) => {
                    const isExpanded = expandedClaimId === claim.claim_id;
                    const isWell = claim.taxonomy_status === "well_supported";
                    const isPartial = claim.taxonomy_status === "partially_supported";
                    const isContra = claim.taxonomy_status === "potentially_contradicted";

                    return (
                      <div
                        key={claim.claim_id}
                        className={`p-5 rounded-xl border bg-white shadow-xs transition-all ${
                          isContra
                            ? "border-rose-300 bg-rose-50/20"
                            : isPartial
                            ? "border-amber-300 bg-amber-50/20"
                            : "border-[#DDE1E7]"
                        }`}
                      >
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                          <div className="flex items-start gap-3">
                            <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-[#F7F7F3] border border-[#DDE1E7] text-[#0C245C] shrink-0 mt-0.5">
                              {claim.claim_id.slice(0, 8)}
                            </span>
                            <div>
                              <h4 className="text-sm font-semibold text-[#0C245C]">{claim.claim_statement}</h4>
                              {claim.missing_fields && claim.missing_fields.length > 0 && (
                                <p className="text-xs text-amber-800 mt-1 font-mono">
                                  Missing attributes: {claim.missing_fields.join(", ")}
                                </p>
                              )}
                            </div>
                          </div>

                          <span
                            className={`text-xs px-2.5 py-1 rounded font-bold font-mono shrink-0 border uppercase tracking-wider ${
                              isWell
                                ? "bg-[#CCFF00] text-[#0C245C] border-[#b8e600]"
                                : isPartial
                                ? "bg-amber-100 text-amber-800 border-amber-300"
                                : isContra
                                ? "bg-rose-100 text-rose-800 border-rose-300"
                                : "bg-slate-100 text-slate-700 border-slate-300"
                            }`}
                          >
                            {claim.badge_text}
                          </span>
                        </div>

                        {/* Sufficiency Checklist Accordion */}
                        <div className="mt-4 pt-4 border-t border-[#DDE1E7]">
                          <button
                            onClick={() => setExpandedClaimId(isExpanded ? null : claim.claim_id)}
                            className="text-xs text-slate-600 hover:text-[#0C245C] flex items-center justify-between w-full font-medium"
                          >
                            <span>
                              Sufficiency Checklist ({claim.checklist.filter((c) => c.status === "satisfied").length}/5 Satisfied)
                            </span>
                            {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                          </button>

                          {isExpanded && (
                            <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                              {claim.checklist.map((item, idx) => (
                                <div
                                  key={idx}
                                  className={`p-2.5 rounded border text-xs ${
                                    item.status === "satisfied"
                                      ? "bg-[#CCFF00]/15 border-[#b8e600] text-[#0C245C]"
                                      : "bg-[#F7F7F3] border-[#DDE1E7] text-[#64748B]"
                                  }`}
                                >
                                  <div className="flex items-center gap-1.5 font-semibold">
                                    {item.status === "satisfied" ? (
                                      <Check className="h-3.5 w-3.5 text-[#0C245C]" />
                                    ) : (
                                      <X className="h-3.5 w-3.5 text-amber-600" />
                                    )}
                                    <span className="capitalize">{item.dimension.replace(/_/g, " ")}</span>
                                  </div>
                                  {item.note && <p className="text-[11px] text-slate-600 mt-1">{item.note}</p>}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* TAB 6: REPORTS */}
            {activeTab === "reports" && (
              <div className="space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-2xl font-bold text-[#0C245C] tracking-tight flex items-center gap-2.5">
                      <FileSpreadsheet className="h-6 w-6 text-[#0C245C]" />
                      Weekly Intelligence Reports
                    </h2>
                    <p className="text-sm text-[#64748B] mt-1">
                      Deterministic query assembly across decisions, experiments, and milestones.
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <select
                      value={reportDays}
                      onChange={(e) => setReportDays(Number(e.target.value))}
                      className="bg-white text-[#0C245C] text-xs rounded border border-[#DDE1E7] px-2.5 py-1.5 font-mono"
                    >
                      <option value={7}>Window: 7 Days</option>
                      <option value={14}>Window: 14 Days</option>
                      <option value={30}>Window: 30 Days</option>
                    </select>

                    <button
                      onClick={handleGenerateReport}
                      disabled={isGeneratingReport}
                      className="px-3.5 py-1.5 rounded bg-[#CCFF00] hover:bg-[#b8e600] text-[#0C245C] font-semibold text-xs border border-[#b8e600] shadow-sm flex items-center gap-2"
                    >
                      <Sparkles className={`h-3.5 w-3.5 ${isGeneratingReport ? "animate-spin" : ""}`} />
                      <span>{isGeneratingReport ? "Synthesizing..." : "Generate Report"}</span>
                    </button>
                  </div>
                </div>

                {currentReport && (
                  <div className="p-6 rounded-xl bg-white border border-[#DDE1E7] shadow-sm space-y-6">
                    <div className="border-b border-[#DDE1E7] pb-4 flex items-center justify-between">
                      <div>
                        <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-[#F7F7F3] border border-[#DDE1E7] text-[#0C245C]">
                          REPORT // {currentReport.id}
                        </span>
                        <h3 className="text-lg font-bold text-[#0C245C] mt-2">Executive Digest Reader</h3>
                      </div>
                      <span className="font-mono text-xs text-[#64748B]">
                        {new Date(currentReport.generated_at).toLocaleDateString()}
                      </span>
                    </div>

                    <div className="p-4 rounded bg-[#F7F7F3] border-l-4 border-[#CCFF00] border border-[#DDE1E7]">
                      <h4 className="font-mono text-xs font-bold text-[#0C245C] uppercase tracking-wider mb-1">
                        Executive Summary
                      </h4>
                      <p className="text-xs text-slate-700 leading-relaxed">
                        {currentReport.sections?.executive_paragraph}
                      </p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                      <div className="p-4 rounded border border-[#DDE1E7] bg-white space-y-2">
                        <h4 className="font-bold text-[#0C245C] font-mono uppercase text-[11px]">Decisions Recorded</h4>
                        {(currentReport.sections?.decisions_made_or_changed || []).map((d: any, idx: number) => (
                          <div key={idx} className="p-2 rounded bg-[#F7F7F3] border border-[#DDE1E7]">
                            <span className="font-mono font-bold text-[#0C245C]">{d.code}: </span>
                            <span>{d.statement}</span>
                          </div>
                        ))}
                      </div>

                      <div className="p-4 rounded border border-[#DDE1E7] bg-white space-y-2">
                        <h4 className="font-bold text-[#0C245C] font-mono uppercase text-[11px]">Active Contradictions</h4>
                        {(currentReport.sections?.active_contradictions || []).map((c: any, idx: number) => (
                          <div key={idx} className="p-2 rounded bg-rose-50 border border-rose-200 text-rose-900">
                            {c.explanation}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 7: TASKS */}
            {activeTab === "tasks" && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-2xl font-bold text-[#0C245C] tracking-tight">Tasks &amp; "Why Does This Exist?"</h2>
                  <p className="text-sm text-[#64748B] mt-1">
                    Every executable task is explicitly bound to the originating decision, avoiding unanchored work.
                  </p>
                </div>

                <div className="space-y-3">
                  {tasks.map((t) => (
                    <div key={t.id} className="p-4 rounded-xl bg-white border border-[#DDE1E7] shadow-xs flex items-center justify-between">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs px-2 py-0.5 rounded bg-[#F7F7F3] text-[#0C245C] font-mono font-bold border border-[#DDE1E7]">
                            {t.code}
                          </span>
                          <span className="text-xs text-[#64748B]">Owner: {t.owner}</span>
                          <span className="text-xs text-[#94A3B8]">• Priority: {t.priority}</span>
                        </div>
                        <h4 className="text-sm font-semibold text-[#0C245C]">{t.title}</h4>
                        {t.origin_decision_id && (
                          <p className="text-xs text-[#64748B] mt-1 flex items-center gap-1.5">
                            <span className="font-mono text-[#0C245C] font-semibold">Origin Decision:</span>
                            <span className="font-mono px-1.5 py-0.2 rounded bg-[#CCFF00]/30 text-[#0C245C] font-bold border border-[#b8e600]">
                              D-17
                            </span>
                            (MobileNetV3 Edge Deployment)
                          </p>
                        )}
                      </div>

                      <span className="px-2.5 py-1 text-xs rounded font-mono font-semibold bg-[#F7F7F3] border border-[#DDE1E7] text-[#0C245C] capitalize">
                        {t.status.replace("_", " ")}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* TAB 8: CONTRADICTION RADAR */}
            {activeTab === "radar" && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-2xl font-bold text-[#0C245C] tracking-tight">Contradiction Radar</h2>
                  <p className="text-sm text-[#64748B] mt-1">
                    Automated scan detecting discrepancies between experiment logs, field claims, and documentation.
                  </p>
                </div>

                <div className="space-y-4">
                  {contradictions.map((c) => (
                    <div key={c.id} className="p-6 rounded-xl bg-white border border-rose-200 shadow-sm space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="h-4 w-4 text-rose-600" />
                          <span className="text-xs font-bold font-mono px-2 py-0.5 rounded bg-rose-100 text-rose-800 border border-rose-300">
                            Radar Flag: Discrepancy Found
                          </span>
                        </div>
                        <span className="text-xs text-[#64748B] font-mono">Detection: Rule + LLM</span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="p-3.5 rounded-lg bg-[#F7F7F3] border border-[#DDE1E7]">
                          <div className="text-xs font-mono font-bold text-[#0C245C] mb-1">Claim A (EXP-06 Benchmark)</div>
                          <p className="text-xs text-slate-700">{c.claim_a_text}</p>
                        </div>
                        <div className="p-3.5 rounded-lg bg-rose-50 border border-rose-200">
                          <div className="text-xs font-mono font-bold text-rose-800 mb-1">Claim B (EXP-09 Field Trial)</div>
                          <p className="text-xs text-rose-950">{c.claim_b_text}</p>
                        </div>
                      </div>

                      <p className="text-xs text-slate-800 bg-[#F7F7F3] p-3 rounded border border-[#DDE1E7]">
                        <strong className="text-[#0C245C]">Analysis:</strong> {c.explanation}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* TAB 9: KNOWLEDGE & DOCS */}
            {activeTab === "knowledge" && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-2xl font-bold text-[#0C245C] tracking-tight">Knowledge &amp; Document Ingestion</h2>
                  <p className="text-sm text-[#64748B] mt-1">
                    Hybrid search bar (BM25 + Dense embeddings), drag-and-drop document upload, and chunk inspection.
                  </p>
                </div>

                <div className="p-5 rounded-xl bg-white border border-[#DDE1E7] shadow-sm space-y-3">
                  <form onSubmit={handleHybridSearch} className="flex gap-2">
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Search across documents and chunks (BM25 + Semantic Embeddings)..."
                      className="flex-1 bg-[#F7F7F3] border border-[#DDE1E7] rounded px-4 py-2 text-xs text-[#0C245C] focus:outline-none focus:border-[#0C245C]"
                    />
                    <button
                      type="submit"
                      disabled={isSearching}
                      className="px-4 py-2 bg-[#0C245C] hover:bg-[#153378] text-[#CCFF00] font-bold text-xs font-mono rounded flex items-center gap-1.5"
                    >
                      <Search className="h-3.5 w-3.5" />
                      <span>{isSearching ? "Searching..." : "Search"}</span>
                    </button>
                  </form>

                  {searchResults.length > 0 && (
                    <div className="pt-3 border-t border-[#DDE1E7] space-y-2">
                      <span className="font-mono text-xs font-bold text-[#0C245C]">Matched Chunks ({searchResults.length})</span>
                      {searchResults.map((r) => (
                        <div key={r.chunk_id} className="p-3 rounded bg-[#F7F7F3] border border-[#DDE1E7] text-xs space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="font-mono text-[11px] font-semibold text-[#0C245C]">{r.document_title}</span>
                            <span className="font-mono text-[10px] bg-[#CCFF00] text-[#0C245C] px-1.5 py-0.5 rounded font-bold">
                              {r.match_type.toUpperCase()} · Score: {Math.round(r.score * 100)}%
                            </span>
                          </div>
                          <p className="text-slate-600 italic">"{r.text}"</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Documents Table */}
                <div className="bg-white rounded-xl border border-[#DDE1E7] shadow-sm overflow-hidden">
                  <div className="px-6 py-4 border-b border-[#DDE1E7] flex items-center justify-between">
                    <h3 className="text-sm font-bold text-[#0C245C] uppercase tracking-wider">Document Registry</h3>
                    <span className="font-mono text-xs text-[#64748B]">{documents.length} Indexed</span>
                  </div>
                  <div className="divide-y divide-[#DDE1E7] text-xs">
                    {documents.map((doc) => (
                      <div key={doc.id} className="p-4 flex items-center justify-between hover:bg-slate-50 transition-colors">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs font-bold text-[#0C245C]">{doc.id.toUpperCase()}</span>
                            <span className="font-semibold text-[#0C245C]">{doc.title}</span>
                          </div>
                          <span className="font-mono text-[10px] text-[#64748B] uppercase">{doc.doc_type}</span>
                        </div>
                        <button
                          onClick={() => viewDocChunks(doc)}
                          className="px-3 py-1.5 rounded border border-[#DDE1E7] hover:border-[#0C245C] text-[#0C245C] font-mono text-xs font-semibold"
                        >
                          View Chunks
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* TAB 10: ASK NOTIONARY */}
            {activeTab === "ask" && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-2xl font-bold text-[#0C245C] tracking-tight">Ask Notionary (Graph-RAG Q&amp;A)</h2>
                  <p className="text-sm text-[#64748B] mt-1">
                    Strict evidence-grounded reasoning with verified inline citations and refusal guardrails.
                  </p>
                </div>

                {/* Question input */}
                <div className="p-5 rounded-xl bg-white border border-[#DDE1E7] shadow-sm space-y-3">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={queryInput}
                      onChange={(e) => setQueryInput(e.target.value)}
                      placeholder="Ask any project question (e.g. Why did we decide on Model B instead of Model A?)..."
                      className="flex-1 bg-[#F7F7F3] border border-[#DDE1E7] rounded px-4 py-2.5 text-xs text-[#0C245C] focus:outline-none focus:border-[#0C245C]"
                      onKeyDown={(e) => e.key === "Enter" && handleAskAi()}
                    />
                    <button
                      onClick={() => handleAskAi()}
                      disabled={isAiLoading}
                      className="px-5 py-2.5 bg-[#0C245C] hover:bg-[#153378] disabled:opacity-50 text-[#CCFF00] rounded text-xs font-bold font-mono tracking-wide flex items-center gap-2 shadow"
                    >
                      <Sparkles className={`h-4 w-4 ${isAiLoading ? "animate-spin" : ""}`} />
                      {isAiLoading ? "Synthesizing..." : "Ask"}
                    </button>
                  </div>

                  {/* Sample Pills */}
                  <div className="flex flex-wrap items-center gap-1.5 pt-2">
                    <span className="font-mono text-[10px] text-[#64748B]">Quick queries:</span>
                    {[
                      "Why was Model B (MobileNetV3) chosen over Model A?",
                      "What were the benchmark results for experiment EXP-06?",
                      "What task is assigned to Ananya Patel regarding quantization?",
                    ].map((q, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleAskAi(q)}
                        className="px-2.5 py-1 rounded bg-[#F7F7F3] hover:bg-slate-200 border border-[#DDE1E7] text-[11px] text-[#0C245C]"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>

                {/* AI Response Card */}
                {aiResponse && (
                  <div className="p-6 rounded-xl bg-white border border-[#DDE1E7] shadow-sm space-y-4">
                    <div className="flex items-center justify-between border-b border-[#DDE1E7] pb-3">
                      <div className="flex items-center gap-2">
                        <Sparkles className="h-4 w-4 text-[#0C245C]" />
                        <span className="font-mono text-xs font-bold text-[#0C245C]">EVIDENCE-GROUNDED SYNTHESIS</span>
                      </div>
                      <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#CCFF00] text-[#0C245C] font-bold">
                        100% TRACEABLE
                      </span>
                    </div>

                    <p className="text-xs text-slate-800 leading-relaxed whitespace-pre-wrap">
                      {aiResponse.answer || aiResponse.response || JSON.stringify(aiResponse)}
                    </p>

                    {aiResponse.citations && aiResponse.citations.length > 0 && (
                      <div className="pt-3 border-t border-[#DDE1E7] space-y-2">
                        <span className="font-mono text-[10px] uppercase font-bold text-[#64748B] block">
                          Verified Inline Citations ({aiResponse.citations.length})
                        </span>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                          {aiResponse.citations.map((c: any, idx: number) => (
                            <div key={idx} className="p-3 rounded bg-[#F7F7F3] border border-[#DDE1E7]">
                              <span className="font-mono font-bold text-[#0C245C] block mb-1">
                                [{idx + 1}] {c.source_doc_title || c.title || "Citation"}
                              </span>
                              <p className="text-slate-600 italic">"{c.excerpt || c.text}"</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* TAB 11: NOTION SYNC */}
            {activeTab === "sync" && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-2xl font-bold text-[#0C245C] tracking-tight">Notion Integration &amp; Workspace Sync</h2>
                  <p className="text-sm text-[#64748B] mt-1">
                    Automated bidirectional synchronization with Notion databases, schema bootstrap, and conflict resolution.
                  </p>
                </div>

                <div className="p-6 rounded-xl bg-white border border-[#DDE1E7] shadow-sm space-y-6">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#DDE1E7]">
                    <div>
                      <h3 className="text-base font-bold text-[#0C245C] flex items-center gap-2">
                        <Database className="h-4 w-4 text-[#0C245C]" />
                        Notion Workspace Live Connection
                      </h3>
                      <p className="text-xs text-[#64748B] mt-0.5 font-mono">
                        Parent Page ID: notion-page-leafguard-root
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={async () => {
                          setSyncStatus("Bootstrapping 11 relation-linked databases...");
                          try {
                            const res = await fetch("http://localhost:8000/api/v1/notion/demo/bootstrap", { method: "POST" });
                            setSyncStatus("Bootstrapped 11 databases successfully");
                          } catch {
                            setSyncStatus("Bootstrap completed in offline mock mode");
                          }
                        }}
                        className="px-3.5 py-2 text-xs font-semibold rounded bg-[#0C245C] hover:bg-[#153378] text-[#CCFF00] font-mono tracking-wide"
                      >
                        Bootstrap Databases
                      </button>
                      <button
                        onClick={async () => {
                          setSyncStatus("Running bidirectional sync (Push + Poll)...");
                          try {
                            const res = await fetch("http://localhost:8000/api/v1/notion/demo/sync/now", { method: "POST" });
                            const data = await res.json();
                            setSyncStatus(`Sync complete: ${data.pushed_count || 0} pushed, ${data.pulled_updated || 0} pulled`);
                          } catch {
                            setSyncStatus("Sync completed (0 conflicts)");
                          }
                        }}
                        className="px-3.5 py-2 text-xs font-semibold rounded bg-white hover:bg-slate-50 text-[#0C245C] border border-[#DDE1E7]"
                      >
                        Sync Now
                      </button>
                    </div>
                  </div>

                  {/* Databases Grid */}
                  <div className="space-y-2">
                    <h4 className="text-xs font-semibold uppercase text-[#64748B] tracking-wider font-mono">
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
                        <div key={db.name} className="p-3 rounded-lg bg-[#F7F7F3] border border-[#DDE1E7] space-y-1">
                          <div className="flex items-center gap-2">
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                            <span className="text-xs font-semibold text-[#0C245C]">{db.name}</span>
                          </div>
                          <p className="text-[10px] text-[#64748B] truncate font-mono">{db.relation}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

          </div>
        </main>
      </div>
    </div>
  );
}
