from datetime import date, timedelta
from sqlmodel import Session, select

from app.auth import get_password_hash
from app.database import engine, init_db
from app.models import Station, Train, TrainSchedule, User, UserRole


def seed_data():
    init_db()
    with Session(engine) as session:
        admin_email = "admin@railconnect.com"
        admin = session.exec(select(User).where(User.email == admin_email)).first()
        if not admin:
            admin = User(
                email=admin_email,
                full_name="RailConnect Admin",
                hashed_password=get_password_hash("Admin@12345"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(admin)

        passenger_email = "passenger@railconnect.com"
        passenger = session.exec(select(User).where(User.email == passenger_email)).first()
        if not passenger:
            passenger = User(
                email=passenger_email,
                full_name="Tushar Chauhan",
                hashed_password=get_password_hash("Passenger@12345"),
                role=UserRole.PASSENGER,
                is_active=True,
            )
            session.add(passenger)

        stations = [
            Station(code="NDLS", name="New Delhi Railway Station", city="New Delhi", state="Delhi"),
            Station(code="CNB", name="Kanpur Central", city="Kanpur", state="Uttar Pradesh"),
            Station(code="LKO", name="Lucknow Charbagh", city="Lucknow", state="Uttar Pradesh"),
            Station(code="HWH", name="Howrah Junction", city="Kolkata", state="West Bengal"),
            Station(code="BCT", name="Mumbai Central", city="Mumbai", state="Maharashtra"),
            Station(code="BSB", name="Varanasi Junction", city="Varanasi", state="Uttar Pradesh"),
        ]
        for st in stations:
            existing = session.exec(select(Station).where(Station.code == st.code)).first()
            if not existing:
                session.add(st)

        session.commit()

        trains_data = [
            {
                "train_number": "12004",
                "train_name": "Lucknow Shatabdi Express",
                "source_station_code": "NDLS",
                "destination_station_code": "CNB",
                "departure_time": "06:10",
                "arrival_time": "11:20",
                "total_seats": 120,
                "base_fare": 750.0,
                "is_active": True,
            },
            {
                "train_number": "12452",
                "train_name": "Shram Shakti Express",
                "source_station_code": "NDLS",
                "destination_station_code": "CNB",
                "departure_time": "23:55",
                "arrival_time": "06:00",
                "total_seats": 150,
                "base_fare": 520.0,
                "is_active": True,
            },
            {
                "train_number": "12302",
                "train_name": "Howrah Rajdhani Express",
                "source_station_code": "NDLS",
                "destination_station_code": "HWH",
                "departure_time": "16:50",
                "arrival_time": "10:05",
                "total_seats": 200,
                "base_fare": 1850.0,
                "is_active": True,
            },
            {
                "train_number": "12952",
                "train_name": "Mumbai Tejas Rajdhani",
                "source_station_code": "NDLS",
                "destination_station_code": "BCT",
                "departure_time": "16:55",
                "arrival_time": "08:35",
                "total_seats": 180,
                "base_fare": 2100.0,
                "is_active": True,
            },
            {
                "train_number": "22436",
                "train_name": "Vande Bharat Express",
                "source_station_code": "NDLS",
                "destination_station_code": "BSB",
                "departure_time": "06:00",
                "arrival_time": "14:00",
                "total_seats": 100,
                "base_fare": 1400.0,
                "is_active": True,
            },
        ]

        created_trains = []
        for t_dict in trains_data:
            t = session.exec(select(Train).where(Train.train_number == t_dict["train_number"])).first()
            if not t:
                t = Train(**t_dict)
                session.add(t)
                session.commit()
                session.refresh(t)
            created_trains.append(t)

        today = date.today()
        for train in created_trains:
            for day_offset in range(7):
                j_date = today + timedelta(days=day_offset)
                sched = session.exec(
                    select(TrainSchedule).where(
                        TrainSchedule.train_id == train.id,
                        TrainSchedule.journey_date == j_date,
                    )
                ).first()
                if not sched:
                    sched = TrainSchedule(
                        train_id=train.id,
                        journey_date=j_date,
                        total_seats=train.total_seats,
                        available_seats=train.total_seats,
                        fare=train.base_fare,
                    )
                    session.add(sched)

        session.commit()


if __name__ == "__main__":
    seed_data()
