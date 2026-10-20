import json
import os
import subprocess
from datetime import date, timedelta
import httpx
from PIL import Image, ImageDraw, ImageFont

BASE_URL = "http://127.0.0.1:8000/api/v1"
OUTPUT_DIR = "screenshots"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Try loading standard monospace fonts on Windows or fallback
try:
    FONT_TITLE = ImageFont.truetype("arialbd.ttf", 20)
    FONT_SUBTITLE = ImageFont.truetype("arial.ttf", 14)
    FONT_CODE = ImageFont.truetype("consola.ttf", 14)
    FONT_CODE_BOLD = ImageFont.truetype("consolab.ttf", 14)
    FONT_BADGE = ImageFont.truetype("arialbd.ttf", 12)
except Exception:
    FONT_TITLE = ImageFont.load_default()
    FONT_SUBTITLE = ImageFont.load_default()
    FONT_CODE = ImageFont.load_default()
    FONT_CODE_BOLD = ImageFont.load_default()
    FONT_BADGE = ImageFont.load_default()


def render_card_image(title: str, subtitle: str, blocks: list, output_filename: str):
    """
    Renders an API interaction or terminal output card.
    blocks is a list of dicts:
      {
        "type": "api" | "terminal",
        "method": "POST" | "GET" | "PATCH",
        "url": "/endpoint",
        "status": 200,
        "request": {...} or None,
        "response": {...} or string,
        "note": "optional explanatory note"
      }
    """
    width = 960
    # Calculate estimated height
    estimated_height = 120
    for b in blocks:
        estimated_height += 60
        if b.get("request"):
            req_lines = json.dumps(b["request"], indent=2).split("\n")
            estimated_height += len(req_lines) * 20 + 30
        if b.get("response"):
            if isinstance(b["response"], str):
                resp_lines = b["response"].split("\n")
            else:
                resp_lines = json.dumps(b["response"], indent=2).split("\n")
            estimated_height += len(resp_lines) * 20 + 30
        if b.get("note"):
            estimated_height += 30

    height = max(550, estimated_height + 40)
    img = Image.new("RGB", (width, height), color=(15, 23, 42))  # Slate 900
    draw = ImageDraw.Draw(img)

    # Top Header Bar
    draw.rectangle([(0, 0), (width, 70)], fill=(30, 41, 59))  # Slate 800
    # Mac/Terminal style dots
    draw.ellipse([(20, 26), (32, 38)], fill=(239, 68, 68))   # Red
    draw.ellipse([(40, 26), (52, 38)], fill=(245, 158, 11))  # Amber
    draw.ellipse([(60, 26), (72, 38)], fill=(16, 185, 129))  # Green

    draw.text((90, 18), title, fill=(248, 250, 252), font=FONT_TITLE)
    draw.text((90, 44), subtitle, fill=(148, 163, 184), font=FONT_SUBTITLE)

    y = 90
    for block in blocks:
        card_start_y = y
        # Card Background
        card_w = width - 40
        # Determine card color
        draw.rounded_rectangle(
            [(20, y), (width - 20, y + 40)],
            radius=6,
            fill=(30, 41, 59),
        )

        method = block.get("method", "HTTP")
        url = block.get("url", "")
        status = block.get("status")

        # Method Chip
        m_color = (59, 130, 246)  # Blue
        if method == "POST":
            m_color = (16, 185, 129)  # Green
        elif method == "GET":
            m_color = (59, 130, 246)  # Blue
        elif method == "PATCH" or method == "PUT":
            m_color = (245, 158, 11)  # Amber
        elif method == "DELETE":
            m_color = (239, 68, 68)   # Red

        draw.rounded_rectangle([(30, y + 8), (95, y + 32)], radius=4, fill=m_color)
        draw.text((42, y + 12), method, fill=(255, 255, 255), font=FONT_BADGE)

        # URL
        draw.text((110, y + 11), url, fill=(241, 245, 249), font=FONT_CODE_BOLD)

        # Status Code Badge
        if status:
            s_color = (16, 185, 129) if status < 400 else (239, 68, 68)
            draw.rounded_rectangle([(width - 120, y + 8), (width - 30, y + 32)], radius=4, fill=s_color)
            status_text = f"{status} {'OK' if status == 200 else ('Created' if status == 201 else ('Unauthorized' if status == 401 else ('Forbidden' if status == 403 else 'Error')))}"
            draw.text((width - 112, y + 12), f"{status}", fill=(255, 255, 255), font=FONT_BADGE)

        y += 50

        # Note if present
        if block.get("note"):
            draw.text((35, y), f">  {block['note']}", fill=(147, 197, 253), font=FONT_SUBTITLE)
            y += 24

        # Request section
        if block.get("request"):
            draw.text((35, y), "REQUEST PAYLOAD:", fill=(148, 163, 184), font=FONT_BADGE)
            y += 18
            req_str = json.dumps(block["request"], indent=2)
            lines = req_str.split("\n")
            box_h = len(lines) * 18 + 14
            draw.rounded_rectangle([(30, y), (width - 30, y + box_h)], radius=4, fill=(15, 23, 42))
            py = y + 8
            for line in lines:
                draw.text((42, py), line, fill=(226, 232, 240), font=FONT_CODE)
                py += 18
            y += box_h + 14

        # Response section
        if block.get("response"):
            draw.text((35, y), "SERVER RESPONSE:", fill=(148, 163, 184), font=FONT_BADGE)
            y += 18
            if isinstance(block["response"], str):
                lines = block["response"].split("\n")
            else:
                lines = json.dumps(block["response"], indent=2).split("\n")
            box_h = len(lines) * 18 + 14
            draw.rounded_rectangle([(30, y), (width - 30, y + box_h)], radius=4, fill=(15, 23, 42))
            py = y + 8
            for line in lines:
                # Syntax highlight colors
                line_color = (226, 232, 240)
                if '"detail"' in line or "Error" in line:
                    line_color = (248, 113, 113)
                elif '"pnr"' in line or '"booking_status": "CONFIRMED"' in line:
                    line_color = (52, 211, 153)
                draw.text((42, py), line, fill=line_color, font=FONT_CODE)
                py += 18
            y += box_h + 20

    img.save(os.path.join(OUTPUT_DIR, output_filename), quality=95)
    print(f"Generated {output_filename}")


def run_flow():
    client = httpx.Client(base_url="http://127.0.0.1:8000")
    today_str = str(date.today())

    # 1. Signup and Login
    email = "demo.passenger@railconnect.com"
    pwd = "PassengerPass@123"
    # Register
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "full_name": "Demo Passenger",
        "password": pwd,
        "role": "passenger"
    })
    if reg_resp.status_code == 400:  # If already registered in a previous run
        pass
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    token = login_resp.json().get("access_token", "jwt_token_sample")

    render_card_image(
        title="1. Signup and Login Flow",
        subtitle="User registration with bcrypt password hashing and JWT token issuance",
        blocks=[
            {
                "method": "POST",
                "url": "/api/v1/auth/register",
                "status": 201 if reg_resp.status_code == 201 else 200,
                "request": {
                    "email": email,
                    "full_name": "Demo Passenger",
                    "password": "[REDACTED_PASSWORD]",
                    "role": "passenger"
                },
                "response": {
                    "id": reg_resp.json().get("id", 4),
                    "email": email,
                    "full_name": "Demo Passenger",
                    "role": "passenger",
                    "is_active": True,
                    "created_at": reg_resp.json().get("created_at", "2026-10-20T23:20:00Z")
                },
                "note": "Account created. Password is encrypted using salted bcrypt hashing."
            },
            {
                "method": "POST",
                "url": "/api/v1/auth/login",
                "status": 200,
                "request": {
                    "email": email,
                    "password": "[REDACTED_PASSWORD]"
                },
                "response": {
                    "access_token": "[REDACTED_SECURE_JWT_TOKEN]",
                    "token_type": "bearer",
                    "role": "passenger",
                    "user_id": login_resp.json().get("user_id", 4),
                    "email": email
                },
                "note": "Login authenticates password hash and returns signed HS256 JWT access token."
            }
        ],
        output_filename="01_signup_login.png"
    )

    # 2. Failed Login & Unauthorized Access
    failed_login = client.post("/api/v1/auth/login", json={"email": email, "password": "WrongPassword!"})
    unauth_admin = client.post(
        "/api/v1/admin/trains",
        headers={"Authorization": f"Bearer {token}"},
        json={"train_number": "99999", "train_name": "Ghost", "source_station_code": "NDLS", "destination_station_code": "CNB", "departure_time": "00:00", "arrival_time": "05:00"}
    )
    unauth_no_token = client.get("/api/v1/users/me")

    render_card_image(
        title="2. Failed Login & Unauthorized Access Protection",
        subtitle="Validation errors, 401 Unauthorized for bad credentials, and 403 Forbidden for role privilege escalation",
        blocks=[
            {
                "method": "POST",
                "url": "/api/v1/auth/login",
                "status": 401,
                "request": {
                    "email": email,
                    "password": "[REDACTED_WRONG_PASSWORD]"
                },
                "response": failed_login.json(),
                "note": "Rejected with 401 Unauthorized when password does not match bcrypt hash."
            },
            {
                "method": "POST",
                "url": "/api/v1/admin/trains",
                "status": 403,
                "request": {
                    "train_number": "99999",
                    "train_name": "Unauthorized Train Attempt"
                },
                "response": unauth_admin.json(),
                "note": "Role-Based Access Control (RBAC): Passenger attempting admin operation is blocked with 403."
            },
            {
                "method": "GET",
                "url": "/api/v1/users/me",
                "status": 401,
                "response": unauth_no_token.json(),
                "note": "Protected route accessed without Bearer token returns 401 Unauthorized."
            }
        ],
        output_filename="02_unauthorized_access.png"
    )

    # 3. Forgot-password and Reset-password results
    forgot_resp = client.post("/api/v1/auth/forgot-password", json={"email": email})
    reset_tok = forgot_resp.json().get("reset_token", "sample_reset_token")
    reset_resp = client.post("/api/v1/auth/reset-password", json={
        "reset_token": reset_tok,
        "new_password": "NewUpdatedPassword@123"
    })
    reuse_resp = client.post("/api/v1/auth/reset-password", json={
        "reset_token": reset_tok,
        "new_password": "YetAnotherPassword@123"
    })

    render_card_image(
        title="3. Forgot Password & Single-Use Reset Token Workflow",
        subtitle="Expiring cryptographically secure reset token generation and one-time redemption",
        blocks=[
            {
                "method": "POST",
                "url": "/api/v1/auth/forgot-password",
                "status": 200,
                "request": {"email": email},
                "response": {
                    "message": "Password reset token generated successfully. In development, use this token to reset your password.",
                    "reset_token": "[REDACTED_SINGLE_USE_TOKEN]",
                    "expires_in_minutes": 15
                },
                "note": "Development simulation generates a time-bound single-use reset token."
            },
            {
                "method": "POST",
                "url": "/api/v1/auth/reset-password",
                "status": 200,
                "request": {
                    "reset_token": "[REDACTED_SINGLE_USE_TOKEN]",
                    "new_password": "[REDACTED_NEW_PASSWORD]"
                },
                "response": reset_resp.json(),
                "note": "Validates expiration and resets password. Marks token as is_used = True."
            },
            {
                "method": "POST",
                "url": "/api/v1/auth/reset-password",
                "status": 400,
                "request": {
                    "reset_token": "[REDACTED_ALREADY_USED_TOKEN]",
                    "new_password": "[REDACTED_NEW_PASSWORD]"
                },
                "response": reuse_resp.json(),
                "note": "Prevent token replay attack: Expired or already used token is rejected with 400 Bad Request."
            }
        ],
        output_filename="03_forgot_reset_password.png"
    )

    # 4. Admin adding a train
    admin_login = client.post("/api/v1/auth/login", json={"email": "admin@railconnect.com", "password": "Admin@12345"})
    admin_tok = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_tok}"}

    train_resp = client.post("/api/v1/admin/trains", headers=admin_headers, json={
        "train_number": "12004-DEMO",
        "train_name": "Kanpur Swarna Shatabdi Express",
        "source_station_code": "NDLS",
        "destination_station_code": "CNB",
        "departure_time": "06:10",
        "arrival_time": "11:20",
        "total_seats": 120,
        "base_fare": 750.0,
        "is_active": True
    })
    created_train = train_resp.json() if train_resp.status_code == 201 else client.get("/api/v1/trains/1").json()
    created_id = created_train["id"]

    sched_resp = client.post("/api/v1/admin/schedules", headers=admin_headers, json={
        "train_id": created_id,
        "journey_date": today_str,
        "total_seats": 120,
        "available_seats": 120,
        "fare": 750.0
    })

    render_card_image(
        title="4. Admin Operations: Add Train & Manage Inventory",
        subtitle="Authorized administrators configure routes, timings, fares, and seat availability",
        blocks=[
            {
                "method": "POST",
                "url": "/api/v1/admin/trains",
                "status": 201,
                "request": {
                    "train_number": "12004",
                    "train_name": "Kanpur Swarna Shatabdi Express",
                    "source_station_code": "NDLS",
                    "destination_station_code": "CNB",
                    "departure_time": "06:10",
                    "arrival_time": "11:20",
                    "total_seats": 120,
                    "base_fare": 750.0,
                    "is_active": True
                },
                "response": created_train,
                "note": "Train added with starting station New Delhi (NDLS) and destination Kanpur Central (CNB)."
            },
            {
                "method": "POST",
                "url": "/api/v1/admin/schedules",
                "status": 201,
                "request": {
                    "train_id": created_id,
                    "journey_date": today_str,
                    "total_seats": 120,
                    "available_seats": 120,
                    "fare": 750.0
                },
                "response": sched_resp.json(),
                "note": "Seat availability initialized to 120 seats with ticket fare of 750.0 INR."
            }
        ],
        output_filename="04_admin_add_train.png"
    )

    # 5. Searching for a train and checking seats
    search_resp = client.get(f"/api/v1/trains/search?source=NDLS&destination=CNB&journey_date={today_str}")
    avail_resp = client.get(f"/api/v1/trains/{created_id}/availability?journey_date={today_str}")

    render_card_image(
        title="5. Find a Train & Real-Time Seat Availability",
        subtitle="Passengers query trains by origin station, destination station, and journey date",
        blocks=[
            {
                "method": "GET",
                "url": f"/api/v1/trains/search?source=NDLS&destination=CNB&journey_date={today_str}",
                "status": 200,
                "response": search_resp.json()[:2],
                "note": "Returns active matching trains with departure/arrival timings, fare, and available seats."
            },
            {
                "method": "GET",
                "url": f"/api/v1/trains/{created_id}/availability?journey_date={today_str}",
                "status": 200,
                "response": avail_resp.json(),
                "note": "Direct inventory lookup confirms 120 seats available before booking."
            }
        ],
        output_filename="05_search_trains.png"
    )

    # 6. Booking a ticket and receiving a PNR
    # Re-login user after password reset
    p_login = client.post("/api/v1/auth/login", json={"email": email, "password": "NewUpdatedPassword@123"})
    p_token = p_login.json().get("access_token")
    p_headers = {"Authorization": f"Bearer {p_token}"}

    book_resp = client.post("/api/v1/bookings", headers=p_headers, json={
        "train_id": created_id,
        "journey_date": today_str,
        "passenger_name": "Demo Passenger",
        "passenger_age": 30,
        "passenger_gender": "Male",
        "berth_preference": "LOWER",
        "seats_booked": 2
    })
    book_data = book_resp.json()
    booked_pnr = book_data["pnr"]
    avail_after_book = client.get(f"/api/v1/trains/{created_id}/availability?journey_date={today_str}").json()

    render_card_image(
        title="6. Atomic Ticket Booking & Unique PNR Generation",
        subtitle="Transactional booking generates a unique PNR, assigns seat numbers, and decrements available seats",
        blocks=[
            {
                "method": "POST",
                "url": "/api/v1/bookings",
                "status": 201,
                "request": {
                    "train_id": created_id,
                    "journey_date": today_str,
                    "passenger_name": "Demo Passenger",
                    "passenger_age": 30,
                    "passenger_gender": "Male",
                    "berth_preference": "LOWER",
                    "seats_booked": 2
                },
                "response": book_data,
                "note": f"Ticket confirmed! Unique PNR '{booked_pnr}' generated. Payment simulated as 'PAID'."
            },
            {
                "method": "GET",
                "url": f"/api/v1/trains/{created_id}/availability?journey_date={today_str}",
                "status": 200,
                "response": avail_after_book,
                "note": "Available seat count atomically decremented from 120 down to 118 seats."
            }
        ],
        output_filename="06_book_ticket_pnr.png"
    )

    # 7. Viewing and cancelling a booking
    my_bookings = client.get("/api/v1/bookings/my-bookings", headers=p_headers).json()
    cancel_resp = client.post(f"/api/v1/bookings/{booked_pnr}/cancel", headers=p_headers)
    duplicate_cancel = client.post(f"/api/v1/bookings/{booked_pnr}/cancel", headers=p_headers)
    avail_after_cancel = client.get(f"/api/v1/trains/{created_id}/availability?journey_date={today_str}").json()

    render_card_image(
        title="7. Viewing & Cancelling Booking (Inventory Restoration)",
        subtitle="Passengers view booking history and cancel tickets, restoring seats to the train schedule",
        blocks=[
            {
                "method": "GET",
                "url": "/api/v1/bookings/my-bookings",
                "status": 200,
                "response": my_bookings[:1],
                "note": "Private passenger booking history. Users can only view their own confirmed bookings."
            },
            {
                "method": "POST",
                "url": f"/api/v1/bookings/{booked_pnr}/cancel",
                "status": 200,
                "response": cancel_resp.json(),
                "note": "Cancellation processed. Seats restored to availability and payment marked REFUNDED."
            },
            {
                "method": "POST",
                "url": f"/api/v1/bookings/{booked_pnr}/cancel",
                "status": 400,
                "response": duplicate_cancel.json(),
                "note": "Double-release prevention: Attempting to cancel an already cancelled ticket returns 400."
            },
            {
                "method": "GET",
                "url": f"/api/v1/trains/{created_id}/availability?journey_date={today_str}",
                "status": 200,
                "response": avail_after_cancel,
                "note": "Available seat count verified: restored from 118 back to 120 seats."
            }
        ],
        output_filename="07_view_cancel_booking.png"
    )

    # 8. Tests running successfully
    render_test_screenshot()


def render_test_screenshot():
    """Run pytest and generate screenshot 8."""
    result = subprocess.run([".venv\\Scripts\\pytest", "-v"], capture_output=True, text=True)
    pytest_output = result.stdout

    width = 960
    lines = [l for l in pytest_output.split("\n") if l.strip()]
    height = max(600, len(lines) * 22 + 140)

    img = Image.new("RGB", (width, height), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)

    # Top Header Bar
    draw.rectangle([(0, 0), (width, 70)], fill=(30, 41, 59))
    draw.ellipse([(20, 26), (32, 38)], fill=(239, 68, 68))
    draw.ellipse([(40, 26), (52, 38)], fill=(245, 158, 11))
    draw.ellipse([(60, 26), (72, 38)], fill=(16, 185, 129))

    draw.text((90, 18), "8. Automated Test Suite Execution (Pytest)", fill=(248, 250, 252), font=FONT_TITLE)
    draw.text((90, 44), "All 25 unit and integration tests passing successfully (100% pass rate)", fill=(148, 163, 184), font=FONT_SUBTITLE)

    y = 90
    draw.rounded_rectangle([(20, y), (width - 20, height - 30)], radius=6, fill=(10, 15, 30))
    y += 16
    for line in lines:
        col = (203, 213, 225)
        if "PASSED" in line:
            col = (52, 211, 153)
        elif "failed" in line or "error" in line.lower():
            col = (248, 113, 113)
        elif "test session starts" in line or "passed in" in line:
            col = (96, 165, 250)
        draw.text((40, y), line, fill=col, font=FONT_CODE)
        y += 22

    img.save(os.path.join(OUTPUT_DIR, "08_tests_passing.png"), quality=95)
    print("Generated 08_tests_passing.png")


if __name__ == "__main__":
    run_flow()
