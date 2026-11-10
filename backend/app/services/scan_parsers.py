# Reading scanner output (Trivy, gitleaks, Hadolint) into one common shape.
#
# Every parser returns (target, findings). A finding is a plain dict with: kind, rule_id, title, severity, and
# optionally description, package, installed_version, fixed_version, location, url.
#
# Secret values are NEVER copied: gitleaks' `Secret` and `Match` fields, Trivy's secret `Match`, author names and
# e-mail addresses are all dropped here, so nothing sensitive can reach the database.
import hashlib

MAX_FINDINGS = 5000
SEVERITIES = {"critical", "high", "medium", "low", "unknown"}


class ScanFormatError(ValueError):
    """The uploaded report is not in the format the scanner endpoint expects."""


def _clip(value, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _severity(value) -> str:
    text = str(value or "").lower()
    return text if text in SEVERITIES else "unknown"


def fingerprint(*parts) -> str:
    return hashlib.sha256("|".join(str(p or "") for p in parts).encode()).hexdigest()[:40]


def _check_size(count: int) -> None:
    if count > MAX_FINDINGS:
        raise ScanFormatError(f"The report has {count} findings; the limit is {MAX_FINDINGS} per upload.")


def parse_trivy(report) -> tuple[str, list[dict]]:
    """`trivy image|fs|config -f json`: vulnerabilities, secrets and failed misconfiguration checks."""
    if not isinstance(report, dict) or not isinstance(report.get("Results", []), list):
        raise ScanFormatError("Expected a Trivy JSON report (an object with a Results list).")
    target = _clip(report.get("ArtifactName"), 255) or "unknown"
    findings: list[dict] = []
    for result in report.get("Results") or []:
        where = _clip(result.get("Target"), 450)
        for v in result.get("Vulnerabilities") or []:
            findings.append({
                "kind": "vulnerability",
                "rule_id": _clip(v.get("VulnerabilityID"), 100) or "unknown",
                "title": _clip(v.get("Title") or f"{v.get('PkgName')} {v.get('VulnerabilityID')}", 255),
                "description": _clip(v.get("Description"), 2000),
                "severity": _severity(v.get("Severity")),
                "package": _clip(v.get("PkgName"), 200),
                "installed_version": _clip(v.get("InstalledVersion"), 100),
                "fixed_version": _clip(v.get("FixedVersion"), 200),
                "location": where,
                "url": _clip(v.get("PrimaryURL"), 500),
            })
        for s in result.get("Secrets") or []:
            line = s.get("StartLine")
            findings.append({
                "kind": "secret",
                "rule_id": _clip(s.get("RuleID"), 100) or "secret",
                "title": _clip(s.get("Title") or "Secret detected", 255),
                "severity": _severity(s.get("Severity") or "high"),
                "location": f"{where}:{line}" if line else where,  # where it is, never what it is
            })
        for m in result.get("Misconfigurations") or []:
            if str(m.get("Status", "FAIL")).upper() != "FAIL":
                continue
            line = (m.get("CauseMetadata") or {}).get("StartLine")
            findings.append({
                "kind": "misconfig",
                "rule_id": _clip(m.get("ID") or m.get("AVDID"), 100) or "misconfig",
                "title": _clip(m.get("Title"), 255) or "Misconfiguration",
                "description": _clip(m.get("Message") or m.get("Description"), 2000),
                "severity": _severity(m.get("Severity")),
                "location": f"{where}:{line}" if line else where,
                "url": _clip(m.get("PrimaryURL"), 500),
            })
    _check_size(len(findings))
    return target, findings


def parse_gitleaks(report) -> tuple[str, list[dict]]:
    """`gitleaks detect -f json`: leaked credentials found in files or in git history."""
    if not isinstance(report, list):
        raise ScanFormatError("Expected a gitleaks JSON report (a list of findings).")
    _check_size(len(report))
    findings = []
    for leak in report:
        if not isinstance(leak, dict):
            raise ScanFormatError("Every gitleaks finding must be an object.")
        commit = _clip(leak.get("Commit"), 40)
        line = leak.get("StartLine")
        path = _clip(leak.get("File"), 400) or "unknown"
        findings.append({
            "kind": "secret",
            "rule_id": _clip(leak.get("RuleID"), 100) or "secret",
            "title": _clip(leak.get("Description"), 255) or "Secret detected",
            "severity": "high",
            "location": f"{path}:{line}" if line else path,
            # The commit is part of the identity: the same string in two commits is two places to clean up.
            "_identity": _clip(leak.get("Fingerprint"), 200) or f"{commit}:{path}:{line}",
            "description": f"Found in commit {commit[:12]}." if commit else None,
        })
    return "git history", findings


HADOLINT_SEVERITY = {"error": "medium", "warning": "low", "info": "low", "style": "low"}


def parse_hadolint(report) -> tuple[str, list[dict]]:
    """`hadolint -f json`: Dockerfile lint results."""
    if not isinstance(report, list):
        raise ScanFormatError("Expected a Hadolint JSON report (a list of findings).")
    _check_size(len(report))
    findings = []
    for item in report:
        if not isinstance(item, dict):
            raise ScanFormatError("Every Hadolint finding must be an object.")
        path, line = _clip(item.get("file"), 400) or "Dockerfile", item.get("line")
        code = _clip(item.get("code"), 100) or "lint"
        findings.append({
            "kind": "lint",
            "rule_id": code,
            "title": _clip(item.get("message"), 255) or code,
            "severity": HADOLINT_SEVERITY.get(str(item.get("level", "")).lower(), "low"),
            "location": f"{path}:{line}" if line else path,
            "url": f"https://github.com/hadolint/hadolint/wiki/{code}" if code.startswith(("DL", "SC")) else None,
        })
    return "Dockerfiles", findings


PARSERS = {"trivy": parse_trivy, "gitleaks": parse_gitleaks, "hadolint": parse_hadolint}
