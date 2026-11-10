from app.models import ApiKey, AuditLog, Incident


def gh_event(run_id=100, conclusion="failure", branch="main", repo="ron1120/app", name="CI", default="main"):
    return {
        "action": "completed",
        "workflow_run": {
            "id": run_id, "name": name, "conclusion": conclusion, "head_branch": branch,
            "head_sha": "abc123", "html_url": f"https://github.com/{repo}/actions/runs/{run_id}",
            "run_attempt": 1, "event": "push", "some_unused_field": {"x": 1},
        },
        "repository": {"full_name": repo, "default_branch": default, "private": False},
    }


def post(client, source_path, key, body):
    return client.post(f"/api/intake/{source_path}", json=body, headers={"X-API-Key": key})


def incidents(client, headers):
    return client.get("/api/incidents", headers=headers).json()["items"]


# ---- keys ---------------------------------------------------------------------------------------------------------
def test_only_admins_manage_keys_and_the_plain_key_is_shown_once(client, db, admin_headers, analyst_headers):
    body = {"name": "github-ci", "source": "github_actions"}
    assert client.post("/api/api-keys", json=body, headers=analyst_headers).status_code == 403
    created = client.post("/api/api-keys", json=body, headers=admin_headers)
    assert created.status_code == 201
    raw = created.json()["key"]
    assert raw.startswith("ops_") and created.json()["prefix"] == raw[:8]
    listing = client.get("/api/api-keys", headers=admin_headers)
    assert listing.status_code == 200 and raw not in listing.text and "key_hash" not in listing.text
    assert client.get("/api/api-keys", headers=analyst_headers).status_code == 403
    stored = db.query(ApiKey).one()
    assert stored.key_hash != raw and raw not in (stored.key_hash, stored.prefix, stored.name)  # only a hash is kept


def test_keys_are_limited_to_known_sources(client, admin_headers):
    assert client.post("/api/api-keys", json={"name": "x", "source": "manual"}, headers=admin_headers).status_code == 422
    assert client.post("/api/api-keys", json={"name": "", "source": "generic"}, headers=admin_headers).status_code == 422


def test_intake_refuses_missing_wrong_and_revoked_keys(client, admin_headers, make_key):
    assert client.post("/api/intake/generic", json={"title": "x"}).status_code == 401
    assert post(client, "generic", "ops_not-a-real-key", {"title": "x"}).status_code == 401
    key = make_key("generic")
    assert post(client, "generic", key, {"title": "x"}).status_code == 200
    key_id = client.get("/api/api-keys", headers=admin_headers).json()[0]["id"]
    assert client.delete(f"/api/api-keys/{key_id}", headers=admin_headers).status_code == 204
    assert client.delete(f"/api/api-keys/{key_id}", headers=admin_headers).status_code == 204  # revoking twice is fine
    assert post(client, "generic", key, {"title": "x"}).status_code == 401  # a revoked key stops working at once
    assert client.delete("/api/api-keys/999", headers=admin_headers).status_code == 404


def test_a_key_only_works_for_its_own_source(client, make_key):
    github_key = make_key("github_actions")
    assert post(client, "alertmanager", github_key, {"alerts": []}).status_code == 403
    assert post(client, "generic", github_key, {"title": "x"}).status_code == 403
    assert post(client, "github-actions", github_key, gh_event()).status_code == 200


def test_a_user_login_token_is_not_an_api_key(client, analyst_headers):
    token = analyst_headers["Authorization"].split()[1]
    assert post(client, "generic", token, {"title": "x"}).status_code == 401


def test_using_a_key_records_when_it_was_last_used(client, admin_headers, make_key):
    key = make_key("generic")
    assert client.get("/api/api-keys", headers=admin_headers).json()[0]["last_used_at"] is None
    post(client, "generic", key, {"title": "x"})
    assert client.get("/api/api-keys", headers=admin_headers).json()[0]["last_used_at"] is not None


# ---- GitHub Actions -----------------------------------------------------------------------------------------------
def test_a_failed_run_on_the_default_branch_is_a_p2_incident(client, admin_headers, make_key):
    key = make_key("github_actions", "github-ci")
    result = post(client, "github-actions", key, gh_event()).json()
    assert result["created"] == 1 and result["updated"] == 0 and result["ignored"] == 0
    incident = client.get(f"/api/incidents/{result['incident_ids'][0]}", headers=admin_headers).json()
    assert incident["severity"] == "P2" and incident["source"] == "github_actions"
    assert incident["service"] == "ron1120/app" and incident["environment"] == "ci"
    assert incident["title"] == "CI failed: CI on main"
    assert incident["evidence"]["run_url"].endswith("/runs/100") and incident["evidence"]["head_sha"] == "abc123"
    assert "key:github-ci" in incident["events"][0]["actor"]


def test_a_failed_run_on_another_branch_is_a_p3(client, admin_headers, make_key):
    key = make_key("github_actions")
    post(client, "github-actions", key, gh_event(branch="feature/x"))
    assert incidents(client, admin_headers)[0]["severity"] == "P3"


def test_runs_that_did_not_fail_are_ignored(client, admin_headers, make_key):
    key = make_key("github_actions")
    for conclusion in ("success", "cancelled", "skipped", None):
        assert post(client, "github-actions", key, gh_event(conclusion=conclusion)).json()["ignored"] == 1
    assert incidents(client, admin_headers) == []


def test_the_same_failed_run_reported_twice_is_one_incident(client, admin_headers, make_key):
    key = make_key("github_actions")
    post(client, "github-actions", key, gh_event(run_id=7))
    again = post(client, "github-actions", key, gh_event(run_id=7)).json()
    assert again["created"] == 0 and again["updated"] == 1
    items = incidents(client, admin_headers)
    assert len(items) == 1 and items[0]["occurrences"] == 2
    post(client, "github-actions", key, gh_event(run_id=8))  # a different run is a different incident
    assert len(incidents(client, admin_headers)) == 2


def test_a_resolved_incident_reopens_when_the_same_thing_fails_again(client, admin_headers, make_key):
    key = make_key("github_actions")
    incident_id = post(client, "github-actions", key, gh_event(run_id=7)).json()["incident_ids"][0]
    client.post(f"/api/incidents/{incident_id}/status", json={"status": "resolved"}, headers=admin_headers)
    post(client, "github-actions", key, gh_event(run_id=7))
    reopened = client.get(f"/api/incidents/{incident_id}", headers=admin_headers).json()
    assert reopened["status"] == "open" and reopened["resolved_at"] is None
    assert any("Reported again" in e["body"] for e in reopened["events"])


def test_a_malformed_github_payload_is_a_422(client, make_key):
    key = make_key("github_actions")
    assert post(client, "github-actions", key, {"workflow_run": {}}).status_code == 422
    assert post(client, "github-actions", key, {}).status_code == 422


# ---- Alertmanager -------------------------------------------------------------------------------------------------
def alert(name="HighCPU", severity="critical", status="firing", fingerprint="f1", **labels):
    return {
        "status": status, "fingerprint": fingerprint,
        "labels": {"alertname": name, "severity": severity, "service": "api", "env": "prod", **labels},
        "annotations": {"summary": f"{name} on api", "description": "CPU above 90% for 10m"},
        "startsAt": "2026-11-08T10:00:00Z", "generatorURL": "http://prometheus/graph",
    }


def test_alerts_become_incidents_with_mapped_severity(client, admin_headers, make_key):
    key = make_key("alertmanager")
    body = {"alerts": [alert(fingerprint="a", severity="critical"), alert("Slow", "warning", fingerprint="b"),
                       alert("Note", "info", fingerprint="c"), alert("Odd", "weird", fingerprint="d")]}
    result = post(client, "alertmanager", key, body).json()
    assert result["created"] == 4
    severities = {i["title"]: i["severity"] for i in incidents(client, admin_headers)}
    assert severities == {"HighCPU on api": "P1", "Slow on api": "P3", "Note on api": "P4", "Odd on api": "P3"}
    detail = client.get(f"/api/incidents/{result['incident_ids'][0]}", headers=admin_headers).json()
    assert detail["service"] == "api" and detail["environment"] == "prod" and detail["source"] == "alertmanager"
    assert detail["evidence"]["labels"]["alertname"] == "HighCPU" and detail["description"] == "CPU above 90% for 10m"


def test_a_firing_alert_repeated_does_not_open_a_second_incident(client, admin_headers, make_key):
    key = make_key("alertmanager")
    for _ in range(3):
        post(client, "alertmanager", key, {"alerts": [alert()]})
    items = incidents(client, admin_headers)
    assert len(items) == 1 and items[0]["occurrences"] == 3


def test_a_resolved_alert_marks_a_triaged_incident_mitigated_but_a_person_closes_it(client, admin_headers, make_key):
    key = make_key("alertmanager")
    incident_id = post(client, "alertmanager", key, {"alerts": [alert()]}).json()["incident_ids"][0]
    client.post(f"/api/incidents/{incident_id}/status", json={"status": "triaged"}, headers=admin_headers)
    result = post(client, "alertmanager", key, {"alerts": [alert(status="resolved")]}).json()
    assert result["updated"] == 1
    detail = client.get(f"/api/incidents/{incident_id}", headers=admin_headers).json()
    assert detail["status"] == "mitigated" and detail["resolved_at"] is None  # not closed by the machine
    assert any("Alert resolved in Alertmanager" in e["body"] for e in detail["events"])


def test_a_resolved_alert_cannot_skip_triage_on_an_untouched_incident(client, admin_headers, make_key):
    key = make_key("alertmanager")
    incident_id = post(client, "alertmanager", key, {"alerts": [alert()]}).json()["incident_ids"][0]
    response = post(client, "alertmanager", key, {"alerts": [alert(status="resolved")]})
    assert response.status_code == 200 and response.json()["updated"] == 1  # never a 500 for a valid alert
    detail = client.get(f"/api/incidents/{incident_id}", headers=admin_headers).json()
    assert detail["status"] == "open" and detail["acknowledged_at"] is None
    assert any("still open" in e["body"] for e in detail["events"])


def test_a_resolved_alert_for_an_unknown_or_closed_incident_is_ignored(client, admin_headers, make_key):
    key = make_key("alertmanager")
    assert post(client, "alertmanager", key, {"alerts": [alert(status="resolved", fingerprint="never-seen")]}).json()["ignored"] == 1
    incident_id = post(client, "alertmanager", key, {"alerts": [alert()]}).json()["incident_ids"][0]
    client.post(f"/api/incidents/{incident_id}/status", json={"status": "resolved"}, headers=admin_headers)
    assert post(client, "alertmanager", key, {"alerts": [alert(status="resolved")]}).json()["ignored"] == 1


def test_alerts_without_a_fingerprint_are_still_deduplicated_by_their_labels(client, admin_headers, make_key):
    key = make_key("alertmanager")
    no_fp = alert(fingerprint=None)
    del no_fp["fingerprint"]
    post(client, "alertmanager", key, {"alerts": [no_fp]})
    post(client, "alertmanager", key, {"alerts": [no_fp]})
    assert len(incidents(client, admin_headers)) == 1


def test_too_many_alerts_in_one_request_is_refused(client, make_key):
    key = make_key("alertmanager")
    body = {"alerts": [alert(fingerprint=str(i)) for i in range(101)]}
    assert post(client, "alertmanager", key, body).status_code == 422


# ---- ci-triage-agent ------------------------------------------------------------------------------------------------
def triage(run_id=100, category="infra_failure", confidence="high", branch="main", repo="ron1120/app"):
    return {
        "repo": repo, "run_id": run_id, "run_url": f"https://github.com/{repo}/actions/runs/{run_id}",
        "workflow": "CI", "branch": branch, "default_branch": "main",
        "diagnosis": {
            "category": category, "confidence": confidence, "summary": "The download timed out.",
            "evidence": ["curl: (28) Connection timed out"], "next_step": "Re-run the job.",
            "source": "rules", "model": "", "usage": {"ignored": True},
        },
    }


def test_the_triage_diagnosis_is_attached_to_the_incident_for_that_run(client, admin_headers, make_key):
    gh, tr = make_key("github_actions"), make_key("ci_triage")
    incident_id = post(client, "github-actions", gh, gh_event(run_id=100)).json()["incident_ids"][0]
    result = post(client, "ci-triage", tr, triage(run_id=100)).json()
    assert result["created"] == 0 and result["updated"] == 1 and result["incident_ids"] == [incident_id]
    detail = client.get(f"/api/incidents/{incident_id}", headers=admin_headers).json()
    assert len(incidents(client, admin_headers)) == 1
    assert detail["evidence"]["diagnosis"]["category"] == "infra_failure" and detail["evidence"]["head_sha"] == "abc123"
    note = [e for e in detail["events"] if e["kind"] == "comment"][-1]
    assert "infra_failure" in note["body"] and "Re-run the job." in note["body"] and "key:ci_triage-key" in note["actor"]


def test_a_triage_report_opens_an_incident_when_ci_intake_never_saw_the_run(client, admin_headers, make_key):
    tr = make_key("ci_triage")
    result = post(client, "ci-triage", tr, triage(run_id=5, category="real_failure", branch="main")).json()
    assert result["created"] == 1
    incident = client.get(f"/api/incidents/{result['incident_ids'][0]}", headers=admin_headers).json()
    assert incident["source"] == "ci_triage" and incident["severity"] == "P2"  # a real failure on the default branch
    assert incident["title"] == "[real_failure] CI failed in ron1120/app" and incident["evidence"]["diagnosis"]["next_step"]


def test_triage_severity_depends_on_the_diagnosis(client, admin_headers, make_key):
    tr = make_key("ci_triage")
    for run_id, category, branch in [(1, "flaky_test", "main"), (2, "real_failure", "feature/x"), (3, "dependency_env", "main")]:
        post(client, "ci-triage", tr, triage(run_id=run_id, category=category, branch=branch))
    by_title = {i["title"].split("]")[0][1:]: i["severity"] for i in incidents(client, admin_headers)}
    assert by_title == {"flaky_test": "P4", "real_failure": "P3", "dependency_env": "P3"}


def test_oversized_triage_fields_are_refused(client, make_key):
    tr = make_key("ci_triage")
    body = triage()
    body["diagnosis"]["summary"] = "x" * 2001
    assert post(client, "ci-triage", tr, body).status_code == 422


# ---- generic ------------------------------------------------------------------------------------------------------
def test_generic_events_with_an_id_deduplicate_and_without_one_do_not(client, admin_headers, make_key):
    key = make_key("generic")
    post(client, "generic", key, {"title": "Cert expiring", "severity": "P2", "external_id": "cert-1"})
    post(client, "generic", key, {"title": "Cert expiring", "severity": "P2", "external_id": "cert-1"})
    assert len(incidents(client, admin_headers)) == 1
    post(client, "generic", key, {"title": "Odd thing"})
    post(client, "generic", key, {"title": "Odd thing"})
    assert len(incidents(client, admin_headers)) == 3


def test_generic_validation(client, make_key):
    key = make_key("generic")
    assert post(client, "generic", key, {"title": "x", "severity": "P7"}).status_code == 422
    assert post(client, "generic", key, {"severity": "P1"}).status_code == 422
    assert post(client, "generic", key, {"title": "x" * 256}).status_code == 422


# ---- the same external id from two different sources are different incidents ----------------------------------------
def test_dedup_is_per_source(client, admin_headers, make_key):
    post(client, "generic", make_key("generic"), {"title": "a", "external_id": "same"})
    post(client, "github-actions", make_key("github_actions"), gh_event(run_id=1))
    assert len(incidents(client, admin_headers)) == 2


def test_nothing_is_written_when_the_key_is_wrong(client, db):
    post(client, "generic", "ops_bad", {"title": "x"})
    assert db.query(Incident).count() == 0 and db.query(AuditLog).filter(AuditLog.action == "incident.create").count() == 0


# ---- Authorization: Bearer (what Alertmanager sends) ---------------------------------------------------------------
def test_a_key_can_also_be_sent_as_a_bearer_token(client, admin_headers, make_key):
    key = make_key("alertmanager")
    response = client.post("/api/intake/alertmanager", json={"alerts": [alert()]}, headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 200 and response.json()["created"] == 1
    assert client.post("/api/intake/alertmanager", json={"alerts": []}, headers={"Authorization": "Bearer ops_nope"}).status_code == 401
    assert client.post("/api/intake/alertmanager", json={"alerts": []}, headers={"Authorization": key}).status_code == 401  # no "Bearer"
