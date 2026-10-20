from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.auth import get_password_hash
from app.database import get_session
from app.main import app
from app.models import Station, Train, TrainSchedule, User, UserRole

# Use an in-memory SQLite database with StaticPool for tests
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@pytest.fixture(name="session")
def session_fixture():
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        # Seed test admin
        admin = User(
            email="admin@railconnect.com",
            full_name="Admin User",
            hashed_password=get_password_hash("Admin@12345"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        # Seed test passenger
        passenger = User(
            email="passenger@railconnect.com",
            full_name="Passenger One",
            hashed_password=get_password_hash("Passenger@12345"),
            role=UserRole.PASSENGER,
            is_active=True,
        )
        # Seed second passenger for ownership tests
        passenger2 = User(
            email="passenger2@railconnect.com",
            full_name="Passenger Two",
            hashed_password=get_password_hash("Passenger@12345"),
            role=UserRole.PASSENGER,
            is_active=True,
        )
        session.add(admin)
        session.add(passenger)
        session.add(passenger2)

        # Seed stations
        ndls = Station(code="NDLS", name="New Delhi", city="New Delhi", state="Delhi")
        cnb = Station(code="CNB", name="Kanpur Central", city="Kanpur", state="UP")
        hwh = Station(code="HWH", name="Howrah", city="Kolkata", state="WB")
        session.add(ndls)
        session.add(cnb)
        session.add(hwh)

        # Seed test train: New Delhi to Kanpur
        train = Train(
            train_number="12004",
            train_name="Lucknow Shatabdi",
            source_station_code="NDLS",
            destination_station_code="CNB",
            departure_time="06:10",
            arrival_time="11:20",
            total_seats=50,
            base_fare=750.0,
            is_active=True,
        )
        session.add(train)
        session.commit()
        session.refresh(train)

        # Seed schedule for upcoming 3 days
        today = date.today()
        for i in range(3):
            j_date = today + timedelta(days=i)
            sched = TrainSchedule(
                train_id=train.id,
                journey_date=j_date,
                total_seats=50,
                available_seats=50,
                fare=750.0,
            )
            session.add(sched)
        session.commit()

        yield session

    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
