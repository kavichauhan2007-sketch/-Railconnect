import pytest
from fastapi.testclient import TestClient


def test_user_registration_success(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "full_name": "New Passenger",
            "password": "SecurePassword123",
            "role": "passenger",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["full_name"] == "New Passenger"
    assert data["role"] == "passenger"
    assert "hashed_password" not in data


def test_user_registration_duplicate_email(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "passenger@railconnect.com",
            "full_name": "Duplicate User",
            "password": "Password123",
            "role": "passenger",
        },
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_login_success(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "passenger@railconnect.com",
            "password": "Passenger@12345",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "passenger"


def test_login_invalid_password(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "passenger@railconnect.com",
            "password": "WrongPassword",
        },
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_profile_requires_auth(client: TestClient):
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401


def test_profile_with_valid_token(client: TestClient):
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "passenger@railconnect.com", "password": "Passenger@12345"},
    )
    token = login_resp.json()["access_token"]

    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "passenger@railconnect.com"


def test_logout_and_token_revocation(client: TestClient):
    # 1. Log in to get token
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "passenger@railconnect.com", "password": "Passenger@12345"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Verify token works
    assert client.get("/api/v1/users/me", headers=headers).status_code == 200

    # 3. Log out to blacklist token
    logout_resp = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == 200
    assert "revoked" in logout_resp.json()["message"]

    # 4. Attempt to use revoked token -> must fail with 401 Unauthorized
    revoked_resp = client.get("/api/v1/users/me", headers=headers)
    assert revoked_resp.status_code == 401
    assert "revoked" in revoked_resp.json()["detail"]


def test_forgot_and_reset_password_flow(client: TestClient):
    # 1. Request forgot password
    forgot_resp = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "passenger@railconnect.com"},
    )
    assert forgot_resp.status_code == 200
    reset_token = forgot_resp.json()["reset_token"]
    assert reset_token is not None

    # 2. Reset password using the token
    reset_resp = client.post(
        "/api/v1/auth/reset-password",
        json={
            "reset_token": reset_token,
            "new_password": "NewSecurePassword456",
        },
    )
    assert reset_resp.status_code == 200
    assert "successfully reset" in reset_resp.json()["message"]

    # 3. Try to use the same token again -> should fail
    reuse_resp = client.post(
        "/api/v1/auth/reset-password",
        json={
            "reset_token": reset_token,
            "new_password": "AnotherPassword789",
        },
    )
    assert reuse_resp.status_code == 400
    assert "already been used" in reuse_resp.json()["detail"]

    # 4. Log in with the new password
    login_new = client.post(
        "/api/v1/auth/login",
        json={"email": "passenger@railconnect.com", "password": "NewSecurePassword456"},
    )
    assert login_new.status_code == 200
