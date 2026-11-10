# JSON shapes for the incident tracker API (requests and responses)
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Severity = Literal["P1", "P2", "P3", "P4"]
Status = Literal["open", "triaged", "mitigated", "resolved"]
Role = Literal["viewer", "analyst", "admin"]
Source = Literal["manual", "github_actions", "alertmanager", "ci_triage", "generic", "scanner"]
# The sources an API key can be issued for: everything except people typing into the UI.
KeySource = Literal["github_actions", "alertmanager", "ci_triage", "generic", "scanner"]


# ---- incidents -------------------------------------------------------------------------------------------------
class IncidentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    severity: Severity = "P3"
    service: str | None = Field(default=None, max_length=100)
    environment: str | None = Field(default=None, max_length=50)
    assignee_id: int | None = None


class IncidentUpdate(BaseModel):
    # Only the fields that are sent are changed. assignee_id: null means "unassign".
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    severity: Severity | None = None
    service: str | None = Field(default=None, max_length=100)
    environment: str | None = Field(default=None, max_length=50)
    assignee_id: int | None = None


class StatusChange(BaseModel):
    status: Status
    note: str | None = Field(default=None, max_length=2000)


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    actor: str
    body: str
    created_at: datetime


class AssigneeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    severity: str
    status: str
    service: str | None
    environment: str | None
    source: str
    external_id: str | None
    occurrences: int
    assignee: AssigneeResponse | None
    sla_due_at: datetime
    breached: bool = False
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class IncidentDetail(IncidentResponse):
    evidence: dict | None
    events: list[EventResponse]


class IncidentList(BaseModel):
    items: list[IncidentResponse]
    total: int
    limit: int
    offset: int


class Stats(BaseModel):
    open_total: int
    open_by_severity: dict[str, int]
    breached: int
    unassigned: int
    mtta_hours: float | None  # mean time to acknowledge, incidents opened in the last 30 days
    mttr_hours: float | None  # mean time to resolve, incidents resolved in the last 30 days


# ---- users, roles, keys, audit ------------------------------------------------------------------------------------
class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: str


class RoleChange(BaseModel):
    role: Role


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    source: KeySource


class ApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    source: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiKeyCreated(ApiKeyResponse):
    key: str  # shown once, when the key is created. Only its hash is stored.


class AuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    actor: str
    actor_type: str
    action: str
    entity_type: str
    entity_id: str | None
    details: dict | None
    ip: str | None


class AuditList(BaseModel):
    items: list[AuditEntry]
    total: int
    limit: int
    offset: int


# ---- machine intake ---------------------------------------------------------------------------------------------
class IntakeResult(BaseModel):
    created: int = 0
    updated: int = 0
    ignored: int = 0
    incident_ids: list[int] = []


class GenericIntake(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    severity: Severity = "P3"
    description: str | None = Field(default=None, max_length=5000)
    service: str | None = Field(default=None, max_length=100)
    environment: str | None = Field(default=None, max_length=50)
    external_id: str | None = Field(default=None, max_length=255)  # same id again = same incident
    evidence: dict | None = None


class _Loose(BaseModel):
    model_config = ConfigDict(extra="ignore")  # GitHub and Alertmanager send many fields we don't use


class WorkflowRun(_Loose):
    id: int
    name: str | None = None
    html_url: str | None = None
    conclusion: str | None = None
    head_branch: str | None = None
    head_sha: str | None = None
    run_attempt: int | None = None
    event: str | None = None


class Repository(_Loose):
    full_name: str
    default_branch: str | None = "main"


class GitHubWorkflowRun(_Loose):
    # The shape of GitHub's `workflow_run` webhook / `github.event` context, so a workflow can post it as-is.
    workflow_run: WorkflowRun
    repository: Repository


class Alert(_Loose):
    status: Literal["firing", "resolved"]
    labels: dict[str, str] = {}
    annotations: dict[str, str] = {}
    startsAt: str | None = None
    endsAt: str | None = None
    generatorURL: str | None = None
    fingerprint: str | None = None


class AlertmanagerWebhook(_Loose):
    alerts: list[Alert] = Field(max_length=100)


class TriageDiagnosis(_Loose):
    # The record ci-triage-agent saves for every diagnosis.
    category: str = Field(max_length=50)
    confidence: str = Field(default="low", max_length=20)
    summary: str = Field(max_length=2000)
    evidence: list[str] = Field(default=[], max_length=20)
    next_step: str = Field(default="", max_length=1000)
    source: str = Field(default="", max_length=20)
    model: str = Field(default="", max_length=100)


class CiTriageReport(_Loose):
    repo: str = Field(max_length=255)
    run_id: int
    run_url: str | None = Field(default=None, max_length=500)
    workflow: str | None = Field(default=None, max_length=255)
    branch: str | None = Field(default=None, max_length=255)
    default_branch: str | None = "main"
    diagnosis: TriageDiagnosis


# ---- findings (DevSecOps scans) ---------------------------------------------------------------------------------------
FindingSeverity = Literal["critical", "high", "medium", "low", "unknown"]
FindingKind = Literal["vulnerability", "secret", "misconfig", "lint"]


class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scanner: str
    kind: str
    target: str
    rule_id: str
    title: str
    description: str | None
    severity: str
    package: str | None
    installed_version: str | None
    fixed_version: str | None
    location: str | None
    url: str | None
    status: str
    status_reason: str | None
    status_by: str | None
    occurrences: int
    incident_id: int | None
    first_seen_at: datetime
    last_seen_at: datetime
    fixed_at: datetime | None


class FindingList(BaseModel):
    items: list[FindingResponse]
    total: int
    limit: int
    offset: int


class FindingStats(BaseModel):
    open_total: int
    open_by_severity: dict[str, int]
    open_by_kind: dict[str, int]
    fixable_open: int  # open vulnerabilities that already have a fixed version
    oldest_open_critical_days: int | None
    last_scan_at: datetime | None


class FindingStatusChange(BaseModel):
    status: Literal["open", "accepted"]
    reason: str | None = Field(default=None, max_length=2000)


class ScanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scanner: str
    target: str
    ref: str | None
    run_url: str | None
    complete: bool
    total: int
    new_count: int
    fixed_count: int
    by_severity: dict
    actor: str
    created_at: datetime


class ScanResult(BaseModel):
    scan_id: int
    total: int
    new: int
    reopened: int
    fixed: int
    unchanged: int
    incident_ids: list[int] = []
