def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok!"}


def test_register_and_login(client):
    register_response = client.post(
        "/api/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert register_response.status_code == 201
    assert register_response.json()["email"] == "user@example.com"

    login_response = client.post(
        "/api/auth/login",
        data={"username": "user@example.com", "password": "password123"},
    )
    assert login_response.status_code == 200
    assert "access_token" in login_response.json()


def test_task_crud(client, auth_headers):
    create_response = client.post(
        "/api/tasks",
        json={"title": "Test task", "description": "Do something"},
        headers=auth_headers,
    )
    assert create_response.status_code == 201
    task = create_response.json()
    assert task["title"] == "Test task"
    assert task["completed"] is False

    list_response = client.get("/api/tasks", headers=auth_headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    update_response = client.put(
        f"/api/tasks/{task['id']}",
        json={"title": "Updated task"},
        headers=auth_headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Updated task"

    complete_response = client.patch(
        f"/api/tasks/{task['id']}/complete",
        headers=auth_headers,
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["completed"] is True

    delete_response = client.delete(
        f"/api/tasks/{task['id']}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 204
