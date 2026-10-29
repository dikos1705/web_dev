from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StrictInt, field_validator, model_validator

Fare = Literal['light', 'standard', 'flex']
Seat = Annotated[str, Field(pattern=r'^[1-6][A-D]$')]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    @field_validator('passenger_name', check_fields=False)
    @classmethod
    def readable_name(cls, value):
        if value is not None and any(ord(c) < 32 for c in value):
            raise ValueError('Passenger name cannot contain control characters')
        return value


class AirportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    city: str
    name: str
    country: str
    timezone: str


class FlightInput(Input):
    number: str = Field(pattern=r'^AE\d{3,4}$')
    origin_code: str = Field(pattern=r'^[A-Z]{3}$')
    destination_code: str = Field(pattern=r'^[A-Z]{3}$')
    departure_at: datetime
    arrival_at: datetime
    price_kzt: StrictInt = Field(gt=0, le=5_000_000)

    @model_validator(mode='after')
    def schedule_is_valid(self):
        if self.origin_code == self.destination_code:
            raise ValueError('Origin and destination must be different')
        if self.departure_at.tzinfo is None or self.arrival_at.tzinfo is None:
            raise ValueError('Use timezone-aware departure and arrival timestamps')
        if self.departure_at <= datetime.now(timezone.utc):
            raise ValueError('Departure must be in the future')
        if self.arrival_at <= self.departure_at:
            raise ValueError('Arrival must be after departure')
        return self


class BookingCreate(Input):
    flight_id: StrictInt = Field(gt=0)
    seat: Seat
    fare: Fare = 'light'
    passenger_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    request_key: UUID

class BookingReplace(Input):
    passenger_name: str = Field(min_length=2, max_length=100)
    email: EmailStr


class BookingPatch(Input):
    passenger_name: str | None = Field(default=None, min_length=2, max_length=100)
    email: EmailStr | None = None
    seat: Seat | None = None

    @model_validator(mode='after')
    def nonempty(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError('Supply at least one non-null passenger_name, email or seat')
        return self


class FareOut(BaseModel):
    code: Fare
    name: str
    price_kzt: int
    cabin_bag_kg: int
    checked_bag_kg: int
    description: str


class FlightOut(BaseModel):
    id: int
    number: str
    origin: AirportOut
    destination: AirportOut
    departure_at: datetime
    arrival_at: datetime
    duration_minutes: int
    price_kzt: int
    currency: Literal['KZT'] = 'KZT'
    available_seats: int
    total_seats: int = 24
    fares: list[FareOut]


class FlightList(BaseModel):
    flights: list[FlightOut]
    total: int


class BookingOut(BaseModel):
    id: UUID
    reference: str
    flight: FlightOut
    seat: str
    fare: Fare
    passenger_name: str
    email: EmailStr
    total_kzt: int
    currency: Literal['KZT'] = 'KZT'
    status: Literal['confirmed', 'cancelled']
    created_at: datetime


class BookingReceipt(BookingOut):
    manage_token: str


class BookingList(BaseModel):
    bookings: list[BookingOut]
    total: int
