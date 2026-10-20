from datetime import date, datetime, timezone
import random
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth import get_current_user
from app.database import get_session
from app.models import (
    Booking,
    BookingStatus,
    PaymentStatus,
    Train,
    TrainSchedule,
    User,
    UserRole,
)
from app.schemas import BookingCancelResponse, BookingCreate, BookingResponse

router = APIRouter(prefix="/bookings", tags=["bookings"])


def generate_unique_pnr(session: Session) -> str:
    while True:
        pnr = f"RC{random.randint(10000000, 99999999)}"
        existing = session.exec(select(Booking).where(Booking.pnr == pnr)).first()
        if not existing:
            return pnr


def enrich_booking_response(session: Session, booking: Booking) -> BookingResponse:
    train = session.get(Train, booking.train_id)
    b_dict = booking.model_dump()
    if train:
        b_dict.update({
            "train_number": train.train_number,
            "train_name": train.train_name,
            "source_station_code": train.source_station_code,
            "destination_station_code": train.destination_station_code,
            "departure_time": train.departure_time,
            "arrival_time": train.arrival_time,
        })
    return BookingResponse(**b_dict)


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def book_ticket(
    booking_in: BookingCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    train = session.get(Train, booking_in.train_id)
    if not train:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Train with ID {booking_in.train_id} not found.")
    if not train.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Train '{train.train_name}' ({train.train_number}) is currently suspended/inactive.",
        )

    today = date.today()
    if booking_in.journey_date < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot book tickets for a journey date in the past.",
        )

    schedule = session.exec(
        select(TrainSchedule).where(
            TrainSchedule.train_id == train.id,
            TrainSchedule.journey_date == booking_in.journey_date,
        )
    ).first()

    if not schedule:
        schedule = TrainSchedule(
            train_id=train.id,
            journey_date=booking_in.journey_date,
            total_seats=train.total_seats,
            available_seats=train.total_seats,
            fare=train.base_fare,
        )
        session.add(schedule)
        session.flush()

    if schedule.available_seats < booking_in.seats_booked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Booking failed: Not enough seats available. "
                f"Requested: {booking_in.seats_booked}, Available: {schedule.available_seats}."
            ),
        )

    schedule.available_seats -= booking_in.seats_booked
    pnr = generate_unique_pnr(session)
    seat_num = f"S1-{schedule.total_seats - schedule.available_seats}"
    total_fare = schedule.fare * booking_in.seats_booked

    booking = Booking(
        pnr=pnr,
        user_id=current_user.id,
        train_id=train.id,
        journey_date=booking_in.journey_date,
        seats_booked=booking_in.seats_booked,
        passenger_name=booking_in.passenger_name.strip(),
        passenger_age=booking_in.passenger_age,
        passenger_gender=booking_in.passenger_gender.strip(),
        berth_preference=booking_in.berth_preference or "LOWER",
        seat_number=seat_num,
        total_fare=total_fare,
        payment_status=PaymentStatus.PAID,
        booking_status=BookingStatus.CONFIRMED,
        booked_at=datetime.now(timezone.utc),
    )

    session.add(schedule)
    session.add(booking)
    session.commit()
    session.refresh(booking)

    return enrich_booking_response(session, booking)


@router.get("/my-bookings", response_model=List[BookingResponse])
def get_my_bookings(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    bookings = session.exec(
        select(Booking)
        .where(Booking.user_id == current_user.id)
        .order_by(Booking.booked_at.desc())
    ).all()

    return [enrich_booking_response(session, b) for b in bookings]


@router.get("/{pnr}", response_model=BookingResponse)
def get_booking_by_pnr(
    pnr: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    booking = session.exec(select(Booking).where(Booking.pnr == pnr.upper().strip())).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Booking with PNR '{pnr}' not found.")

    if current_user.role != UserRole.ADMIN and booking.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You can only view your own bookings.",
        )

    return enrich_booking_response(session, booking)


@router.post("/{pnr}/cancel", response_model=BookingCancelResponse)
def cancel_booking(
    pnr: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    booking = session.exec(select(Booking).where(Booking.pnr == pnr.upper().strip())).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Booking with PNR '{pnr}' not found.")

    if current_user.role != UserRole.ADMIN and booking.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You can only cancel your own bookings.",
        )

    if booking.booking_status == BookingStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticket is already cancelled. Cannot repeat cancellation.",
        )

    booking.booking_status = BookingStatus.CANCELLED
    booking.payment_status = PaymentStatus.REFUNDED
    booking.cancelled_at = datetime.now(timezone.utc)

    schedule = session.exec(
        select(TrainSchedule).where(
            TrainSchedule.train_id == booking.train_id,
            TrainSchedule.journey_date == booking.journey_date,
        )
    ).first()

    seats_restored = booking.seats_booked
    if schedule:
        schedule.available_seats = min(
            schedule.total_seats,
            schedule.available_seats + booking.seats_booked,
        )
        session.add(schedule)

    session.add(booking)
    session.commit()

    return BookingCancelResponse(
        message="Booking successfully cancelled. Refund processed and seats restored to availability.",
        pnr=booking.pnr,
        booking_status=booking.booking_status,
        seats_restored=seats_restored,
        cancelled_at=booking.cancelled_at,
    )
