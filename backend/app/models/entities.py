import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from app.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    notion_parent_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

class Person(Base):
    __tablename__ = "persons"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    aliases = Column(JSON, default=list)  # list of strings
    notion_user_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now)

class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    title = Column(String(255), nullable=False)
    doc_type = Column(String(50), default="note")  # note, paper, chat, meeting, experiment_log
    file_uri = Column(String(500), nullable=True)
    content_text = Column(Text, nullable=True)
    content_hash = Column(String(64), nullable=True)
    notion_page_id = Column(String(255), nullable=True)
    notion_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    title = Column(String(255), nullable=False)
    meeting_date = Column(DateTime, nullable=True)
    attendees = Column(JSON, default=list)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    extraction_status = Column(String(50), default="unextracted")  # unextracted, extracted, reviewed
    notion_page_id = Column(String(255), nullable=True)
    notion_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utc_now)

class Reference(Base):
    __tablename__ = "references"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    title = Column(String(255), nullable=False)
    authors = Column(String(255), nullable=True)
    year = Column(Integer, nullable=True)
    url_or_doi = Column(String(500), nullable=True)
    key_takeaways = Column(Text, nullable=True)
    notion_page_id = Column(String(255), nullable=True)
    notion_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utc_now)

class Claim(Base):
    __tablename__ = "claims"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    statement = Column(Text, nullable=False)
    claim_type = Column(String(50), default="observation")  # observation, comparative, factual, assumption
    subject = Column(String(255), nullable=True)
    metric = Column(String(255), nullable=True)
    direction = Column(String(50), nullable=True)  # increase, decrease, equal, better
    dataset = Column(String(255), nullable=True)
    status = Column(String(50), default="unverified")  # unverified, supported, contradicted
    source_excerpt = Column(Text, nullable=True)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    notion_page_id = Column(String(255), nullable=True)
    notion_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utc_now)

class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    code = Column(String(50), nullable=False)  # e.g., EXP-06
    hypothesis = Column(Text, nullable=True)
    model = Column(String(255), nullable=True)
    dataset = Column(String(255), nullable=True)
    parameters = Column(JSON, default=dict)
    status = Column(String(50), default="completed")  # planned, running, completed, aborted
    owner = Column(String(255), nullable=True)
    run_date = Column(DateTime, nullable=True)
    notion_page_id = Column(String(255), nullable=True)
    notion_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utc_now)

class ExperimentResult(Base):
    __tablename__ = "experiment_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    experiment_id = Column(String(36), ForeignKey("experiments.id"), nullable=False)
    metric = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=True)
    split = Column(String(50), nullable=True)  # test, val, train
    num_runs = Column(Integer, default=1)
    variance = Column(Float, nullable=True)
    source_excerpt = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

class Decision(Base):
    __tablename__ = "decisions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    code = Column(String(50), nullable=False)  # e.g., D-17
    statement = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)
    alternatives = Column(JSON, default=list)  # list of alternatives considered
    status = Column(String(50), default="active")  # active, superseded, rejected, proposed
    decided_on = Column(DateTime, nullable=True)
    decided_by = Column(String(255), nullable=True)
    meeting_id = Column(String(36), ForeignKey("meetings.id"), nullable=True)
    version = Column(Integer, default=1)
    supersedes_id = Column(String(36), nullable=True)
    origin = Column(String(50), default="human_authored")  # human_authored, ai_inferred
    review_status = Column(String(50), default="approved")  # unreviewed, approved, rejected
    notion_page_id = Column(String(255), nullable=True)
    notion_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    code = Column(String(50), nullable=False)  # e.g., T-14
    title = Column(String(255), nullable=False)
    status = Column(String(50), default="todo")  # todo, in_progress, blocked, done
    owner = Column(String(255), nullable=True)
    due_date = Column(DateTime, nullable=True)
    priority = Column(String(50), default="medium")  # low, medium, high, urgent
    origin_decision_id = Column(String(36), ForeignKey("decisions.id"), nullable=True)
    is_blocked = Column(Boolean, default=False)
    blocked_reason = Column(Text, nullable=True)
    notion_page_id = Column(String(255), nullable=True)
    notion_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

class Milestone(Base):
    __tablename__ = "milestones"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    due_date = Column(DateTime, nullable=True)
    progress_percentage = Column(Integer, default=0)
    notion_page_id = Column(String(255), nullable=True)
    notion_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utc_now)

class Deliverable(Base):
    __tablename__ = "deliverables"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    deliverable_type = Column(String(50), default="artifact")
    status = Column(String(50), default="in_progress")
    due_date = Column(DateTime, nullable=True)
    milestone_id = Column(String(36), ForeignKey("milestones.id"), nullable=True)
    notion_page_id = Column(String(255), nullable=True)
    notion_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utc_now)

class Edge(Base):
    __tablename__ = "edges"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    from_type = Column(String(50), nullable=False)  # decision, task, experiment, claim, deliverable
    from_id = Column(String(36), nullable=False)
    to_type = Column(String(50), nullable=False)
    to_id = Column(String(36), nullable=False)
    edge_type = Column(String(50), nullable=False)  # supports, contradicts, resulted_in, depends_on, supersedes
    origin = Column(String(50), default="human_authored")  # human_authored, ai_inferred
    review_status = Column(String(50), default="approved")  # unreviewed, approved, rejected
    rationale_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

class Contradiction(Base):
    __tablename__ = "contradictions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    claim_a_id = Column(String(36), ForeignKey("claims.id"), nullable=False)
    claim_b_id = Column(String(36), ForeignKey("claims.id"), nullable=False)
    detection_method = Column(String(50), default="rule")  # rule, llm, both
    status = Column(String(50), default="open")  # open, confirmed, dismissed, context_differs
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

class ImpactAnalysis(Base):
    __tablename__ = "impact_analyses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    trigger_decision_id = Column(String(36), ForeignKey("decisions.id"), nullable=False)
    scenario = Column(String(50), default="actual")  # actual, what_if
    results = Column(JSON, default=dict)  # affected nodes, paths, explanations
    created_at = Column(DateTime, default=utc_now)
