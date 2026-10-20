from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, func, select

from app.database import get_session
from app.models import Booking, BookingStatus, Train, TrainSchedule
from app.schemas import TrainResponse, TrainSearchResult

router = APIRouter(prefix="/trains", tags=["Trains & Search"])


def get_available_seats_and_fare(session: Session, train: Train, journey_date: date) -> tuple[int, float]:
    """
    Calculate real-time seat availability and fare for a train on a given date.
    Looks up explicit TrainSchedule first; if none exists, calculates from
    train's total_seats minus active bookings.
    """
    schedule = session.exec(
        select(TrainSchedule).where(
            TrainSchedule.train_id == train.id,
            TrainSchedule.journey_date == journey_date,
        )
    ).first()

    if schedule:
        return schedule.available_seats, schedule.fare

    # Calculate dynamically if schedule wasn't explicitly initialized
    booked_count = session.exec(
        select(func.coalesce(func.sum(Booking.seats_booked), 0)).where(
            Booking.train_id == train.id,
            Booking.journey_date == journey_date,
            Booking.booking_status == BookingStatus.CONFIRMED,
        )
    ).one()

    available = max(0, train.total_seats - booked_count)
    return available, train.base_fare


@router.get("", response_model=List[TrainResponse])
def get_all_trains(
    active_only: bool = Query(True, description="Filter for active trains only"),
    session: Session = Depends(get_session),
):
    """Get list of trains in the railway system."""
    query = select(Train)
    if active_only:
        query = query.where(Train.is_active == True)
    trains = session.exec(query).all()
    return trains


@router.get("/search", response_model=List[TrainSearchResult])
def search_trains(
    source: str = Query(..., description="Starting station code (e.g. NDLS)"),
    destination: str = Query(..., description="Destination station code (e.g. CNB)"),
    journey_date: date = Query(..., description="Journey date in YYYY-MM-DD format"),
    session: Session = Depends(get_session),
):
    """
    Search for active trains between starting and destination stations on a journey date.
    Returns timings, fare, and real-time available seat count.
    """
    src = source.upper().strip()
    dst = destination.upper().strip()

    if src == dst:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and destination stations cannot be the same.",
        )

    # Validate that journey date is not in the past
    today = date.today()
    if journey_date < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Journey date cannot be in the past. Today is {today}.",
        )

    trains = session.exec(
        select(Train).where(
            Train.source_station_code == src,
            Train.destination_station_code == dst,
            Train.is_active == True,
        )
    ).all()

    results: List[TrainSearchResult] = []
    for train in trains:
        avail_seats, fare = get_available_seats_and_fare(session, train, journey_date)
        results.append(
            TrainSearchResult(
                train_id=train.id,
                train_number=train.train_number,
                train_name=train.train_name,
                source_station_code=train.source_station_code,
                destination_station_code=train.destination_station_code,
                departure_time=train.departure_time,
                arrival_time=train.arrival_time,
                journey_date=journey_date,
                total_seats=train.total_seats,
                available_seats=avail_seats,
                fare=fare,
                is_active=train.is_active,
            )
        )

    return results


@router.get("/{train_id}", response_model=TrainResponse)
def get_train_by_id(train_id: int, session: Session = Depends(get_session)):
    """Get details of a specific train by ID."""
    train = session.get(Train, train_id)
    if not train:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Train with ID {train_id} not found.",
        )
    return train


@router.get("/{train_id}/availability")
def check_seat_availability(
    train_id: int,
    journey_date: date = Query(..., description="Journey date in YYYY-MM-DD format"),
    session: Session = Depends(get_session),
):
    """Check seat availability and ticket fare for a specific train on a date."""
    train = session.get(Train, train_id)
    if not train:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Train with ID {train_id} not found.",
        )

    avail_seats, fare = get_available_seats_and_fare(session, train, journey_date)
    return {
        "train_id": train.id,
        "train_number": train.train_number,
        "train_name": train.train_name,
        "journey_date": journey_date,
        "total_seats": train.total_seats,
        "available_seats": avail_seats,
        "fare": fare,
        "status": "AVAILABLE" if avail_seats > 0 else "SOLD_OUT",
    }
