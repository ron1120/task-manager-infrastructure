import pytest
from app.models import AuditLog, Finding, Incident, IncidentEvent, Scan
from app.services.scan_parsers import ScanFormatError, parse_gitleaks, parse_hadolint, parse_trivy

# Built at runtime, not written as one literal, so secret scanners do not flag this test file.
SECRET_VALUE = "-".join(["sk", "live", "9f8e7d6c5b4a3210abcdef0123456789"])


def vuln(cve="CVE-2026-0001", pkg="openssl", installed="1.0", fixed="1.1", severity="HIGH"):
    return {"VulnerabilityID": cve, "PkgName": pkg, "InstalledVersion": installed, "FixedVersion": fixed,
            "Severity": severity, "Title": f"{pkg} problem", "Description": "bad", "PrimaryURL": f"https://avd/{cve}"}


def trivy(*vulns, name="registry/app:1.0", secrets=(), misconfigs=()):
    result = {"Target": "app (debian 13)", "Vulnerabilities": list(vulns)}
    if secrets:
        result["Secrets"] = list(secrets)
    if misconfigs:
        result["Misconfigurations"] = list(misconfigs)
    return {"ArtifactName": name, "Results": [result]}


def upload(client, key, scanner, report, **params):
    return client.post(f"/api/intake/scan/{scanner}", json=report, params=params, headers={"X-API-Key": key})


def findings(client, headers, **params):
    return client.get("/api/findings", params=params, headers=headers).json()


# ---- parsers ---------------------------------------------------------------------------------------------------------
def test_trivy_parser_reads_vulnerabilities_secrets_and_failed_misconfigurations():
    report = trivy(
        vuln(), vuln("CVE-2", "zlib", severity="WEIRD"),
        secrets=[{"RuleID": "aws-key", "Title": "AWS key", "Severity": "CRITICAL", "StartLine": 7, "Match": SECRET_VALUE}],
        misconfigs=[{"ID": "DS-0002", "Title": "Runs as root", "Severity": "HIGH", "Status": "FAIL", "Message": "m",
                     "CauseMetadata": {"StartLine": 3}}, {"ID": "DS-9", "Title": "ok", "Severity": "LOW", "Status": "PASS"}],
    )
    target, items = parse_trivy(report)
    assert target == "registry/app:1.0" and [i["kind"] for i in items] == ["vulnerability"] * 2 + ["secret", "misconfig"]
    assert items[0]["severity"] == "high" and items[1]["severity"] == "unknown"  # unknown names are not guessed at
    assert items[2]["location"] == "app (debian 13):7" and items[3]["location"] == "app (debian 13):3"
    assert SECRET_VALUE not in str(items)  # where the secret is, never what it is


def test_gitleaks_parser_drops_secrets_authors_and_emails():
    leak = {"RuleID": "generic-api-key", "Description": "Generic API Key", "File": "README.md", "StartLine": 97,
            "Commit": "09632d80ca671b3108bda9123842e703b131f38e", "Secret": SECRET_VALUE, "Match": f"token={SECRET_VALUE}",
            "Author": "Some One", "Email": "someone@example.com", "Fingerprint": "09632d8:README.md:generic-api-key:97"}
    target, items = parse_gitleaks([leak])
    assert target == "git history" and items[0]["location"] == "README.md:97" and items[0]["severity"] == "high"
    dump = str(items)
    for forbidden in (SECRET_VALUE, "Some One", "someone@example.com"):
        assert forbidden not in dump


def test_hadolint_parser_maps_levels_to_severities():
    _, items = parse_hadolint([
        {"code": "DL3008", "level": "warning", "message": "Pin versions", "file": "backend/Dockerfile", "line": 8},
        {"code": "DL1000", "level": "error", "message": "Bad", "file": "Dockerfile", "line": 1},
    ])
    assert [(i["rule_id"], i["severity"], i["location"]) for i in items] == [
        ("DL3008", "low", "backend/Dockerfile:8"), ("DL1000", "medium", "Dockerfile:1")]


@pytest.mark.parametrize("parser,bad", [(parse_trivy, []), (parse_trivy, {"Results": "x"}), (parse_gitleaks, {}),
                                        (parse_hadolint, "text"), (parse_gitleaks, ["not an object"])])
def test_parsers_reject_the_wrong_format(parser, bad):
    with pytest.raises(ScanFormatError):
        parser(bad)


def test_a_report_with_too_many_findings_is_refused():
    with pytest.raises(ScanFormatError, match="limit"):
        parse_hadolint([{"code": f"DL{i}", "level": "info", "message": "m", "file": "f", "line": 1} for i in range(5001)])


# ---- intake ---------------------------------------------------------------------------------------------------------
def test_only_a_scanner_key_can_upload_scans(client, make_key):
    report = trivy(vuln())
    assert client.post("/api/intake/scan/trivy", json=report).status_code == 401
    assert upload(client, make_key("generic"), "trivy", report).status_code == 403
    assert upload(client, make_key("scanner"), "trivy", report).status_code == 200


def test_the_first_scan_records_findings_and_repeats_inside_a_report_count_once(client, admin_headers, make_key):
    key = make_key("scanner")
    result = upload(client, key, "trivy", trivy(vuln(), vuln(), vuln("CVE-2026-0002", "zlib", severity="LOW"))).json()
    assert (result["total"], result["new"], result["fixed"], result["reopened"], result["unchanged"]) == (2, 2, 0, 0, 0)
    assert result["incident_ids"] == []
    assert findings(client, admin_headers)["total"] == 2


def test_scanning_the_same_thing_again_changes_nothing_but_the_counters(client, admin_headers, make_key):
    key = make_key("scanner")
    upload(client, key, "trivy", trivy(vuln()))
    second = upload(client, key, "trivy", trivy(vuln())).json()
    assert (second["new"], second["unchanged"], second["fixed"]) == (0, 1, 0)
    item = findings(client, admin_headers)["items"][0]
    assert item["occurrences"] == 2 and item["status"] == "open"


def test_a_finding_that_disappears_is_marked_fixed_and_reopens_if_it_returns(client, admin_headers, make_key):
    key = make_key("scanner")
    upload(client, key, "trivy", trivy(vuln("CVE-A"), vuln("CVE-B", "zlib")))
    fixed = upload(client, key, "trivy", trivy(vuln("CVE-B", "zlib"))).json()
    assert fixed["fixed"] == 1
    by_rule = {f["rule_id"]: f for f in findings(client, admin_headers)["items"]}
    assert by_rule["CVE-A"]["status"] == "fixed" and by_rule["CVE-A"]["fixed_at"] and by_rule["CVE-B"]["status"] == "open"
    back = upload(client, key, "trivy", trivy(vuln("CVE-A"), vuln("CVE-B", "zlib"))).json()
    assert back["reopened"] == 1 and back["fixed"] == 0
    reopened = {f["rule_id"]: f for f in findings(client, admin_headers)["items"]}["CVE-A"]
    assert reopened["status"] == "open" and reopened["fixed_at"] is None


def test_a_partial_scan_never_closes_findings(client, admin_headers, make_key):
    key = make_key("scanner")
    upload(client, key, "trivy", trivy(vuln("CVE-A"), vuln("CVE-B", "zlib")))
    partial = upload(client, key, "trivy", trivy(vuln("CVE-B", "zlib")), complete="false").json()
    assert partial["fixed"] == 0
    assert findings(client, admin_headers, status="open")["total"] == 2


def test_findings_are_per_target(client, admin_headers, make_key):
    key = make_key("scanner")
    upload(client, key, "trivy", trivy(vuln(), name="image-a"))
    upload(client, key, "trivy", trivy(name="image-b"))  # a clean scan of another image closes nothing in image-a
    assert findings(client, admin_headers, status="open")["total"] == 1
    upload(client, key, "trivy", trivy(vuln()), target="override")  # the target can be named by the caller
    assert findings(client, admin_headers, target="override")["total"] == 1


def test_upgrading_a_package_closes_the_old_finding_and_a_new_fix_is_picked_up(client, admin_headers, make_key):
    key = make_key("scanner")
    upload(client, key, "trivy", trivy(vuln(installed="1.0", fixed="")))
    upload(client, key, "trivy", trivy(vuln(installed="1.0", fixed="1.2")))  # a fix was published
    item = findings(client, admin_headers)["items"][0]
    assert item["fixed_version"] == "1.2" and item["occurrences"] == 2
    upload(client, key, "trivy", trivy(vuln(installed="1.1", fixed="1.3")))  # upgraded, still vulnerable: a new finding
    states = sorted((f["installed_version"], f["status"]) for f in findings(client, admin_headers)["items"])
    assert states == [("1.0", "fixed"), ("1.1", "open")]


def test_bad_uploads_are_rejected(client, make_key):
    key = make_key("scanner")
    assert upload(client, key, "trivy", []).status_code == 422
    assert upload(client, key, "gitleaks", {"Results": []}).status_code == 422
    assert upload(client, key, "nessus", {}).status_code == 422
    assert client.post("/api/intake/scan/trivy", content="not json", headers={"X-API-Key": key}).status_code == 422


# ---- secrets and incidents --------------------------------------------------------------------------------------------
LEAK = {"RuleID": "generic-api-key", "Description": "Generic API Key", "File": "config.py", "StartLine": 12,
        "Commit": "abc1234def", "Secret": SECRET_VALUE, "Match": f"KEY={SECRET_VALUE}", "Email": "dev@example.com",
        "Author": "Dev Eloper", "Fingerprint": "abc1234:config.py:generic-api-key:12"}


def test_a_leaked_secret_opens_a_p1_incident_and_the_value_is_never_stored(client, db, admin_headers, make_key):
    result = upload(client, make_key("scanner"), "gitleaks", [LEAK], target="repo").json()
    assert result["new"] == 1 and len(result["incident_ids"]) == 1
    incident = client.get(f"/api/incidents/{result['incident_ids'][0]}", headers=admin_headers).json()
    assert incident["severity"] == "P1" and incident["source"] == "scanner" and "secret" in incident["title"]
    assert incident["evidence"]["findings"][0]["location"] == "config.py:12"
    finding = findings(client, admin_headers)["items"][0]
    assert finding["incident_id"] == incident["id"] and finding["kind"] == "secret"
    # Search every table that could hold it.
    for model in (Finding, Incident, IncidentEvent, AuditLog, Scan):
        for row in db.query(model).all():
            dump = str(vars(row))
            for forbidden in (SECRET_VALUE, "dev@example.com", "Dev Eloper"):
                assert forbidden not in dump, f"{forbidden} leaked into {model.__tablename__}"


def test_the_same_leak_in_the_next_scan_does_not_open_another_incident(client, admin_headers, make_key):
    key = make_key("scanner")
    upload(client, key, "gitleaks", [LEAK], target="repo")
    again = upload(client, key, "gitleaks", [LEAK], target="repo").json()
    assert again["new"] == 0 and again["incident_ids"] == []
    assert client.get("/api/incidents", headers=admin_headers).json()["total"] == 1


def test_a_new_critical_vulnerability_opens_a_p2_incident_but_high_and_lint_do_not(client, admin_headers, make_key):
    key = make_key("scanner")
    quiet = upload(client, key, "trivy", trivy(vuln(severity="HIGH"), vuln("CVE-L", "x", severity="LOW"))).json()
    assert quiet["incident_ids"] == []
    loud = upload(client, key, "trivy", trivy(vuln(severity="HIGH"), vuln("CVE-C", "libc", severity="CRITICAL"))).json()
    assert loud["new"] == 1 and len(loud["incident_ids"]) == 1
    incident = client.get(f"/api/incidents/{loud['incident_ids'][0]}", headers=admin_headers).json()
    assert incident["severity"] == "P2" and incident["evidence"]["findings"][0]["rule"] == "CVE-C"
    assert incident["evidence"]["findings"][0]["fixed"] == "1.1"
    hadolint = upload(client, key, "hadolint", [{"code": "DL3008", "level": "error", "message": "m", "file": "D", "line": 1}]).json()
    assert hadolint["incident_ids"] == []


def test_a_critical_misconfiguration_also_opens_an_incident(client, make_key):
    report = trivy(misconfigs=[{"ID": "AWS-0104", "Title": "Open egress", "Severity": "CRITICAL", "Status": "FAIL"}])
    assert len(upload(client, make_key("scanner"), "trivy", report).json()["incident_ids"]) == 1


# ---- reading, accepting risk, linking ---------------------------------------------------------------------------------
def seed(client, make_key):
    key = make_key("scanner")
    upload(client, key, "trivy", trivy(
        vuln("CVE-LOW", "a", fixed="", severity="LOW"), vuln("CVE-HIGH", "b", severity="HIGH"),
        vuln("CVE-MED", "c", fixed="", severity="MEDIUM"), vuln("CVE-HIGH2", "d", fixed="", severity="HIGH"),
    ))
    upload(client, key, "hadolint", [{"code": "DL3008", "level": "warning", "message": "Pin", "file": "Dockerfile", "line": 2}])


def test_listing_is_sorted_worst_first_and_filterable(client, admin_headers, viewer_headers, make_key):
    seed(client, make_key)
    items = findings(client, viewer_headers)["items"]  # viewers can read
    assert [f["severity"] for f in items] == ["high", "high", "medium", "low", "low"]
    assert items[0]["rule_id"] == "CVE-HIGH"  # among equals, the one with a fix available comes first
    assert findings(client, admin_headers, severity="high")["total"] == 2
    assert findings(client, admin_headers, scanner="hadolint")["total"] == 1
    assert findings(client, admin_headers, kind="lint")["total"] == 1
    assert findings(client, admin_headers, fixable="true")["total"] == 1
    assert findings(client, admin_headers, q="CVE-MED")["items"][0]["package"] == "c"
    page = findings(client, admin_headers, limit=2, offset=4)
    assert page["total"] == 5 and len(page["items"]) == 1
    assert client.get("/api/findings?limit=500", headers=admin_headers).status_code == 422
    assert client.get("/api/findings?severity=scary", headers=admin_headers).status_code == 422
    assert client.get("/api/findings").status_code == 401


def test_stats(client, db, admin_headers, make_key):
    key = make_key("scanner")
    upload(client, key, "trivy", trivy(vuln("CVE-C", "libc", severity="CRITICAL"), vuln("CVE-H", "b", fixed="", severity="HIGH")))
    stats = client.get("/api/findings/stats", headers=admin_headers).json()
    assert stats["open_total"] == 2 and stats["open_by_severity"]["critical"] == 1 and stats["fixable_open"] == 1
    assert stats["open_by_kind"] == {"vulnerability": 2} and stats["last_scan_at"] and stats["oldest_open_critical_days"] == 0


def test_the_age_of_the_oldest_critical_is_reported(client, db, admin_headers, make_key):
    from datetime import datetime, timedelta, timezone

    upload(client, make_key("scanner"), "trivy", trivy(vuln("CVE-C", "libc", severity="CRITICAL")))
    row = db.query(Finding).one()
    row.first_seen_at = datetime.now(timezone.utc) - timedelta(days=10, hours=1)
    db.commit()
    assert client.get("/api/findings/stats", headers=admin_headers).json()["oldest_open_critical_days"] == 10


def test_an_analyst_can_accept_a_risk_with_a_reason_and_it_survives_the_next_scan(client, admin_headers, analyst_headers, make_key):
    seed(client, make_key)
    target = findings(client, admin_headers, q="CVE-MED")["items"][0]
    path = f"/api/findings/{target['id']}/status"
    assert client.post(path, json={"status": "accepted"}, headers=analyst_headers).status_code == 422  # no reason
    assert client.post(path, json={"status": "accepted", "reason": "no"}, headers=analyst_headers).status_code == 422
    accepted = client.post(path, json={"status": "accepted", "reason": "Needs a major upgrade, tracked in #12"}, headers=analyst_headers)
    assert accepted.status_code == 200 and accepted.json()["status"] == "accepted"
    assert accepted.json()["status_by"] == "user:analyst@example.com" and "major upgrade" in accepted.json()["status_reason"]
    upload(client, make_key("scanner", "again"), "trivy", trivy(
        vuln("CVE-LOW", "a", fixed="", severity="LOW"), vuln("CVE-HIGH", "b", severity="HIGH"),
        vuln("CVE-MED", "c", fixed="", severity="MEDIUM"), vuln("CVE-HIGH2", "d", fixed="", severity="HIGH")))
    assert client.get(f"/api/findings/{target['id']}", headers=admin_headers).json()["status"] == "accepted"
    assert findings(client, admin_headers, status="open")["total"] == 4  # accepted ones leave the open list
    reopened = client.post(path, json={"status": "open"}, headers=analyst_headers).json()
    assert reopened["status"] == "open" and reopened["status_reason"] is None
    entries = client.get("/api/audit?action=finding.status_change", headers=admin_headers).json()["items"]
    assert entries[1]["details"]["reason"].startswith("Needs a major upgrade") and entries[1]["details"]["to"] == "accepted"


def test_viewers_cannot_change_findings_and_fixed_cannot_be_set_by_hand(client, admin_headers, viewer_headers, analyst_headers, make_key):
    seed(client, make_key)
    fid = findings(client, admin_headers)["items"][0]["id"]
    assert client.post(f"/api/findings/{fid}/status", json={"status": "accepted", "reason": "because"}, headers=viewer_headers).status_code == 403
    assert client.post(f"/api/findings/{fid}/incident", headers=viewer_headers).status_code == 403
    assert client.post(f"/api/findings/{fid}/status", json={"status": "fixed"}, headers=analyst_headers).status_code == 422
    assert client.get("/api/findings/9999", headers=admin_headers).status_code == 404
    assert client.post("/api/findings/9999/status", json={"status": "open"}, headers=analyst_headers).status_code == 404


def test_opening_an_incident_for_a_finding_is_idempotent(client, admin_headers, analyst_headers, make_key):
    seed(client, make_key)
    high = findings(client, admin_headers, q="CVE-HIGH2")["items"][0]
    first = client.post(f"/api/findings/{high['id']}/incident", headers=analyst_headers)
    assert first.status_code == 201 and first.json()["severity"] == "P3" and "CVE-HIGH2" in first.json()["title"]
    second = client.post(f"/api/findings/{high['id']}/incident", headers=analyst_headers).json()
    assert second["id"] == first.json()["id"]
    assert client.get("/api/incidents", headers=admin_headers).json()["total"] == 1
    assert client.get(f"/api/findings/{high['id']}", headers=admin_headers).json()["incident_id"] == first.json()["id"]


def test_scans_are_listed_newest_first(client, admin_headers, make_key):
    key = make_key("scanner")
    upload(client, key, "trivy", trivy(vuln()), ref="abc123", run_url="https://github.com/x/y/actions/runs/1")
    upload(client, key, "trivy", trivy())
    scans = client.get("/api/scans", headers=admin_headers).json()
    assert [s["fixed_count"] for s in scans] == [1, 0] and scans[1]["ref"] == "abc123" and scans[0]["actor"] == "key:scanner-key"
    assert scans[1]["by_severity"]["high"] == 1


def test_open_findings_are_exported_as_metrics(client, make_key):
    upload(client, make_key("scanner"), "trivy", trivy(vuln(severity="HIGH"), vuln("CVE-2", "z", severity="HIGH")))
    assert 'findings_open{severity="high"} 2.0' in client.get("/metrics").text
