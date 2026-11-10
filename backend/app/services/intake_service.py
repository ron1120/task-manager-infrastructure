# Turning events from machines (GitHub Actions, Alertmanager, ci-triage-agent, anything else) into incidents.
# Every function returns an IntakeResult-shaped dict: how many incidents were created, updated or ignored.
import hashlib
import json

from sqlalchemy.orm import Session

from app.core.actor import Actor
from app.models import ApiKey, Incident
from app.schemas.ops import AlertmanagerWebhook, CiTriageReport, GenericIntake, GitHubWorkflowRun
from app.services import incident_service

FAILED_CONCLUSIONS = {"failure", "timed_out", "startup_failure"}
ALERT_SEVERITY = {"critical": "P1", "high": "P2", "error": "P2", "warning": "P3", "info": "P4", "none": "P4"}
# How bad a CI failure is, by what the triage agent decided it was. Real failures on the default branch matter most.
TRIAGE_SEVERITY = {"real_failure": "P3", "flaky_test": "P4", "infra_failure": "P3", "dependency_env": "P3"}


def _result() -> dict:
    return {"created": 0, "updated": 0, "ignored": 0, "incident_ids": []}


def _note(result: dict, incident: Incident, created: bool) -> None:
    result["created" if created else "updated"] += 1
    result["incident_ids"].append(incident.id)


def report_incident(
    db: Session, actor: Actor, *, source: str, external_id: str | None, ip: str | None, **fields
) -> tuple[Incident, bool]:
    """Create the incident, or, if this source already reported this external_id, count it as a repeat.

    A repeat of a resolved incident reopens it: the thing that was fixed has broken again.
    """
    existing = None
    if external_id:
        existing = (
            db.query(Incident).filter(Incident.source == source, Incident.external_id == external_id).first()
        )
    if existing is None:
        return incident_service.create_incident(
            db, actor, source=source, external_id=external_id, ip=ip, **fields
        ), True

    existing.occurrences += 1
    if existing.status == "resolved":
        incident_service.change_status(
            db, existing, actor, "open", note="Reported again after it was resolved.", ip=ip
        )
    else:
        db.commit()
    db.refresh(existing)
    return existing, False


def github_actions(db: Session, key: ApiKey, payload: GitHubWorkflowRun, ip: str | None) -> dict:
    result = _result()
    run, repo = payload.workflow_run, payload.repository
    if run.conclusion not in FAILED_CONCLUSIONS:
        result["ignored"] += 1  # a passing, skipped or cancelled run is not an incident
        return result
    on_default_branch = run.head_branch == repo.default_branch
    incident, created = report_incident(
        db,
        Actor.api_key(key),
        source="github_actions",
        external_id=f"{repo.full_name}#{run.id}",
        ip=ip,
        title=f"CI failed: {run.name or 'workflow'} on {run.head_branch or 'unknown branch'}",
        severity="P2" if on_default_branch else "P3",
        description=f"Workflow run {run.id} in {repo.full_name} ended with: {run.conclusion}.",
        service=repo.full_name,
        environment="ci",
        evidence={
            "run_url": run.html_url,
            "branch": run.head_branch,
            "head_sha": run.head_sha,
            "event": run.event,
            "run_attempt": run.run_attempt,
            "conclusion": run.conclusion,
        },
    )
    _note(result, incident, created)
    return result


def alertmanager(db: Session, key: ApiKey, payload: AlertmanagerWebhook, ip: str | None) -> dict:
    result = _result()
    actor = Actor.api_key(key)
    for alert in payload.alerts:
        labels, notes = alert.labels, alert.annotations
        # Alertmanager's own fingerprint identifies an alert; fall back to hashing its labels.
        fingerprint = alert.fingerprint or hashlib.sha256(json.dumps(labels, sort_keys=True).encode()).hexdigest()[:16]
        if alert.status == "resolved":
            existing = db.query(Incident).filter(Incident.source == "alertmanager", Incident.external_id == fingerprint).first()
            if existing is None or existing.status not in ("open", "triaged"):
                result["ignored"] += 1
                continue
            # A resolved alert means the symptom stopped. A person still decides when the incident is closed.
            if existing.status == "triaged":
                incident_service.change_status(db, existing, actor, "mitigated", note="Alert resolved in Alertmanager.", ip=ip)
            else:
                # Nobody has looked at it yet, so it cannot skip triage: leave it open and say what happened.
                incident_service.add_comment(
                    db, existing, actor, "Alert resolved in Alertmanager. The incident is still open: it needs triage.", ip
                )
            _note(result, existing, False)
            continue
        incident, created = report_incident(
            db,
            actor,
            source="alertmanager",
            external_id=fingerprint,
            ip=ip,
            title=(notes.get("summary") or labels.get("alertname") or "Alert")[:255],
            severity=ALERT_SEVERITY.get(labels.get("severity", "").lower(), "P3"),
            description=(notes.get("description") or "")[:5000] or None,
            service=(labels.get("service") or labels.get("job") or labels.get("namespace")),
            environment=(labels.get("env") or labels.get("environment") or labels.get("cluster")),
            evidence={
                "labels": labels,
                "annotations": notes,
                "startsAt": alert.startsAt,
                "generatorURL": alert.generatorURL,
            },
        )
        _note(result, incident, created)
    return result


def ci_triage(db: Session, key: ApiKey, payload: CiTriageReport, ip: str | None) -> dict:
    """Attach the triage agent's diagnosis to the incident for that run, or open one if CI intake never saw it."""
    result = _result()
    actor = Actor.api_key(key)
    d = payload.diagnosis
    external_id = f"{payload.repo}#{payload.run_id}"
    diagnosis = d.model_dump()
    summary = f"CI triage ({d.confidence} confidence): {d.category}. {d.summary}"
    if d.next_step:
        summary += f" Next step: {d.next_step}"

    existing = (
        db.query(Incident)
        .filter(Incident.external_id == external_id, Incident.source.in_(("github_actions", "ci_triage")))
        .first()
    )
    if existing is not None:
        existing.evidence = {**(existing.evidence or {}), "diagnosis": diagnosis}
        incident_service.add_comment(db, existing, actor, summary, ip)
        _note(result, existing, False)
        return result

    on_default_branch = payload.branch is not None and payload.branch == payload.default_branch
    severity = TRIAGE_SEVERITY.get(d.category, "P3")
    if d.category == "real_failure" and on_default_branch:
        severity = "P2"
    incident, created = report_incident(
        db,
        actor,
        source="ci_triage",
        external_id=external_id,
        ip=ip,
        title=f"[{d.category}] {payload.workflow or 'CI'} failed in {payload.repo}",
        severity=severity,
        description=summary,
        service=payload.repo,
        environment="ci",
        evidence={"run_url": payload.run_url, "branch": payload.branch, "diagnosis": diagnosis},
    )
    _note(result, incident, created)
    return result


def generic(db: Session, key: ApiKey, payload: GenericIntake, ip: str | None) -> dict:
    result = _result()
    incident, created = report_incident(
        db,
        Actor.api_key(key),
        source="generic",
        external_id=payload.external_id,
        ip=ip,
        title=payload.title,
        severity=payload.severity,
        description=payload.description,
        service=payload.service,
        environment=payload.environment,
        evidence=payload.evidence,
    )
    _note(result, incident, created)
    return result
