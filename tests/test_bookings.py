from datetime import date, timedelta
from fastapi.testclient import TestClient


def get_token(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_book_ticket_success(client: TestClient):
    token = get_token(client, "passenger@railconnect.com", "Passenger@12345")
    headers = {"Authorization": f"Bearer {token}"}
    today = str(date.today())

    # 1. Book a ticket for Shatabdi Express (train 1)
    book_resp = client.post(
        "/api/v1/bookings",
        headers=headers,
        json={
            "train_id": 1,
            "journey_date": today,
            "passenger_name": "Kavish Passenger",
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

    # 2. Check seat inventory decreased from 50 to 48
    avail_resp = client.get(f"/api/v1/trains/1/availability?journey_date={today}")
    assert avail_resp.json()["available_seats"] == 48


def test_booking_history_privacy(client: TestClient):
    token1 = get_token(client, "passenger@railconnect.com", "Passenger@12345")
    token2 = get_token(client, "passenger2@railconnect.com", "Passenger@12345")
    today = str(date.today())

    # Passenger 1 books a ticket
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

    # Passenger 2 checks their booking history -> should be empty
    history2 = client.get(
        "/api/v1/bookings/my-bookings",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert history2.status_code == 200
    assert len(history2.json()) == 0

    # Passenger 1 checks their booking history -> contains at least 1 booking
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

    # 1. Passenger 1 books a ticket
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

    # 2. Passenger 1 accesses their own ticket -> success
    resp1 = client.get(f"/api/v1/bookings/{pnr}", headers={"Authorization": f"Bearer {token1}"})
    assert resp1.status_code == 200
    assert resp1.json()["pnr"] == pnr

    # 3. Passenger 2 tries to access Passenger 1's ticket -> 403 Forbidden
    resp2 = client.get(f"/api/v1/bookings/{pnr}", headers={"Authorization": f"Bearer {token2}"})
    assert resp2.status_code == 403
    assert "You can only view your own bookings" in resp2.json()["detail"]


def test_ticket_cancellation_and_seat_restoration(client: TestClient):
    token = get_token(client, "passenger@railconnect.com", "Passenger@12345")
    headers = {"Authorization": f"Bearer {token}"}
    today = str(date.today())

    # 1. Check initial seats
    init_avail = client.get(f"/api/v1/trains/1/availability?journey_date={today}").json()["available_seats"]

    # 2. Book 3 seats
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

    # Check seats decreased
    after_book = client.get(f"/api/v1/trains/1/availability?journey_date={today}").json()["available_seats"]
    assert after_book == init_avail - 3

    # 3. Cancel the booking
    cancel_resp = client.post(f"/api/v1/bookings/{pnr}/cancel", headers=headers)
    assert cancel_resp.status_code == 200
    cancel_data = cancel_resp.json()
    assert cancel_data["booking_status"] == "CANCELLED"
    assert cancel_data["seats_restored"] == 3

    # Check seats restored
    after_cancel = client.get(f"/api/v1/trains/1/availability?journey_date={today}").json()["available_seats"]
    assert after_cancel == init_avail

    # 4. Attempt to cancel again -> must fail with 400
    duplicate_cancel = client.post(f"/api/v1/bookings/{pnr}/cancel", headers=headers)
    assert duplicate_cancel.status_code == 400
    assert "already cancelled" in duplicate_cancel.json()["detail"]


def test_prevent_overbooking(client: TestClient):
    admin_token = get_token(client, "admin@railconnect.com", "Admin@12345")
    user_token = get_token(client, "passenger@railconnect.com", "Passenger@12345")
    specific_date = str(date.today() + timedelta(days=2))

    # 1. Admin sets available seats to 1 for this date
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

    # 2. User books the 1 seat
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

    # 3. Second user tries to book -> must fail with 400 Bad Request
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
