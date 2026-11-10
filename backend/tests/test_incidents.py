from datetime import datetime, timedelta, timezone

from app.models import AuditLog, Incident


def new_incident(client, headers, **overrides):
    body = {"title": "Disk full on db-1", "severity": "P2", "service": "database", "environment": "prod", **overrides}
    response = client.post("/api/incidents", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_creating_an_incident_sets_a_deadline_and_the_first_timeline_entry(client, analyst_headers):
    incident = new_incident(client, analyst_headers, severity="P1")
    assert incident["status"] == "open" and incident["severity"] == "P1" and incident["source"] == "manual"
    opened = datetime.fromisoformat(incident["created_at"])
    due = datetime.fromisoformat(incident["sla_due_at"])
    assert due - opened == timedelta(hours=4)  # P1 must be resolved within 4 hours
    assert incident["breached"] is False and incident["events"][0]["kind"] == "system"
    assert "analyst@example.com" in incident["events"][0]["actor"]


def test_sla_deadlines_follow_severity(client, analyst_headers):
    hours = {}
    for severity in ("P1", "P2", "P3", "P4"):
        i = new_incident(client, analyst_headers, severity=severity)
        hours[severity] = (datetime.fromisoformat(i["sla_due_at"]) - datetime.fromisoformat(i["created_at"])).total_seconds() / 3600
    assert hours == {"P1": 4, "P2": 24, "P3": 72, "P4": 168}


def test_viewers_can_read_but_not_change_incidents(client, analyst_headers, viewer_headers):
    incident = new_incident(client, analyst_headers)
    assert client.get("/api/incidents", headers=viewer_headers).status_code == 200
    assert client.get(f"/api/incidents/{incident['id']}", headers=viewer_headers).status_code == 200
    assert client.post("/api/incidents", json={"title": "x"}, headers=viewer_headers).status_code == 403
    assert client.patch(f"/api/incidents/{incident['id']}", json={"title": "y"}, headers=viewer_headers).status_code == 403
    assert client.post(f"/api/incidents/{incident['id']}/status", json={"status": "triaged"}, headers=viewer_headers).status_code == 403
    assert client.post(f"/api/incidents/{incident['id']}/comments", json={"body": "hi"}, headers=viewer_headers).status_code == 403


def test_everything_needs_a_login(client):
    assert client.get("/api/incidents").status_code == 401
    assert client.post("/api/incidents", json={"title": "x"}).status_code == 401
    assert client.get("/api/incidents/stats").status_code == 401


def test_unknown_incident_is_404(client, analyst_headers):
    assert client.get("/api/incidents/999", headers=analyst_headers).status_code == 404
    assert client.post("/api/incidents/999/status", json={"status": "triaged"}, headers=analyst_headers).status_code == 404


def test_validation_rejects_bad_input(client, analyst_headers):
    assert client.post("/api/incidents", json={"title": ""}, headers=analyst_headers).status_code == 422
    assert client.post("/api/incidents", json={"title": "x", "severity": "P9"}, headers=analyst_headers).status_code == 422
    assert client.post("/api/incidents", json={"title": "x", "assignee_id": 999}, headers=analyst_headers).status_code == 422


def test_status_follows_the_workflow_and_records_the_milestones(client, analyst_headers):
    incident = new_incident(client, analyst_headers)
    path = f"/api/incidents/{incident['id']}/status"
    triaged = client.post(path, json={"status": "triaged", "note": "looking"}, headers=analyst_headers).json()
    assert triaged["status"] == "triaged" and triaged["acknowledged_at"] is not None and triaged["resolved_at"] is None
    assert any("Note: looking" in e["body"] for e in triaged["events"])
    assert client.post(path, json={"status": "mitigated"}, headers=analyst_headers).json()["status"] == "mitigated"
    resolved = client.post(path, json={"status": "resolved"}, headers=analyst_headers).json()
    assert resolved["status"] == "resolved" and resolved["resolved_at"] is not None and resolved["breached"] is False


def test_impossible_status_moves_are_refused(client, analyst_headers):
    incident = new_incident(client, analyst_headers)
    path = f"/api/incidents/{incident['id']}/status"
    refused = client.post(path, json={"status": "mitigated"}, headers=analyst_headers)  # open -> mitigated skips triage
    assert refused.status_code == 409 and "Allowed:" in refused.json()["detail"]
    assert client.post(path, json={"status": "bogus"}, headers=analyst_headers).status_code == 422
    client.post(path, json={"status": "resolved"}, headers=analyst_headers)
    assert client.post(path, json={"status": "mitigated"}, headers=analyst_headers).status_code == 409


def test_a_resolved_incident_can_be_reopened(client, analyst_headers):
    incident = new_incident(client, analyst_headers)
    path = f"/api/incidents/{incident['id']}/status"
    client.post(path, json={"status": "resolved"}, headers=analyst_headers)
    reopened = client.post(path, json={"status": "open"}, headers=analyst_headers).json()
    assert reopened["status"] == "open" and reopened["resolved_at"] is None


def test_comments_build_the_timeline_in_order(client, analyst_headers):
    incident = new_incident(client, analyst_headers)
    path = f"/api/incidents/{incident['id']}/comments"
    client.post(path, json={"body": "first"}, headers=analyst_headers)
    detail = client.post(path, json={"body": "second"}, headers=analyst_headers).json()
    assert [e["body"] for e in detail["events"] if e["kind"] == "comment"] == ["first", "second"]
    assert client.post(path, json={"body": ""}, headers=analyst_headers).status_code == 422


def test_updating_severity_moves_the_deadline_and_is_logged(client, analyst_headers):
    incident = new_incident(client, analyst_headers, severity="P4")
    updated = client.patch(f"/api/incidents/{incident['id']}", json={"severity": "P1"}, headers=analyst_headers).json()
    due = datetime.fromisoformat(updated["sla_due_at"]) - datetime.fromisoformat(updated["created_at"])
    assert updated["severity"] == "P1" and due == timedelta(hours=4)
    assert any(e["kind"] == "severity" and "P4 to P1" in e["body"] for e in updated["events"])


def test_assigning_and_unassigning(client, admin_headers, analyst_headers):
    me = client.get("/api/auth/me", headers=analyst_headers).json()
    incident = new_incident(client, analyst_headers)
    path = f"/api/incidents/{incident['id']}"
    assigned = client.patch(path, json={"assignee_id": me["id"]}, headers=analyst_headers).json()
    assert assigned["assignee"]["email"] == "analyst@example.com"
    unassigned = client.patch(path, json={"assignee_id": None}, headers=analyst_headers).json()
    assert unassigned["assignee"] is None
    assert [e["body"] for e in unassigned["events"] if e["kind"] == "assignment"][-1].startswith("Unassigned")
    assert client.patch(path, json={"assignee_id": 999}, headers=analyst_headers).status_code == 422


def test_an_update_that_changes_nothing_writes_no_audit_entry(client, db, analyst_headers):
    incident = new_incident(client, analyst_headers, title="Same")
    before = db.query(AuditLog).count()
    client.patch(f"/api/incidents/{incident['id']}", json={"title": "Same"}, headers=analyst_headers)
    assert db.query(AuditLog).count() == before


def test_listing_filters_search_and_paging(client, analyst_headers):
    new_incident(client, analyst_headers, title="Low disk", severity="P4", service="db")
    new_incident(client, analyst_headers, title="API down", severity="P1", service="api")
    new_incident(client, analyst_headers, title="API slow", severity="P3", service="api")
    everything = client.get("/api/incidents", headers=analyst_headers).json()
    assert everything["total"] == 3 and [i["severity"] for i in everything["items"]] == ["P1", "P3", "P4"]  # worst first
    assert client.get("/api/incidents?service=api", headers=analyst_headers).json()["total"] == 2
    assert client.get("/api/incidents?severity=P4", headers=analyst_headers).json()["items"][0]["title"] == "Low disk"
    assert client.get("/api/incidents?q=slow", headers=analyst_headers).json()["total"] == 1
    page = client.get("/api/incidents?limit=2&offset=2", headers=analyst_headers).json()
    assert page["total"] == 3 and len(page["items"]) == 1
    assert client.get("/api/incidents?limit=500", headers=analyst_headers).status_code == 422
    assert client.get("/api/incidents?status=bogus", headers=analyst_headers).status_code == 422


def test_listing_by_assignee_and_unassigned(client, analyst_headers):
    me = client.get("/api/auth/me", headers=analyst_headers).json()
    mine = new_incident(client, analyst_headers, title="Mine", assignee_id=me["id"])
    new_incident(client, analyst_headers, title="Nobody's")
    assert [i["id"] for i in client.get("/api/incidents?assignee=me", headers=analyst_headers).json()["items"]] == [mine["id"]]
    assert client.get("/api/incidents?unassigned=true", headers=analyst_headers).json()["total"] == 1
    assert client.get("/api/incidents?assignee=nobody", headers=analyst_headers).status_code == 422


def test_overdue_incidents_are_flagged_and_filterable(client, db, analyst_headers):
    overdue = new_incident(client, analyst_headers, title="Overdue", severity="P4")
    new_incident(client, analyst_headers, title="Fine", severity="P4")
    row = db.query(Incident).filter(Incident.id == overdue["id"]).first()
    row.sla_due_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    flagged = client.get("/api/incidents?breached=true", headers=analyst_headers).json()
    assert [i["title"] for i in flagged["items"]] == ["Overdue"] and flagged["items"][0]["breached"] is True
    assert client.get("/api/incidents?breached=false", headers=analyst_headers).json()["total"] == 1
    # Resolving stops the clock.
    client.post(f"/api/incidents/{overdue['id']}/status", json={"status": "resolved"}, headers=analyst_headers)
    assert client.get("/api/incidents?breached=true", headers=analyst_headers).json()["total"] == 0


def test_stats_summarise_the_open_work(client, db, analyst_headers):
    a = new_incident(client, analyst_headers, severity="P1")
    b = new_incident(client, analyst_headers, severity="P3")
    new_incident(client, analyst_headers, severity="P3")
    client.post(f"/api/incidents/{a['id']}/status", json={"status": "triaged"}, headers=analyst_headers)
    client.post(f"/api/incidents/{b['id']}/status", json={"status": "resolved"}, headers=analyst_headers)
    stats = client.get("/api/incidents/stats", headers=analyst_headers).json()
    assert stats["open_total"] == 2 and stats["open_by_severity"] == {"P1": 1, "P2": 0, "P3": 1, "P4": 0}
    assert stats["unassigned"] == 2 and stats["breached"] == 0
    assert stats["mtta_hours"] is not None and stats["mttr_hours"] is not None


def test_stats_with_no_incidents(client, analyst_headers):
    stats = client.get("/api/incidents/stats", headers=analyst_headers).json()
    assert stats["open_total"] == 0 and stats["mtta_hours"] is None and stats["mttr_hours"] is None


def test_the_existing_task_endpoints_still_work_for_every_role(client, viewer_headers):
    assert client.post("/api/tasks", json={"title": "mine"}, headers=viewer_headers).status_code == 201
