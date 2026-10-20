from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.auth import get_current_user, get_password_hash
from app.database import get_session
from app.models import User
from app.schemas import UserProfileUpdate, UserResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def get_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get profile of the currently authenticated user.
    Users can only view their own profile.
    """
    return current_user


@router.put("/me", response_model=UserResponse)
def update_user_profile(
    update_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Update profile of the currently authenticated user.
    """
    if update_data.full_name is not None:
        current_user.full_name = update_data.full_name
    if update_data.new_password is not None:
        current_user.hashed_password = get_password_hash(update_data.new_password)

    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user
