from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import admin, auth, bookings, trains, users
from app.seed import seed_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan event: initialize DB and seed initial demo data."""
    init_db()
    try:
        seed_data()
    except Exception as e:
        print(f"Notice: Seed data initialization check: {e}")
    yield


app = FastAPI(
    title="RailConnect 🚆 - Mini Railway Booking Backend",
    description=(
        "A robust, scalable railway ticket booking backend built with FastAPI, SQLModel, and SQLite. "
        "Supports user registration/login, JWT authentication with token revocation, admin railway management, "
        "search by origin/destination/date, atomic ticket booking with unique PNR generation, cancellation, "
        "and strict concurrency control."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Enable CORS for flexible integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers under standard API versioning
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(users.router, prefix=settings.API_V1_PREFIX)
app.include_router(trains.router, prefix=settings.API_V1_PREFIX)
app.include_router(bookings.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin.router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Root"])
def root():
    """Welcome endpoint providing system metadata and API documentation link."""
    return {
        "project": "RailConnect 🚆",
        "description": "Mini Railway Booking System Backend",
        "status": "active",
        "docs": "/docs",
        "redoc": "/redoc",
        "api_prefix": settings.API_V1_PREFIX,
        "features": [
            "User Accounts & Password Hashing (bcrypt)",
            "JWT Authentication & Token Revocation (Logout)",
            "Forgot Password & Single-Use Expiring Reset Tokens",
            "Admin Control (Add/Update/Deactivate Trains, Stations, Fares & Seats)",
            "Train Search by Source, Destination & Date",
            "Atomic Ticket Booking & Unique PNR Generation",
            "Ticket Cancellation & Seat Inventory Restoration",
            "Double-booking & Repeated Cancellation Prevention",
        ],
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint to verify backend service status."""
    return {"status": "healthy", "service": "RailConnect Backend"}
