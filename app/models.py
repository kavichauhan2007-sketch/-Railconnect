from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional
from sqlmodel import Field, SQLModel


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    PASSENGER = "passenger"
    ADMIN = "admin"


class BookingStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, Enum):
    PAID = "PAID"
    REFUNDED = "REFUNDED"


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, nullable=False)
    full_name: str = Field(nullable=False)
    hashed_password: str = Field(nullable=False)
    role: str = Field(default=UserRole.PASSENGER)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=get_utc_now)


class TokenBlacklist(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(index=True, unique=True, nullable=False)
    blacklisted_at: datetime = Field(default_factory=get_utc_now)
    expires_at: datetime = Field(nullable=False)


class PasswordResetToken(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, nullable=False)
    token: str = Field(index=True, unique=True, nullable=False)
    expires_at: datetime = Field(nullable=False)
    is_used: bool = Field(default=False)
    created_at: datetime = Field(default_factory=get_utc_now)


class Station(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True, nullable=False)
    name: str = Field(nullable=False)
    city: str = Field(nullable=False)
    state: str = Field(nullable=False)


class Train(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    train_number: str = Field(index=True, unique=True, nullable=False)
    train_name: str = Field(nullable=False)
    source_station_code: str = Field(index=True, nullable=False)
    destination_station_code: str = Field(index=True, nullable=False)
    departure_time: str = Field(nullable=False)
    arrival_time: str = Field(nullable=False)
    total_seats: int = Field(default=100, nullable=False)
    base_fare: float = Field(default=500.0, nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(default_factory=get_utc_now)


class TrainSchedule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    train_id: int = Field(foreign_key="train.id", index=True, nullable=False)
    journey_date: date = Field(index=True, nullable=False)
    total_seats: int = Field(nullable=False)
    available_seats: int = Field(nullable=False)
    fare: float = Field(nullable=False)


class Booking(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    pnr: str = Field(index=True, unique=True, nullable=False)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    train_id: int = Field(foreign_key="train.id", index=True, nullable=False)
    journey_date: date = Field(index=True, nullable=False)
    seats_booked: int = Field(default=1, nullable=False)
    passenger_name: str = Field(nullable=False)
    passenger_age: int = Field(nullable=False)
    passenger_gender: str = Field(nullable=False)
    berth_preference: Optional[str] = Field(default="LOWER")
    seat_number: Optional[str] = Field(default=None)
    total_fare: float = Field(nullable=False)
    payment_status: str = Field(default=PaymentStatus.PAID)
    booking_status: str = Field(default=BookingStatus.CONFIRMED)
    booked_at: datetime = Field(default_factory=get_utc_now)
    cancelled_at: Optional[datetime] = Field(default=None)
