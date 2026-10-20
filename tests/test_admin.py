from datetime import date, timedelta
from fastapi.testclient import TestClient


def get_token(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_admin_access_forbidden_for_passenger(client: TestClient):
    token = get_token(client, "passenger@railconnect.com", "Passenger@12345")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/admin/trains",
        headers=headers,
        json={
            "train_number": "99999",
            "train_name": "Unauthorized Train",
            "source_station_code": "NDLS",
            "destination_station_code": "CNB",
            "departure_time": "10:00",
            "arrival_time": "15:00",
            "total_seats": 50,
            "base_fare": 400.0,
            "is_active": True,
        },
    )
    assert response.status_code == 403
    assert "Administrator privileges required" in response.json()["detail"]


def test_admin_add_station(client: TestClient):
    token = get_token(client, "admin@railconnect.com", "Admin@12345")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/admin/stations",
        headers=headers,
        json={
            "code": "AGC",
            "name": "Agra Cantt",
            "city": "Agra",
            "state": "Uttar Pradesh",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["code"] == "AGC"
    assert data["name"] == "Agra Cantt"


def test_admin_add_train(client: TestClient):
    token = get_token(client, "admin@railconnect.com", "Admin@12345")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/admin/trains",
        headers=headers,
        json={
            "train_number": "12003",
            "train_name": "New Delhi Shatabdi Express",
            "source_station_code": "CNB",
            "destination_station_code": "NDLS",
            "departure_time": "16:50",
            "arrival_time": "22:00",
            "total_seats": 80,
            "base_fare": 750.0,
            "is_active": True,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["train_number"] == "12003"
    assert data["source_station_code"] == "CNB"
    assert data["destination_station_code"] == "NDLS"


def test_admin_update_and_deactivate_train(client: TestClient):
    token = get_token(client, "admin@railconnect.com", "Admin@12345")
    headers = {"Authorization": f"Bearer {token}"}

    update_resp = client.put(
        "/api/v1/admin/trains/1",
        headers=headers,
        json={"base_fare": 850.0},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["base_fare"] == 850.0

    deactivate_resp = client.patch("/api/v1/admin/trains/1/deactivate", headers=headers)
    assert deactivate_resp.status_code == 200
    assert deactivate_resp.json()["is_active"] is False

    today = str(date.today())
    search_resp = client.get(
        f"/api/v1/trains/search?source=NDLS&destination=CNB&journey_date={today}"
    )
    assert search_resp.status_code == 200
    assert len(search_resp.json()) == 0

    reactivate_resp = client.patch("/api/v1/admin/trains/1/activate", headers=headers)
    assert reactivate_resp.status_code == 200
    assert reactivate_resp.json()["is_active"] is True


def test_admin_set_schedule_and_seats(client: TestClient):
    token = get_token(client, "admin@railconnect.com", "Admin@12345")
    headers = {"Authorization": f"Bearer {token}"}
    future_date = str(date.today() + timedelta(days=10))

    response = client.post(
        "/api/v1/admin/schedules",
        headers=headers,
        json={
            "train_id": 1,
            "journey_date": future_date,
            "total_seats": 60,
            "available_seats": 60,
            "fare": 900.0,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["total_seats"] == 60
    assert data["available_seats"] == 60
    assert data["fare"] == 900.0
