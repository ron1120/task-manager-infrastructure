def test_metrics_are_exposed_in_prometheus_format(client):
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/plain")
    assert 'http_requests_total{method="GET",path="/health",status="200"}' in response.text
    assert "http_request_duration_seconds_bucket" in response.text
    assert 'incidents_open{severity="P1"} 0.0' in response.text and "incidents_breached 0.0" in response.text


def test_incident_gauges_follow_the_database(client, analyst_headers):
    client.post("/api/incidents", json={"title": "a", "severity": "P1"}, headers=analyst_headers)
    client.post("/api/incidents", json={"title": "b", "severity": "P1"}, headers=analyst_headers)
    done = client.post("/api/incidents", json={"title": "c", "severity": "P2"}, headers=analyst_headers).json()
    client.post(f"/api/incidents/{done['id']}/status", json={"status": "resolved"}, headers=analyst_headers)
    text = client.get("/metrics").text
    assert 'incidents_open{severity="P1"} 2.0' in text and 'incidents_open{severity="P2"} 0.0' in text


def test_metric_labels_use_route_templates_not_raw_urls(client, analyst_headers):
    client.get("/api/incidents/12345", headers=analyst_headers)  # does not exist
    text = client.get("/metrics").text
    assert 'path="/api/incidents/{incident_id}"' in text and "12345" not in text
