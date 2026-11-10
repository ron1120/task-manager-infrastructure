from app.models import AuditLog


def audit(client, headers, **params):
    return client.get("/api/audit", params=params, headers=headers).json()


def test_the_first_user_is_the_admin_and_later_ones_are_analysts(client, admin_headers, analyst_headers):
    assert client.get("/api/auth/me", headers=admin_headers).json()["role"] == "admin"
    assert client.get("/api/auth/me", headers=analyst_headers).json()["role"] == "analyst"


def test_admins_can_change_roles_and_it_is_audited(client, admin_headers, analyst_headers):
    analyst_id = client.get("/api/auth/me", headers=analyst_headers).json()["id"]
    changed = client.patch(f"/api/users/{analyst_id}/role", json={"role": "viewer"}, headers=admin_headers)
    assert changed.status_code == 200 and changed.json()["role"] == "viewer"
    # The new role applies to the very next request, with the same token.
    assert client.post("/api/incidents", json={"title": "x"}, headers=analyst_headers).status_code == 403
    entry = audit(client, admin_headers, action="user.role_change")["items"][0]
    assert entry["details"] == {"from": "analyst", "to": "viewer"} and entry["actor"] == "user:user@example.com"


def test_analysts_cannot_change_roles_or_read_the_audit_log(client, analyst_headers):
    me = client.get("/api/auth/me", headers=analyst_headers).json()["id"]
    assert client.patch(f"/api/users/{me}/role", json={"role": "admin"}, headers=analyst_headers).status_code == 403
    assert client.get("/api/audit", headers=analyst_headers).status_code == 403
    assert client.get("/api/audit").status_code == 401


def test_the_last_admin_cannot_be_demoted(client, admin_headers):
    me = client.get("/api/auth/me", headers=admin_headers).json()["id"]
    refused = client.patch(f"/api/users/{me}/role", json={"role": "analyst"}, headers=admin_headers)
    assert refused.status_code == 409 and "at least one admin" in refused.json()["detail"]


def test_an_admin_can_be_demoted_when_another_admin_exists(client, admin_headers, analyst_headers):
    analyst_id = client.get("/api/auth/me", headers=analyst_headers).json()["id"]
    client.patch(f"/api/users/{analyst_id}/role", json={"role": "admin"}, headers=admin_headers)
    me = client.get("/api/auth/me", headers=admin_headers).json()["id"]
    assert client.patch(f"/api/users/{me}/role", json={"role": "analyst"}, headers=admin_headers).status_code == 200


def test_role_changes_are_validated(client, admin_headers, analyst_headers):
    analyst_id = client.get("/api/auth/me", headers=analyst_headers).json()["id"]
    assert client.patch(f"/api/users/{analyst_id}/role", json={"role": "root"}, headers=admin_headers).status_code == 422
    assert client.patch("/api/users/999/role", json={"role": "viewer"}, headers=admin_headers).status_code == 404


def test_the_user_list_is_for_analysts_and_up(client, admin_headers, analyst_headers, viewer_headers):
    emails = [u["email"] for u in client.get("/api/users", headers=analyst_headers).json()]
    assert emails == ["user@example.com", "analyst@example.com", "viewer@example.com"]
    assert "hashed_password" not in client.get("/api/users", headers=analyst_headers).text
    assert client.get("/api/users", headers=viewer_headers).status_code == 403


def test_every_change_leaves_an_audit_entry_with_who_did_it(client, admin_headers, analyst_headers, make_key):
    incident_id = client.post("/api/incidents", json={"title": "x", "severity": "P2"}, headers=analyst_headers).json()["id"]
    client.post(f"/api/incidents/{incident_id}/status", json={"status": "triaged"}, headers=analyst_headers)
    client.post(f"/api/incidents/{incident_id}/comments", json={"body": "hi"}, headers=analyst_headers)
    client.patch(f"/api/incidents/{incident_id}", json={"severity": "P1"}, headers=analyst_headers)
    key = make_key("generic", "monitor")
    client.post("/api/intake/generic", json={"title": "from a machine"}, headers={"X-API-Key": key})
    actions = [e["action"] for e in audit(client, admin_headers, limit=200)["items"]]
    for expected in ("incident.create", "incident.status_change", "incident.comment", "incident.update", "apikey.create"):
        assert expected in actions
    machine = audit(client, admin_headers, action="incident.create")["items"][0]
    assert machine["actor"] == "key:monitor" and machine["actor_type"] == "api_key"
    mine = [e for e in audit(client, admin_headers, action="incident.create")["items"] if e["actor_type"] == "user"]
    assert mine[0]["actor"] == "user:analyst@example.com" and mine[0]["ip"]


def test_logins_and_failed_logins_are_audited_without_the_password(client, admin_headers):
    client.post("/api/auth/login", data={"username": "user@example.com", "password": "wrong-password-123"})
    failed = audit(client, admin_headers, action="auth.login_failed")["items"]
    assert len(failed) == 1 and failed[0]["actor"] == "anonymous:user@example.com" and failed[0]["ip"]
    assert "wrong-password-123" not in client.get("/api/audit?limit=200", headers=admin_headers).text
    assert audit(client, admin_headers, action="auth.login")["total"] >= 1
    assert audit(client, admin_headers, action="user.register")["total"] >= 1


def test_secrets_never_reach_the_audit_log(client, db, admin_headers, make_key):
    key = make_key("generic")
    client.post("/api/intake/generic", json={"title": "x"}, headers={"X-API-Key": key})
    everything = " ".join(str(vars(row)) for row in db.query(AuditLog).all())
    assert key not in everything and "password123" not in everything


def test_the_audit_log_filters_and_pages(client, admin_headers, analyst_headers):
    for n in range(3):
        client.post("/api/incidents", json={"title": f"i{n}"}, headers=analyst_headers)
    creates = audit(client, admin_headers, action="incident.create", limit=2)
    assert creates["total"] == 3 and len(creates["items"]) == 2
    assert audit(client, admin_headers, entity_type="incident")["total"] == 3
    assert audit(client, admin_headers, actor="user:analyst@example.com", action="incident.create")["total"] == 3
    ids = [e["id"] for e in audit(client, admin_headers, limit=200)["items"]]
    assert ids == sorted(ids, reverse=True)  # newest first
    assert client.get("/api/audit?limit=500", headers=admin_headers).status_code == 422


def test_there_is_no_way_to_edit_or_delete_audit_entries(client, admin_headers):
    entry_id = audit(client, admin_headers)["items"][0]["id"]
    for method in ("put", "patch", "delete"):
        assert getattr(client, method)(f"/api/audit/{entry_id}", headers=admin_headers).status_code in (404, 405)
