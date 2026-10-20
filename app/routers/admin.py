from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.auth import get_current_admin
from app.database import get_session
from app.models import Booking, Station, Train, TrainSchedule, User
from app.schemas import (
    BookingResponse,
    StationCreate,
    StationResponse,
    TrainCreate,
    TrainResponse,
    TrainScheduleCreate,
    TrainScheduleResponse,
    TrainUpdate,
)

router = APIRouter(prefix="/admin", tags=["Admin Operations"])


# ================= Station Management =================
@router.post("/stations", response_model=StationResponse, status_code=status.HTTP_201_CREATED)
def create_station(
    station_in: StationCreate,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """Add a new railway station. Admin only."""
    code = station_in.code.upper().strip()
    existing = session.exec(select(Station).where(Station.code == code)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Station with code '{code}' already exists.",
        )
    station = Station(
        code=code,
        name=station_in.name.strip(),
        city=station_in.city.strip(),
        state=station_in.state.strip(),
    )
    session.add(station)
    session.commit()
    session.refresh(station)
    return station


@router.get("/stations", response_model=List[StationResponse])
def list_stations(
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """List all stations. Admin only."""
    stations = session.exec(select(Station)).all()
    return stations


# ================= Train Management =================
@router.post("/trains", response_model=TrainResponse, status_code=status.HTTP_201_CREATED)
def create_train(
    train_in: TrainCreate,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """
    Add a new train with route, timings, fare, and total seats.
    Admin only.
    """
    train_number = train_in.train_number.strip()
    existing = session.exec(select(Train).where(Train.train_number == train_number)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Train with number '{train_number}' already exists.",
        )

    # Validate stations exist (or create if needed for fictional flexibility)
    src_code = train_in.source_station_code.upper().strip()
    dst_code = train_in.destination_station_code.upper().strip()

    if src_code == dst_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and destination stations cannot be the same.",
        )

    train = Train(
        train_number=train_number,
        train_name=train_in.train_name.strip(),
        source_station_code=src_code,
        destination_station_code=dst_code,
        departure_time=train_in.departure_time.strip(),
        arrival_time=train_in.arrival_time.strip(),
        total_seats=train_in.total_seats,
        base_fare=train_in.base_fare,
        is_active=train_in.is_active,
    )
    session.add(train)
    session.commit()
    session.refresh(train)
    return train


@router.put("/trains/{train_id}", response_model=TrainResponse)
def update_train(
    train_id: int,
    train_update: TrainUpdate,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """Update train information, routes, timings, seats, or fare. Admin only."""
    train = session.get(Train, train_id)
    if not train:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Train with ID {train_id} not found.",
        )

    update_dict = train_update.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        if key in ["source_station_code", "destination_station_code"] and value:
            setattr(train, key, value.upper().strip())
        else:
            setattr(train, key, value)

    session.add(train)
    session.commit()
    session.refresh(train)
    return train


@router.patch("/trains/{train_id}/deactivate", response_model=TrainResponse)
def deactivate_train(
    train_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """Deactivate a train. Inactive trains will not appear in search results. Admin only."""
    train = session.get(Train, train_id)
    if not train:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Train with ID {train_id} not found.",
        )
    train.is_active = False
    session.add(train)
    session.commit()
    session.refresh(train)
    return train


@router.patch("/trains/{train_id}/activate", response_model=TrainResponse)
def activate_train(
    train_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """Reactivate a train. Admin only."""
    train = session.get(Train, train_id)
    if not train:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Train with ID {train_id} not found.",
        )
    train.is_active = True
    session.add(train)
    session.commit()
    session.refresh(train)
    return train


# ================= Schedule / Seat Availability =================
@router.post("/schedules", response_model=TrainScheduleResponse, status_code=status.HTTP_201_CREATED)
def set_train_schedule(
    schedule_in: TrainScheduleCreate,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """
    Set or update seat availability and fare for a specific train and date.
    Admin only.
    """
    train = session.get(Train, schedule_in.train_id)
    if not train:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Train with ID {schedule_in.train_id} not found.",
        )

    # Check if a schedule already exists for this train on this journey date
    existing_schedule = session.exec(
        select(TrainSchedule).where(
            TrainSchedule.train_id == schedule_in.train_id,
            TrainSchedule.journey_date == schedule_in.journey_date,
        )
    ).first()

    if existing_schedule:
        existing_schedule.total_seats = schedule_in.total_seats
        existing_schedule.available_seats = schedule_in.available_seats
        existing_schedule.fare = schedule_in.fare
        session.add(existing_schedule)
        session.commit()
        session.refresh(existing_schedule)
        return existing_schedule

    schedule = TrainSchedule(
        train_id=schedule_in.train_id,
        journey_date=schedule_in.journey_date,
        total_seats=schedule_in.total_seats,
        available_seats=schedule_in.available_seats,
        fare=schedule_in.fare,
    )
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return schedule


# ================= Booking Oversight =================
@router.get("/bookings", response_model=List[BookingResponse])
def view_all_bookings(
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """View all booking records across the system. Admin only."""
    bookings = session.exec(select(Booking).order_by(Booking.booked_at.desc())).all()
    # Enrich response with train details
    result = []
    for b in bookings:
        train = session.get(Train, b.train_id)
        b_dict = b.model_dump()
        if train:
            b_dict.update({
                "train_number": train.train_number,
                "train_name": train.train_name,
                "source_station_code": train.source_station_code,
                "destination_station_code": train.destination_station_code,
                "departure_time": train.departure_time,
                "arrival_time": train.arrival_time,
            })
        result.append(BookingResponse(**b_dict))
    return result
