# Business logic for findings: ingest a scan, list and summarise, accept a risk, open an incident for a finding.
from datetime import datetime

from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from app.core.actor import Actor
from app.models import FINDING_SEVERITIES, Finding, Scan
from app.services import audit, incident_service
from app.services.scan_parsers import PARSERS, fingerprint

SEVERITY_ORDER = case({name: rank for rank, name in enumerate(FINDING_SEVERITIES)}, value=Finding.severity, else_=99)
INCIDENT_SEVERITY = {"critical": "P2", "high": "P3"}  # a finding's severity -> the incident's, when one is opened


class FindingNotFound(LookupError):
    pass


class RiskReasonRequired(ValueError):
    pass


def _identity(scanner: str, finding: dict) -> str:
    # A gitleaks leak is identified by its commit too; everything else by what, where and which package version.
    return fingerprint(
        finding["kind"], finding["rule_id"], finding.get("package"), finding.get("installed_version"),
        finding.get("location"), finding.get("_identity"),
    )


def ingest_scan(
    db: Session,
    actor: Actor,
    scanner: str,
    report,
    *,
    target: str | None = None,
    ref: str | None = None,
    run_url: str | None = None,
    complete: bool = True,
    ip: str | None = None,
) -> dict:
    """Store one scan. Returns counts and the ids of any incidents opened for it.

    `complete` means the report covers the whole target, so a finding missing from it really was fixed. Pass False
    for a partial scan (for example only the files in one pull request) to avoid closing findings by mistake.
    """
    reported_target, parsed = PARSERS[scanner](report)
    target = (target or reported_target)[:255]
    at = incident_service.now()

    existing = {
        f.fingerprint: f for f in db.query(Finding).filter(Finding.scanner == scanner, Finding.target == target).all()
    }
    seen: set[str] = set()
    new: list[Finding] = []
    reopened = unchanged = 0
    by_severity = {name: 0 for name in FINDING_SEVERITIES}

    for item in parsed:
        fp = _identity(scanner, item)
        if fp in seen:
            continue  # the same finding listed twice in one report
        seen.add(fp)
        by_severity[item["severity"]] += 1
        found = existing.get(fp)
        if found is None:
            found = Finding(
                fingerprint=fp, scanner=scanner, target=target, status="open", occurrences=1,
                first_seen_at=at, last_seen_at=at,
                **{k: v for k, v in item.items() if not k.startswith("_")},
            )
            db.add(found)
            new.append(found)
            continue
        found.occurrences += 1
        found.last_seen_at = at
        found.severity, found.fixed_version = item["severity"], item.get("fixed_version")  # a fix may have appeared
        if found.status == "fixed":
            found.status, found.fixed_at, found.status_reason = "open", None, None
            reopened += 1
        else:
            unchanged += 1

    fixed = 0
    if complete:
        for fp, found in existing.items():
            if fp not in seen and found.status != "fixed":
                found.status, found.fixed_at = "fixed", at  # it is gone from a full scan: someone fixed it
                fixed += 1

    scan = Scan(
        scanner=scanner, target=target, ref=_clip(ref, 100), run_url=_clip(run_url, 500), complete=complete,
        total=len(seen), new_count=len(new), fixed_count=fixed, by_severity=by_severity, actor=actor.label,
    )
    db.add(scan)
    db.flush()  # gives the new findings and the scan their ids

    incident_ids = _open_incidents(db, actor, scan, new, ip)
    audit.record(
        db, actor, "scan.ingest", "scan", scan.id,
        {"scanner": scanner, "target": target, "total": len(seen), "new": len(new), "fixed": fixed, "reopened": reopened}, ip,
    )
    db.commit()
    return {
        "scan_id": scan.id, "total": len(seen), "new": len(new), "reopened": reopened, "fixed": fixed,
        "unchanged": unchanged, "incident_ids": incident_ids,
    }


def _clip(value: str | None, limit: int) -> str | None:
    return value[:limit] if value else None


def _open_incidents(db: Session, actor: Actor, scan: Scan, new: list[Finding], ip: str | None) -> list[int]:
    """A leaked secret, or a new critical finding, is something to act on today, so it becomes an incident."""
    ids = []
    secrets = [f for f in new if f.kind == "secret"]
    critical = [f for f in new if f.kind != "secret" and f.severity == "critical" and f.kind != "lint"]
    for group, title, severity, label in (
        (secrets, f"{len(secrets)} secret(s) found in {scan.target}", "P1", "secrets"),
        (critical, f"{len(critical)} new critical finding(s) in {scan.target}", "P2", "critical"),
    ):
        if not group:
            continue
        incident = incident_service.create_incident(
            db, actor, title=title[:255], severity=severity, service=scan.target[:100], environment="security",
            source="scanner", external_id=f"scan:{scan.id}:{label}", ip=ip,
            description=f"{scan.scanner} reported these in scan #{scan.id}. Open the Security page to review them.",
            # Rule, package and where: enough to act on. Never a secret's value.
            evidence={"scan_id": scan.id, "ref": scan.ref, "run_url": scan.run_url, "findings": [
                {"rule": f.rule_id, "package": f.package, "installed": f.installed_version, "fixed": f.fixed_version,
                 "location": f.location} for f in group[:20]
            ]},
        )
        for f in group:
            f.incident_id = incident.id
        ids.append(incident.id)
    return ids


def get_finding(db: Session, finding_id: int) -> Finding | None:
    return db.query(Finding).filter(Finding.id == finding_id).first()


def list_findings(
    db: Session, *, status: str | None = None, severity: str | None = None, scanner: str | None = None,
    kind: str | None = None, target: str | None = None, fixable: bool | None = None, q: str | None = None,
    limit: int = 25, offset: int = 0,
) -> tuple[list[Finding], int]:
    query = db.query(Finding)
    for column, value in ((Finding.status, status), (Finding.severity, severity), (Finding.scanner, scanner),
                          (Finding.kind, kind), (Finding.target, target)):
        if value:
            query = query.filter(column == value)
    if fixable is not None:
        has_fix = Finding.fixed_version.isnot(None) & (Finding.fixed_version != "")
        query = query.filter(has_fix if fixable else ~has_fix)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Finding.rule_id.ilike(like), Finding.title.ilike(like), Finding.package.ilike(like),
                                 Finding.location.ilike(like)))
    total = query.count()
    # Worst first, then the ones with a fix available, then newest.
    items = query.order_by(SEVERITY_ORDER, Finding.fixed_version.is_(None), Finding.last_seen_at.desc(), Finding.id) \
        .offset(offset).limit(limit).all()
    return items, total


def stats(db: Session) -> dict:
    open_rows = db.query(Finding).filter(Finding.status == "open").all()
    by_severity = {name: 0 for name in FINDING_SEVERITIES}
    by_kind: dict[str, int] = {}
    for f in open_rows:
        by_severity[f.severity] += 1
        by_kind[f.kind] = by_kind.get(f.kind, 0) + 1
    criticals = [incident_service.aware(f.first_seen_at) for f in open_rows if f.severity == "critical"]
    last = db.query(Scan).order_by(Scan.id.desc()).first()
    return {
        "open_total": len(open_rows),
        "open_by_severity": by_severity,
        "open_by_kind": by_kind,
        "fixable_open": sum(1 for f in open_rows if f.kind == "vulnerability" and f.fixed_version),
        "oldest_open_critical_days": (incident_service.now() - min(criticals)).days if criticals else None,
        "last_scan_at": last.created_at if last else None,
    }


def set_status(
    db: Session, finding: Finding, actor: Actor, status: str, reason: str | None, ip: str | None = None
) -> Finding:
    """A person accepts a risk (with a reason) or reopens a finding. Fixed is set only by a scan."""
    if status == "accepted" and not (reason and len(reason.strip()) >= 5):
        raise RiskReasonRequired("Accepting a risk needs a reason of at least 5 characters.")
    old = finding.status
    if old != status:
        finding.status = status
        finding.status_reason = reason.strip() if status == "accepted" else None
        finding.status_by = actor.label
        audit.record(
            db, actor, "finding.status_change", "finding", finding.id,
            {"from": old, "to": status, "rule": finding.rule_id, "reason": finding.status_reason}, ip,
        )
        db.commit()
        db.refresh(finding)
    return finding


def open_incident_for(db: Session, finding: Finding, actor: Actor, ip: str | None = None):
    if finding.incident_id is not None:
        return incident_service.get_incident(db, finding.incident_id)
    detail = f"{finding.package} {finding.installed_version}" if finding.package else finding.location
    incident = incident_service.create_incident(
        db, actor, title=f"{finding.rule_id}: {finding.title}"[:255], severity=INCIDENT_SEVERITY.get(finding.severity, "P4"),
        service=finding.target[:100], environment="security", source="manual", ip=ip,
        description=f"{finding.scanner} finding #{finding.id} ({finding.severity}) in {detail}.\n{finding.url or ''}".strip(),
        evidence={"finding_id": finding.id, "fixed_version": finding.fixed_version, "location": finding.location},
    )
    finding.incident_id = incident.id
    audit.record(db, actor, "finding.incident", "finding", finding.id, {"incident_id": incident.id}, ip)
    db.commit()
    return incident


def recent_scans(db: Session, limit: int = 20) -> list[Scan]:
    return db.query(Scan).order_by(Scan.id.desc()).limit(limit).all()


def age_hours(finding: Finding, at: datetime | None = None) -> float:
    return ((at or incident_service.now()) - incident_service.aware(finding.first_seen_at)).total_seconds() / 3600
