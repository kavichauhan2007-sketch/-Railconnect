from datetime import date, timedelta
from fastapi.testclient import TestClient


def get_token(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_book_ticket_success(client: TestClient):
    token = get_token(client, "passenger@railconnect.com", "Passenger@12345")
    headers = {"Authorization": f"Bearer {token}"}
    today = str(date.today())

    book_resp = client.post(
        "/api/v1/bookings",
        headers=headers,
        json={
            "train_id": 1,
            "journey_date": today,
            "passenger_name": "Tushar Chauhan",
            "passenger_age": 28,
            "passenger_gender": "Male",
            "berth_preference": "LOWER",
            "seats_booked": 2,
        },
    )
    assert book_resp.status_code == 201
    booking = book_resp.json()
    assert booking["pnr"].startswith("RC")
    assert booking["seats_booked"] == 2
    assert booking["booking_status"] == "CONFIRMED"
    assert booking["payment_status"] == "PAID"
    assert booking["train_number"] == "12004"
    assert booking["source_station_code"] == "NDLS"
    assert booking["destination_station_code"] == "CNB"

    avail_resp = client.get(f"/api/v1/trains/1/availability?journey_date={today}")
    assert avail_resp.json()["available_seats"] == 48


def test_booking_history_privacy(client: TestClient):
    token1 = get_token(client, "passenger@railconnect.com", "Passenger@12345")
    token2 = get_token(client, "passenger2@railconnect.com", "Passenger@12345")
    today = str(date.today())

    client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token1}"},
        json={
            "train_id": 1,
            "journey_date": today,
            "passenger_name": "Passenger One",
            "passenger_age": 25,
            "passenger_gender": "Male",
            "seats_booked": 1,
        },
    )

    history2 = client.get(
        "/api/v1/bookings/my-bookings",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert history2.status_code == 200
    assert len(history2.json()) == 0

    history1 = client.get(
        "/api/v1/bookings/my-bookings",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert history1.status_code == 200
    assert len(history1.json()) >= 1


def test_get_booking_by_pnr_and_unauthorized_access(client: TestClient):
    token1 = get_token(client, "passenger@railconnect.com", "Passenger@12345")
    token2 = get_token(client, "passenger2@railconnect.com", "Passenger@12345")
    today = str(date.today())

    book_resp = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token1}"},
        json={
            "train_id": 1,
            "journey_date": today,
            "passenger_name": "Passenger One",
            "passenger_age": 25,
            "passenger_gender": "Male",
            "seats_booked": 1,
        },
    )
    pnr = book_resp.json()["pnr"]

    resp1 = client.get(f"/api/v1/bookings/{pnr}", headers={"Authorization": f"Bearer {token1}"})
    assert resp1.status_code == 200
    assert resp1.json()["pnr"] == pnr

    resp2 = client.get(f"/api/v1/bookings/{pnr}", headers={"Authorization": f"Bearer {token2}"})
    assert resp2.status_code == 403
    assert "You can only view your own bookings" in resp2.json()["detail"]


def test_ticket_cancellation_and_seat_restoration(client: TestClient):
    token = get_token(client, "passenger@railconnect.com", "Passenger@12345")
    headers = {"Authorization": f"Bearer {token}"}
    today = str(date.today())

    init_avail = client.get(f"/api/v1/trains/1/availability?journey_date={today}").json()["available_seats"]

    book_resp = client.post(
        "/api/v1/bookings",
        headers=headers,
        json={
            "train_id": 1,
            "journey_date": today,
            "passenger_name": "Family Trip",
            "passenger_age": 35,
            "passenger_gender": "Female",
            "seats_booked": 3,
        },
    )
    assert book_resp.status_code == 201
    pnr = book_resp.json()["pnr"]

    after_book = client.get(f"/api/v1/trains/1/availability?journey_date={today}").json()["available_seats"]
    assert after_book == init_avail - 3

    cancel_resp = client.post(f"/api/v1/bookings/{pnr}/cancel", headers=headers)
    assert cancel_resp.status_code == 200
    cancel_data = cancel_resp.json()
    assert cancel_data["booking_status"] == "CANCELLED"
    assert cancel_data["seats_restored"] == 3

    after_cancel = client.get(f"/api/v1/trains/1/availability?journey_date={today}").json()["available_seats"]
    assert after_cancel == init_avail

    duplicate_cancel = client.post(f"/api/v1/bookings/{pnr}/cancel", headers=headers)
    assert duplicate_cancel.status_code == 400
    assert "already cancelled" in duplicate_cancel.json()["detail"]


def test_prevent_overbooking(client: TestClient):
    admin_token = get_token(client, "admin@railconnect.com", "Admin@12345")
    user_token = get_token(client, "passenger@railconnect.com", "Passenger@12345")
    specific_date = str(date.today() + timedelta(days=2))

    client.post(
        "/api/v1/admin/schedules",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "train_id": 1,
            "journey_date": specific_date,
            "total_seats": 1,
            "available_seats": 1,
            "fare": 750.0,
        },
    )

    first_book = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "train_id": 1,
            "journey_date": specific_date,
            "passenger_name": "First Passenger",
            "passenger_age": 30,
            "passenger_gender": "Male",
            "seats_booked": 1,
        },
    )
    assert first_book.status_code == 201

    second_book = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "train_id": 1,
            "journey_date": specific_date,
            "passenger_name": "Second Passenger",
            "passenger_age": 22,
            "passenger_gender": "Female",
            "seats_booked": 1,
        },
    )
    assert second_book.status_code == 400
    assert "Not enough seats available" in second_book.json()["detail"]
