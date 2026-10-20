from datetime import date, timedelta
from fastapi.testclient import TestClient


def test_search_trains_success(client: TestClient):
    today = str(date.today())
    response = client.get(f"/api/v1/trains/search?source=NDLS&destination=CNB&journey_date={today}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    train = data[0]
    assert train["train_number"] == "12004"
    assert train["source_station_code"] == "NDLS"
    assert train["destination_station_code"] == "CNB"
    assert train["departure_time"] == "06:10"
    assert train["arrival_time"] == "11:20"
    assert train["available_seats"] == 50
    assert train["fare"] == 750.0


def test_search_trains_same_source_and_destination(client: TestClient):
    today = str(date.today())
    response = client.get(f"/api/v1/trains/search?source=NDLS&destination=NDLS&journey_date={today}")
    assert response.status_code == 400
    assert "cannot be the same" in response.json()["detail"]


def test_search_trains_past_date(client: TestClient):
    past_date = str(date.today() - timedelta(days=1))
    response = client.get(f"/api/v1/trains/search?source=NDLS&destination=CNB&journey_date={past_date}")
    assert response.status_code == 400
    assert "cannot be in the past" in response.json()["detail"]


def test_search_trains_no_route(client: TestClient):
    today = str(date.today())
    response = client.get(f"/api/v1/trains/search?source=HWH&destination=CNB&journey_date={today}")
    assert response.status_code == 200
    assert response.json() == []


def test_get_train_by_id(client: TestClient):
    response = client.get("/api/v1/trains/1")
    assert response.status_code == 200
    assert response.json()["train_number"] == "12004"


def test_get_train_by_invalid_id(client: TestClient):
    response = client.get("/api/v1/trains/9999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_check_seat_availability(client: TestClient):
    today = str(date.today())
    response = client.get(f"/api/v1/trains/1/availability?journey_date={today}")
    assert response.status_code == 200
    data = response.json()
    assert data["train_id"] == 1
    assert data["available_seats"] == 50
    assert data["status"] == "AVAILABLE"
