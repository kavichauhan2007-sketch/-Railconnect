from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ================= User & Auth Schemas =================
class UserRegister(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=6, max_length=100)
    role: Optional[str] = Field(default="passenger", description="Role: 'passenger' or 'admin'")


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    email: str


class TokenPayload(BaseModel):
    sub: str  # email
    role: str
    user_id: int
    exp: Optional[int] = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    new_password: Optional[str] = Field(None, min_length=6, max_length=100)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str
    reset_token: str
    expires_in_minutes: int


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str = Field(..., min_length=6, max_length=100)


# ================= Station Schemas =================
class StationCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=10, description="Station code, e.g. NDLS")
    name: str = Field(..., min_length=2, max_length=100, description="Station name, e.g. New Delhi")
    city: str
    state: str


class StationResponse(BaseModel):
    id: int
    code: str
    name: str
    city: str
    state: str

    model_config = ConfigDict(from_attributes=True)


# ================= Train Schemas =================
class TrainCreate(BaseModel):
    train_number: str = Field(..., min_length=3, max_length=20)
    train_name: str = Field(..., min_length=2, max_length=100)
    source_station_code: str
    destination_station_code: str
    departure_time: str = Field(..., description="Format HH:MM (24-hour), e.g. '06:10'")
    arrival_time: str = Field(..., description="Format HH:MM (24-hour), e.g. '11:20'")
    total_seats: int = Field(default=100, gt=0)
    base_fare: float = Field(default=500.0, gt=0)
    is_active: bool = True


class TrainUpdate(BaseModel):
    train_name: Optional[str] = None
    source_station_code: Optional[str] = None
    destination_station_code: Optional[str] = None
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    total_seats: Optional[int] = Field(None, gt=0)
    base_fare: Optional[float] = Field(None, gt=0)
    is_active: Optional[bool] = None


class TrainResponse(BaseModel):
    id: int
    train_number: str
    train_name: str
    source_station_code: str
    destination_station_code: str
    departure_time: str
    arrival_time: str
    total_seats: int
    base_fare: float
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ================= Schedule Schemas =================
class TrainScheduleCreate(BaseModel):
    train_id: int
    journey_date: date
    total_seats: int = Field(..., gt=0)
    available_seats: int = Field(..., ge=0)
    fare: float = Field(..., gt=0)


class TrainScheduleResponse(BaseModel):
    id: int
    train_id: int
    journey_date: date
    total_seats: int
    available_seats: int
    fare: float

    model_config = ConfigDict(from_attributes=True)


# ================= Train Search Schemas =================
class TrainSearchResult(BaseModel):
    train_id: int
    train_number: str
    train_name: str
    source_station_code: str
    destination_station_code: str
    departure_time: str
    arrival_time: str
    journey_date: date
    total_seats: int
    available_seats: int
    fare: float
    is_active: bool


# ================= Booking Schemas =================
class BookingCreate(BaseModel):
    train_id: int
    journey_date: date
    passenger_name: str = Field(..., min_length=2, max_length=100)
    passenger_age: int = Field(..., ge=1, le=120)
    passenger_gender: str = Field(..., description="'Male', 'Female', or 'Other'")
    berth_preference: Optional[str] = Field(default="LOWER")
    seats_booked: int = Field(default=1, ge=1, le=6)


class BookingResponse(BaseModel):
    id: int
    pnr: str
    user_id: int
    train_id: int
    train_number: Optional[str] = None
    train_name: Optional[str] = None
    source_station_code: Optional[str] = None
    destination_station_code: Optional[str] = None
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    journey_date: date
    seats_booked: int
    passenger_name: str
    passenger_age: int
    passenger_gender: str
    berth_preference: Optional[str] = None
    seat_number: Optional[str] = None
    total_fare: float
    payment_status: str
    booking_status: str
    booked_at: datetime
    cancelled_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BookingCancelResponse(BaseModel):
    message: str
    pnr: str
    booking_status: str
    seats_restored: int
    cancelled_at: datetime
