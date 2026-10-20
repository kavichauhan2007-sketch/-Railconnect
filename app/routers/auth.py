from datetime import datetime, timedelta, timezone
import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import Session, select

from app.auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
    security,
    verify_password,
)
from app.config import settings
from app.database import get_session
from app.models import PasswordResetToken, TokenBlacklist, User, UserRole
from app.schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    Token,
    UserLogin,
    UserRegister,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegister, session: Session = Depends(get_session)):
    existing_user = session.exec(select(User).where(User.email == user_in.email)).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    role = (user_in.role or "passenger").lower()
    if role not in [UserRole.PASSENGER, UserRole.ADMIN]:
        role = UserRole.PASSENGER

    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        role=role,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(login_data: UserLogin, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == login_data.email)).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Contact administration.",
        )

    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": user.id})
    return Token(
        access_token=token,
        token_type="bearer",
        role=user.role,
        user_id=user.id,
        email=user.email,
    )


@router.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    token = credentials.credentials
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    session.add(TokenBlacklist(token=token, expires_at=expires_at))
    session.commit()
    return {"message": "Successfully logged out. Token has been revoked and can no longer be used."}


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(request: ForgotPasswordRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == request.email)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found registered with this email address.",
        )

    reset_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)

    db_token = PasswordResetToken(
        email=user.email,
        token=reset_token,
        expires_at=expires_at,
        is_used=False,
    )
    session.add(db_token)
    session.commit()

    return ForgotPasswordResponse(
        message="Password reset token generated successfully. In development, use this token to reset your password.",
        reset_token=reset_token,
        expires_in_minutes=settings.RESET_TOKEN_EXPIRE_MINUTES,
    )


@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest, session: Session = Depends(get_session)):
    db_token = session.exec(
        select(PasswordResetToken).where(PasswordResetToken.token == request.reset_token)
    ).first()

    if not db_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid password reset token.")

    if db_token.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset token has already been used. Please request a new one.",
        )

    now = datetime.now(timezone.utc)
    token_expiry = db_token.expires_at
    if token_expiry.tzinfo is None:
        token_expiry = token_expiry.replace(tzinfo=timezone.utc)

    if now > token_expiry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset token has expired. Please request a new one.",
        )

    user = session.exec(select(User).where(User.email == db_token.email)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated user account not found.")

    user.hashed_password = get_password_hash(request.new_password)
    db_token.is_used = True

    session.add(user)
    session.add(db_token)
    session.commit()

    return {"message": "Password has been successfully reset. You can now log in with your new password."}
