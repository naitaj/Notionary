import re
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, computed_field

SCHEMA_VERSION = "1.0.0"

# ----------------- Extraction Contracts -----------------

class ExtractedClaim(BaseModel):
    statement: str
    claim_type: str = Field(default="observation", description="observation, comparative, factual, assumption")
    subject: Optional[str] = None
    metric: Optional[str] = None
    direction: Optional[str] = None
    dataset: Optional[str] = None
    condition: Optional[str] = None
    value: Optional[float] = None
    excerpt: str = Field(default="", description="Exact verbatim excerpt from source document")
    char_start: Optional[int] = None
    char_end: Optional[int] = None

    @field_validator("value", mode="before")
    @classmethod
    def normalize_value(cls, v):
        if v is None or v == "":
            return None
        try:
            if isinstance(v, str):
                nums = re.findall(r"[-+]?\d*\.?\d+", v)
                if nums:
                    return float(nums[0])
            return float(v)
        except Exception:
            return None

class ExtractedTask(BaseModel):
    code: Optional[str] = None  # e.g., T-14
    title: str
    owner_alias: Optional[str] = None
    due_date_str: Optional[str] = None
    priority: str = "medium"
    origin_decision_code: Optional[str] = None
    excerpt: str = ""

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, v):
        if not v:
            return "medium"
        return str(v).lower()

class ExtractedExperiment(BaseModel):
    code: str  # e.g., EXP-06
    hypothesis: Optional[str] = None
    model: Optional[str] = None
    dataset: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    owner_alias: Optional[str] = None
    run_date_str: Optional[str] = None
    metric: Optional[str] = None
    metric_value: Optional[float] = None
    metric_unit: Optional[str] = None
    excerpt: str = ""

    @field_validator("parameters", mode="before")
    @classmethod
    def normalize_parameters(cls, v):
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            return {"description": v}
        return {}

    @field_validator("metric_value", mode="before")
    @classmethod
    def normalize_metric_value(cls, v):
        if v is None or v == "":
            return None
        try:
            if isinstance(v, str):
                nums = re.findall(r"[-+]?\d*\.?\d+", v)
                if nums:
                    return float(nums[0])
            return float(v)
        except Exception:
            return None

class ExtractedDecision(BaseModel):
    code: str  # e.g., D-17
    statement: str
    rationale: Optional[str] = None
    alternatives: List[Dict[str, Any]] = Field(default_factory=list)
    decided_by_alias: Optional[str] = None
    decided_date_str: Optional[str] = None
    supersedes_code: Optional[str] = None
    excerpt: str = ""

    @field_validator("alternatives", mode="before")
    @classmethod
    def normalize_alternatives(cls, v):
        if isinstance(v, str):
            return [{"name": v, "reason": ""}]
        if isinstance(v, list):
            res = []
            for item in v:
                if isinstance(item, str):
                    res.append({"name": item, "reason": ""})
                elif isinstance(item, dict):
                    res.append(item)
            return res
        return []

class ExtractionResult(BaseModel):
    schema_version: str = SCHEMA_VERSION
    document_id: str = ""
    doc_type: str = "meeting_note"
    decisions: List[ExtractedDecision] = Field(default_factory=list)
    tasks: List[ExtractedTask] = Field(default_factory=list)
    experiments: List[ExtractedExperiment] = Field(default_factory=list)
    claims: List[ExtractedClaim] = Field(default_factory=list)
    discarded_excerpts_count: int = 0

    @field_validator("decisions", "tasks", "experiments", "claims", mode="before")
    @classmethod
    def normalize_lists(cls, v):
        if v is None:
            return []
        return v

# ----------------- Review Inbox Proposals -----------------

class ProposalPayload(BaseModel):
    id: str
    project_id: str
    entity_type: str  # decision, task, claim, experiment, edge
    tier: str = "medium"  # low, medium, high
    confidence_label: str = "high"  # high, medium, low
    needs_attention: bool = False
    status: str = "pending"  # pending, approved, rejected, merged
    payload: Dict[str, Any]
    excerpt_text: Optional[str] = None
    created_at: datetime

# ----------------- Evidence Graph & Lineage -----------------

class GraphNode(BaseModel):
    id: str
    code: Optional[str] = None
    title: str
    entity_type: str
    status: Optional[str] = None
    origin: str = "human_authored"
    review_status: str = "approved"
    notion_url: Optional[str] = None

class GraphEdgeItem(BaseModel):
    id: str
    from_id: str
    from_type: str
    to_id: str
    to_type: str
    edge_type: str
    origin: str = "human_authored"
    review_status: str = "approved"
    rationale_text: Optional[str] = None

class LineageResponse(BaseModel):
    schema_version: str = SCHEMA_VERSION
    decision_id: str
    decision_code: str
    statement: str
    status: str
    version: int
    upstream_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    downstream_work: List[Dict[str, Any]] = Field(default_factory=list)
    alternatives_considered: List[Dict[str, Any]] = Field(default_factory=list)
    later_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    version_history: List[Dict[str, Any]] = Field(default_factory=list)
    as_of: Optional[str] = None

# ----------------- Cited RAG & Q&A -----------------

class Citation(BaseModel):
    citation_number: int  # e.g., 1 for [1]
    entity_type: str
    entity_id: str
    code_or_title: str
    excerpt: str
    origin: str = "human_authored"  # human_authored, system_derived, ai_inferred
    source_date: Optional[str] = None
    notion_url: Optional[str] = None

    @computed_field
    @property
    def n(self) -> int:
        return self.citation_number

    @computed_field
    @property
    def record(self) -> str:
        return self.code_or_title

class GraphContextNode(BaseModel):
    id: str
    code: Optional[str] = None
    title: str
    entity_type: str
    relationship: str
    hop: int = 1
    is_restricted: bool = False
    origin: str = "human_authored"

class RagQueryRequest(BaseModel):
    project_id: str
    query: str
    as_of: Optional[str] = None

class RagAnswer(BaseModel):
    schema_version: str = SCHEMA_VERSION
    query: str
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    provenance_bar: Dict[str, int] = Field(default_factory=lambda: {"human_authored": 0, "system_derived": 0, "ai_inferred": 0})
    open_contradictions_flagged: List[str] = Field(default_factory=list)
    flags: List[Dict[str, Any]] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    graph_context: List[GraphContextNode] = Field(default_factory=list)
    refusal: bool = False
    refusal_reason: Optional[str] = None

# ----------------- Contradictions & Radar -----------------

class ContradictionClassification(BaseModel):
    schema_version: str = SCHEMA_VERSION
    is_contradiction: bool
    confidence: float
    detection_method: str = "rule"  # rule, llm, both
    metric_delta: Optional[float] = None
    explanation: str
    excerpt_a: str
    excerpt_b: str

# ----------------- Impact Analysis -----------------

class ImpactAffectedItem(BaseModel):
    id: str
    code: Optional[str] = None
    title: str
    entity_type: str
    hop: int
    relationship_class: str  # task_affected, deliverable_risk, review_required, stale_doc, informational
    path_description: str
    status: str
    suggested_action: str
    ai_explanation: Optional[str] = None  # LLM one-sentence explanation (Plan §7.4), labeled "AI suggestion"
    origin: str = "human_authored"

class ClassifiedImpact(BaseModel):
    schema_version: str = SCHEMA_VERSION
    project_id: str
    decision_id: str
    analysis_id: Optional[str] = None
    scenario: str = "actual"  # actual, what_if
    total_affected: int
    summary: str
    affected_items: List[ImpactAffectedItem] = Field(default_factory=list)
    completeness_hints: List[Dict[str, Any]] = Field(default_factory=list)  # Plan §7.3: nodes with zero upstream links

# ----------------- Coverage & Missing Evidence -----------------

class CoverageCheckItem(BaseModel):
    dimension: str
    description: str
    status: str  # satisfied, missing, partial
    details: Optional[str] = None

class CoverageResult(BaseModel):
    schema_version: str = SCHEMA_VERSION
    claim_id: str
    claim_code: Optional[str] = None
    claim_statement: str
    coverage_status: str  # verified, partial, missing_evidence
    taxonomy_status: str = "unsupported"  # well_supported, partially_supported, unsupported, potentially_contradicted, potentially_stale
    badge_text: str = "Evidence incomplete"
    missing_fields: List[str] = Field(default_factory=list)
    checklist: List[CoverageCheckItem] = Field(default_factory=list)
    summary_verdict: str

# ----------------- Project Health (6 Dimensions) -----------------

class HealthDimensionDetail(BaseModel):
    name: str  # execution, evidence_coverage, documentation_health, decision_stability, dependency_health, knowledge_consistency
    label: str
    traffic_light: str  # green, amber, red
    threshold_rule: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    drilldown_items: List[Dict[str, Any]] = Field(default_factory=list)

class ProjectHealthResponse(BaseModel):
    schema_version: str = SCHEMA_VERSION
    project_id: str
    dimensions: Dict[str, HealthDimensionDetail] = Field(default_factory=dict)
    summary_lights: Dict[str, int] = Field(default_factory=lambda: {"green": 0, "amber": 0, "red": 0})
    # Backwards-compatible fields for legacy clients
    evidence_coverage: float = 0.0
    blocked_tasks_count: int = 0
    open_contradictions_count: int = 0
    stale_decisions_count: int = 0
    active_decisions_count: int = 0
    experiments_count: int = 0
    health_score: float = 0.0

# ----------------- Experiment Summaries -----------------

class ExperimentSummaryResponse(BaseModel):
    schema_version: str = SCHEMA_VERSION
    experiment_id: str
    code: str
    hypothesis: Optional[str] = None
    model: Optional[str] = None
    status: str
    setup: Dict[str, Any] = Field(default_factory=dict)
    results_table: List[Dict[str, Any]] = Field(default_factory=list)
    comparison_to_baseline: Dict[str, Any] = Field(default_factory=dict)
    linked_decisions: List[Dict[str, Any]] = Field(default_factory=list)
    ai_summary: Optional[str] = None

# ----------------- Blocked Tasks -----------------

class BlockedTaskDerivation(BaseModel):
    task_id: str
    task_code: Optional[str] = None
    title: str
    status: str
    is_blocked: bool
    blocked_reason: Optional[str] = None
    blockage_source: str = "none"  # manual_override, upstream_task, superseded_decision, unapproved_decision, none
    upstream_chain: List[Dict[str, Any]] = Field(default_factory=list)

# ----------------- Weekly Reports -----------------

class ReportSections(BaseModel):
    schema_version: str = SCHEMA_VERSION
    period_start: str
    period_end: str
    executive_paragraph: str = Field(description="Deterministic + AI summary paragraph")
    experiments_completed: List[Dict[str, Any]] = Field(default_factory=list)
    decisions_made_or_changed: List[Dict[str, Any]] = Field(default_factory=list)
    tasks_progress_and_blocked: List[Dict[str, Any]] = Field(default_factory=list)
    contradictions_flagged: List[Dict[str, Any]] = Field(default_factory=list)
    stale_artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    missing_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    milestone_risks: List[Dict[str, Any]] = Field(default_factory=list)
    upcoming_work: List[Dict[str, Any]] = Field(default_factory=list)

# ----------------- Job & Event Contracts -----------------

class JobCreateRequest(BaseModel):
    project_id: Optional[str] = None
    job_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None

class JobEventResponse(BaseModel):
    id: int
    stage: Optional[str] = None
    message: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    created_at: datetime

class JobResponse(BaseModel):
    id: str
    project_id: Optional[str] = None
    job_type: str
    status: str
    progress: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
