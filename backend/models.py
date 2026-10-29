from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Airport(Base):
    __tablename__ = 'airports'
    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    city: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(120))
    country: Mapped[str] = mapped_column(String(60))
    timezone: Mapped[str] = mapped_column(String(50))


class Flight(Base):
    __tablename__ = 'flights'
    __table_args__ = (
        CheckConstraint('origin_code <> destination_code', name='different_airports'),
        CheckConstraint('arrival_at > departure_at', name='positive_duration'),
        CheckConstraint('price_kzt > 0', name='positive_price'),
        Index('ix_flight_search', 'origin_code', 'destination_code', 'departure_at'),
        Index('uq_flight_schedule', 'number', 'departure_at', unique=True),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(8))
    origin_code: Mapped[str] = mapped_column(ForeignKey('airports.code'))
    destination_code: Mapped[str] = mapped_column(ForeignKey('airports.code'))
    departure_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    price_kzt: Mapped[int] = mapped_column(Integer)
    origin: Mapped[Airport] = relationship(foreign_keys=[origin_code], lazy='joined')
    destination: Mapped[Airport] = relationship(foreign_keys=[destination_code], lazy='joined')


class Booking(Base):
    __tablename__ = 'bookings'
    __table_args__ = (
        CheckConstraint("status IN ('confirmed', 'cancelled')", name='valid_booking_status'),
        CheckConstraint("fare IN ('light', 'standard', 'flex')", name='valid_fare'),
        CheckConstraint("seat ~ '^[1-6][A-D]$'", name='valid_seat'),
        CheckConstraint('total_kzt > 0', name='positive_total'),
        Index('uq_active_seat', 'flight_id', 'seat', unique=True,
              postgresql_where=text("status = 'confirmed'")),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    reference: Mapped[str] = mapped_column(String(8), unique=True)
    flight_id: Mapped[int] = mapped_column(ForeignKey('flights.id', ondelete='RESTRICT'), index=True)
    seat: Mapped[str] = mapped_column(String(2))
    fare: Mapped[str] = mapped_column(String(10))
    passenger_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254))
    total_kzt: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default='confirmed')
    request_key: Mapped[UUID] = mapped_column(unique=True)
    request_digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    flight: Mapped[Flight] = relationship(lazy='joined')
