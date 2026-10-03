import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import relationship, declarative_mixin
from app.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

@declarative_mixin
class CommonColumnsMixin:
    """Shared columns per Plan §3.1 for all primary domain entities."""
    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), nullable=False, index=True)
    
    # Notion synchronization tracking
    notion_page_id = Column(String(255), nullable=True, index=True)
    notion_url = Column(String(500), nullable=True)
    sync_status = Column(String(50), default="synced")  # synced, pending, failed, conflict
    last_synced_hash = Column(String(64), nullable=True)
    local_dirty = Column(Boolean, default=False)
    last_synced_notion_edited_time = Column(DateTime, nullable=True)

    # Provenance & Trust badges (Plan §1.1, TRD Part 3)
    origin = Column(String(50), default="human_authored")  # human_authored, system_derived, ai_inferred
    review_status = Column(String(50), default="approved")  # unreviewed, approved, rejected

    # Scoping & Multi-team permissions (Plan §0.3, §4.1)
    visibility = Column(String(50), default="project")  # project, team, private
    visibility_team_id = Column(String(36), nullable=True)

    # Temporal & Versioning (Plan §3.5)
    version = Column(Integer, default=1)
    effective_from = Column(DateTime, default=utc_now)
    effective_to = Column(DateTime, nullable=True)  # NULL indicates active version
    archived = Column(Boolean, default=False)

    created_at = Column(DateTime, default=utc_now)
    created_by = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

# ----------------- Platform & Identity -----------------

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False)
    display_name = Column(String(255), nullable=False)
    avatar_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utc_now)

class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    notion_parent_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

class Team(Base):
    __tablename__ = "teams"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utc_now)

class ProjectMember(Base):
    __tablename__ = "project_members"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    role = Column(String(50), default="member")  # owner, member, reviewer, guest
    team_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=utc_now)

class Person(Base):
    """External/team members mentioned in docs/meetings without full logins (Plan §1.2 Issue 3)."""
    __tablename__ = "people"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    display_name = Column(String(255), nullable=False)
    aliases = Column(JSON, default=list)  # e.g., ["Karan", "karan@leafguard.ai"]
    email = Column(String(255), nullable=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    notion_user_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    def __init__(self, **kwargs):
        if "name" in kwargs and "display_name" not in kwargs:
            kwargs["display_name"] = kwargs.pop("name")
        super().__init__(**kwargs)

    @property
    def name(self):
        return self.display_name

    @name.setter
    def name(self, val):
        self.display_name = val

# ----------------- Auditing, Jobs & LLM Logging -----------------

class AuditLog(Base):
    """Append-only audit log for high-integrity traceability."""
    __tablename__ = "audit_log"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), nullable=False, index=True)
    actor_id = Column(String(255), default="system")
    actor_type = Column(String(50), default="system")  # human, system, ai
    action = Column(String(100), nullable=False)  # approve, reject, sync, infer_edge, update
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(36), nullable=False)
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    prompt_version = Column(String(50), nullable=True)
    model = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utc_now)

class Job(Base):
    """Asynchronous background jobs queue."""
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), nullable=True, index=True)
    job_type = Column(String(100), nullable=False)  # document_ingest, extraction, notion_sync_push, etc.
    payload = Column(JSON, default=dict)
    status = Column(String(50), default="queued")  # queued, running, succeeded, failed
    attempts = Column(Integer, default=0)
    idempotency_key = Column(String(255), nullable=True)
    run_after = Column(DateTime, default=utc_now)
    locked_by = Column(String(255), nullable=True)
    locked_at = Column(DateTime, nullable=True)
    progress = Column(JSON, default=dict)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

class JobEvent(Base):
    """SSE progress event stream for jobs."""
    __tablename__ = "job_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    stage = Column(String(100), nullable=True)
    message = Column(Text, nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now)

class IdempotencyKeyRecord(Base):
    __tablename__ = "idempotency_keys"

    key = Column(String(255), primary_key=True)
    route = Column(String(255), primary_key=True)
    response = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now)

class LLMCall(Base):
    """Log of every LLM and embedding invocation with cache keys."""
    __tablename__ = "llm_calls"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), nullable=True, index=True)
    job_id = Column(String(36), nullable=True)
    purpose = Column(String(100), nullable=False)  # extraction, rag_qa, contradiction_check, impact_phrasing
    model = Column(String(100), nullable=True)
    prompt_version = Column(String(50), nullable=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    cache_key = Column(String(255), unique=True, nullable=True)
    response = Column(JSON, nullable=True)
    status = Column(String(50), default="succeeded")
    created_at = Column(DateTime, default=utc_now)

# ----------------- Ingestion & Documents -----------------

class Document(Base, CommonColumnsMixin):
    __tablename__ = "documents"

    title = Column(String(255), nullable=False)
    doc_type = Column(String(50), default="note")  # meeting_note, paper, experiment_log, design_doc, dataset_card
    file_uri = Column(String(500), nullable=True)
    content_text = Column(Text, nullable=True)
    content_hash = Column(String(64), nullable=True, index=True)
    doc_date = Column(DateTime, nullable=True)
    supersedes_id = Column(String(36), nullable=True)
    pipeline_status = Column(String(50), default="uploaded")  # uploaded, parsing, chunked, extracted, completed, failed

class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    heading_path = Column(String(500), nullable=True)
    char_start = Column(Integer, nullable=False)
    char_end = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)  # vector represented as float array
    created_at = Column(DateTime, default=utc_now)

class Excerpt(Base):
    __tablename__ = "excerpts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    chunk_id = Column(String(36), ForeignKey("chunks.id"), nullable=True)
    char_start = Column(Integer, nullable=False)
    char_end = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now)

# ----------------- Domain Entities -----------------

class Meeting(Base, CommonColumnsMixin):
    __tablename__ = "meetings"

    title = Column(String(255), nullable=False)
    meeting_date = Column(DateTime, nullable=True)
    attendees = Column(JSON, default=list)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    extraction_status = Column(String(50), default="unextracted")

class Reference(Base, CommonColumnsMixin):
    __tablename__ = "references"

    title = Column(String(255), nullable=False)
    authors = Column(String(255), nullable=True)
    year = Column(Integer, nullable=True)
    url_or_doi = Column(String(500), nullable=True)
    key_takeaways = Column(Text, nullable=True)

class Claim(Base, CommonColumnsMixin):
    __tablename__ = "claims"

    statement = Column(Text, nullable=False)
    claim_type = Column(String(50), default="observation")  # observation, comparative, factual, assumption
    subject = Column(String(255), nullable=True)
    metric = Column(String(255), nullable=True)
    direction = Column(String(50), nullable=True)  # increase, decrease, equal, better, worse
    dataset = Column(String(255), nullable=True)
    condition = Column(String(255), nullable=True)
    value = Column(Float, nullable=True)
    coverage_status = Column(String(50), default="unverified")  # unverified, supported, contradicted, incomplete
    source_excerpt_id = Column(String(36), nullable=True)
    source_excerpt = Column(Text, nullable=True)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    embedding = Column(JSON, nullable=True)

    def __init__(self, **kwargs):
        if "status" in kwargs and "coverage_status" not in kwargs:
            kwargs["coverage_status"] = kwargs.pop("status")
        super().__init__(**kwargs)

    @property
    def status(self):
        return self.coverage_status

    @status.setter
    def status(self, val):
        self.coverage_status = val

class Experiment(Base, CommonColumnsMixin):
    __tablename__ = "experiments"

    code = Column(String(50), nullable=False, index=True)  # e.g., EXP-06
    hypothesis = Column(Text, nullable=True)
    model = Column(String(255), nullable=True)
    dataset = Column(String(255), nullable=True)
    parameters = Column(JSON, default=dict)
    status = Column(String(50), default="completed")  # planned, running, completed, aborted
    owner = Column(String(255), nullable=True)
    owner_id = Column(String(36), ForeignKey("people.id"), nullable=True)
    run_date = Column(DateTime, nullable=True)

class ExperimentResult(Base, CommonColumnsMixin):
    __tablename__ = "experiment_results"

    experiment_id = Column(String(36), ForeignKey("experiments.id"), nullable=False, index=True)
    metric = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=True)
    split = Column(String(50), nullable=True)  # test, val, train, field
    num_runs = Column(Integer, default=1)
    variance = Column(Float, nullable=True)
    baseline_ref = Column(String(100), nullable=True)
    excerpt_id = Column(String(36), ForeignKey("excerpts.id"), nullable=True)
    source_excerpt = Column(Text, nullable=True)

class Decision(Base, CommonColumnsMixin):
    __tablename__ = "decisions"

    code = Column(String(50), nullable=False, index=True)  # e.g., D-17
    statement = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)
    alternatives = Column(JSON, default=list)  # list of alternatives considered
    status = Column(String(50), default="active")  # active, proposed, superseded, reverted, modified
    decided_on = Column(DateTime, nullable=True)
    decided_by = Column(String(255), nullable=True)
    decided_by_id = Column(String(36), ForeignKey("people.id"), nullable=True)
    meeting_id = Column(String(36), ForeignKey("meetings.id"), nullable=True)
    supersedes_id = Column(String(36), nullable=True)

class Assumption(Base, CommonColumnsMixin):
    __tablename__ = "assumptions"

    statement = Column(Text, nullable=False)
    status = Column(String(50), default="valid")

class Task(Base, CommonColumnsMixin):
    __tablename__ = "tasks"

    code = Column(String(50), nullable=False, index=True)  # e.g., T-14
    title = Column(String(255), nullable=False)
    status = Column(String(50), default="todo")  # todo, in_progress, blocked, done
    owner = Column(String(255), nullable=True)
    owner_id = Column(String(36), ForeignKey("people.id"), nullable=True)
    due_date = Column(DateTime, nullable=True)
    priority = Column(String(50), default="medium")  # low, medium, high, urgent
    origin_decision_id = Column(String(36), ForeignKey("decisions.id"), nullable=True)
    origin_meeting_id = Column(String(36), ForeignKey("meetings.id"), nullable=True)
    is_blocked = Column(Boolean, default=False)
    blocked_reason = Column(Text, nullable=True)
    needs_reevaluation = Column(Boolean, default=False)  # Plan §1.2 & §3.2

class Milestone(Base, CommonColumnsMixin):
    __tablename__ = "milestones"

    name = Column(String(255), nullable=False)
    due_date = Column(DateTime, nullable=True)
    progress_percentage = Column(Integer, default=0)

class Deliverable(Base, CommonColumnsMixin):
    __tablename__ = "deliverables"

    name = Column(String(255), nullable=False)
    deliverable_type = Column(String(50), default="artifact")
    status = Column(String(50), default="in_progress")
    due_date = Column(DateTime, nullable=True)
    milestone_id = Column(String(36), ForeignKey("milestones.id"), nullable=True)

# ----------------- Typed Graph Edges -----------------

class Edge(Base):
    """Canonical typed graph edge with Plan §1.2 vocabulary."""
    __tablename__ = "edges"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), nullable=False, index=True)
    from_type = Column(String(50), nullable=False)  # decision, task, experiment, claim, deliverable, document, meeting, reference
    from_id = Column(String(36), nullable=False, index=True)
    to_type = Column(String(50), nullable=False)
    to_id = Column(String(36), nullable=False, index=True)
    
    # Vocabulary per Plan §1.2 Issue 4 & §3.3:
    # references, discussed_in, produced, supports, contradicts, resulted_in,
    # depends_on, contributes_to, assigned_to, supersedes, modifies, affects,
    # validates, invalidates, assumes, describes, motivates
    edge_type = Column(String(50), nullable=False)
    
    origin = Column(String(50), default="human_authored")  # human_authored, system_derived, ai_inferred
    review_status = Column(String(50), default="approved")  # unreviewed, approved, rejected
    rationale_text = Column(Text, nullable=True)
    excerpt_id = Column(String(36), ForeignKey("excerpts.id"), nullable=True)
    proposal_id = Column(String(36), nullable=True)

    effective_from = Column(DateTime, default=utc_now)
    effective_to = Column(DateTime, nullable=True)  # NULL indicates currently active edge
    recorded_at = Column(DateTime, default=utc_now)
    created_at = Column(DateTime, default=utc_now)

# ----------------- Review Inbox & Intelligence -----------------

class Proposal(Base):
    """Review Inbox queue for unreviewed AI extractions (Plan §3.2 #25)."""
    __tablename__ = "proposals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)  # decision, task, claim, experiment, edge
    payload = Column(JSON, nullable=False)
    excerpt_id = Column(String(36), ForeignKey("excerpts.id"), nullable=True)
    confidence_label = Column(String(50), default="high")  # high, medium, low
    needs_attention = Column(Boolean, default=False)
    status = Column(String(50), default="pending")  # pending, approved, rejected, merged
    rejection_reason = Column(Text, nullable=True)
    link_target_id = Column(String(36), nullable=True)
    tier = Column(String(50), default="medium")  # low, medium, high
    created_at = Column(DateTime, default=utc_now)

class NotionDatabase(Base):
    __tablename__ = "notion_databases"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)  # decisions, tasks, claims, etc.
    notion_database_id = Column(String(255), nullable=False)
    data_source_id = Column(String(255), nullable=True)
    property_map = Column(JSON, default=dict)
    schema_version = Column(Integer, default=1)
    last_cursor = Column(String(255), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

class NotionConflict(Base):
    __tablename__ = "notion_conflicts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(36), nullable=False)
    notion_page_id = Column(String(255), nullable=True)
    app_snapshot = Column(JSON, nullable=True)
    notion_snapshot = Column(JSON, nullable=True)
    field_diffs = Column(JSON, nullable=True)
    status = Column(String(50), default="open")  # open, resolved
    resolution = Column(JSON, nullable=True)
    resolved_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)

class Contradiction(Base):
    """Polymorphic contradiction detection (Plan §1.2 Issue 6 & §3.3)."""
    __tablename__ = "contradictions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), nullable=False, index=True)
    a_type = Column(String(50), nullable=False, default="claim")  # claim, experiment_result
    a_id = Column(String(36), nullable=False)
    b_type = Column(String(50), nullable=False, default="claim")  # claim, experiment_result
    b_id = Column(String(36), nullable=False)

    def __init__(self, **kwargs):
        if "claim_a_id" in kwargs:
            kwargs["a_id"] = kwargs.pop("claim_a_id")
            kwargs.setdefault("a_type", "claim")
        if "claim_b_id" in kwargs:
            kwargs["b_id"] = kwargs.pop("claim_b_id")
            kwargs.setdefault("b_type", "claim")
        super().__init__(**kwargs)

    # Backwards compatibility accessors
    @property
    def claim_a_id(self):
        return self.a_id

    @claim_a_id.setter
    def claim_a_id(self, val):
        self.a_id = val
        self.a_type = "claim"

    @property
    def claim_b_id(self):
        return self.b_id

    @claim_b_id.setter
    def claim_b_id(self, val):
        self.b_id = val
        self.b_type = "claim"

    excerpt_a_id = Column(String(36), nullable=True)
    excerpt_b_id = Column(String(36), nullable=True)
    detection_method = Column(String(50), default="rule")  # rule, llm, both
    llm_result = Column(JSON, nullable=True)
    status = Column(String(50), default="open")  # open, confirmed, dismissed, context_differs
    explanation = Column(Text, nullable=True)
    reviewer_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utc_now)

class StaleFlag(Base):
    __tablename__ = "stale_flags"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    reasons = Column(JSON, default=list)
    triggering_record_id = Column(String(36), nullable=True)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=utc_now)

class DatasetAlias(Base):
    """Canonical name normalization table (Plan §1.2 Issue 7 & §3.3)."""
    __tablename__ = "dataset_aliases"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), nullable=False, index=True)
    kind = Column(String(50), nullable=False)  # subject, dataset, metric
    canonical = Column(String(255), nullable=False)
    alias = Column(String(255), nullable=False)

class ImpactAnalysis(Base):
    __tablename__ = "impact_analyses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), nullable=False, index=True)
    trigger_decision_id = Column(String(36), ForeignKey("decisions.id"), nullable=False)
    scenario = Column(String(50), default="actual")  # actual, what_if
    results = Column(JSON, default=dict)  # affected nodes, paths, explanations
    actions_taken = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utc_now)

class Report(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), nullable=False, index=True)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    sections = Column(JSON, default=dict)  # structured blocks tagged Source/Derived/AI
    notion_page_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now)

class EvalCase(Base):
    __tablename__ = "eval_cases"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), nullable=False, index=True)
    kind = Column(String(50), default="qa")  # qa, extraction, contradiction, impact
    query = Column(Text, nullable=False)
    expected_answer = Column(Text, nullable=True)
    expected_sources = Column(JSON, default=list)  # list of entity codes e.g. ["D-17", "EXP-06"]
    should_refuse = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)

class EvalRun(Base):
    __tablename__ = "eval_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), nullable=False, index=True)
    eval_type = Column(String(50), default="qa")
    git_sha = Column(String(50), nullable=True)
    prompt_version = Column(String(50), nullable=True)
    model = Column(String(100), nullable=True)
    total_cases = Column(Integer, default=0)
    passed_cases = Column(Integer, default=0)
    hit_at_5 = Column(Float, default=0.0)
    citation_correctness = Column(Float, default=0.0)
    metrics = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utc_now)
