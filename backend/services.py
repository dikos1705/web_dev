"""Booking invariants and transactions. Money is stored as integer KZT."""
import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Airport, Booking, Flight
from .security import management_token

SEATS = [f'{row}{letter}' for row in range(1, 7) for letter in 'ABCD']
FARES = {
    'light': ('Light', 100, 7, 0, 'Travel light. One cabin bag and your choice of seat.'),
    'standard': ('Standard', 125, 7, 23, 'A little more room for everything you bring.'),
    'flex': ('Flex', 150, 10, 32, 'Pack for a longer stay. Our most generous baggage allowance.'),
}


def fare_options(base_price):
    return [dict(code=code, name=name, price_kzt=(base_price * percent + 99) // 100,
                 cabin_bag_kg=cabin, checked_bag_kg=checked, description=description)
            for code, (name, percent, cabin, checked, description) in FARES.items()]


def price_for(flight, fare):
    return (flight.price_kzt * FARES[fare][1] + 99) // 100


async def occupied_seats(db: AsyncSession, flight_id):
    return set((await db.scalars(select(Booking.seat).where(
        Booking.flight_id == flight_id, Booking.status == 'confirmed'))).all())


async def flight_view(db: AsyncSession, flight, occupied_count=None):
    if occupied_count is None:
        occupied_count = len(await occupied_seats(db, flight.id))
    return dict(id=flight.id, number=flight.number,
        origin=flight.origin, destination=flight.destination,
        departure_at=flight.departure_at, arrival_at=flight.arrival_at,
        duration_minutes=int((flight.arrival_at - flight.departure_at).total_seconds() // 60),
        price_kzt=flight.price_kzt, available_seats=24 - occupied_count,
        fares=fare_options(flight.price_kzt))


async def booking_view(db: AsyncSession, booking, receipt=False):
    result = dict(id=booking.id, reference=booking.reference, flight=await flight_view(db, booking.flight),
        seat=booking.seat, fare=booking.fare, passenger_name=booking.passenger_name,
        email=booking.email, total_kzt=booking.total_kzt, status=booking.status,
        created_at=booking.created_at)
    if receipt:
        result['manage_token'] = management_token(booking.id)
    return result


async def get_flight(db: AsyncSession, flight_id, lock=False):
    query = select(Flight).where(Flight.id == flight_id)
    if lock:
        query = query.with_for_update(of=Flight)
    flight = await db.scalar(query)
    if flight is None:
        raise HTTPException(404, 'Flight not found')
    return flight


def check_departure(flight):
    if flight.departure_at <= datetime.now(timezone.utc):
        raise HTTPException(409, 'This flight has already departed')


async def check_airports(db: AsyncSession, data):
    for code in (data.origin_code, data.destination_code):
        if await db.get(Airport, code) is None:
            raise HTTPException(422, f'Unknown airport: {code}')


async def create_booking(db: AsyncSession, data):
    digest = hashlib.sha256(json.dumps(data.model_dump(mode='json'), sort_keys=True).encode()).hexdigest()
    async with db.begin():
        # One lock order for creation, changes and cancellation: flight, then booking.
        flight = await get_flight(db, data.flight_id, lock=True)
        existing = await db.scalar(select(Booking).where(Booking.request_key == data.request_key))
        if existing:
            if existing.request_digest != digest:
                raise HTTPException(409, 'request_key was already used for different booking details')
            return await booking_view(db, existing, receipt=True), False
        check_departure(flight)
        if data.seat in await occupied_seats(db, flight.id):
            raise HTTPException(409, 'This seat was just booked. Please choose another seat.')
        booking_id = uuid4()
        booking = Booking(id=booking_id, reference=booking_id.hex[:8].upper(), flight=flight,
            seat=data.seat, fare=data.fare, passenger_name=data.passenger_name,
            email=str(data.email), total_kzt=price_for(flight, data.fare),
            request_key=data.request_key, request_digest=digest)
        db.add(booking)
        await db.flush()
        result = await booking_view(db, booking, receipt=True)
    return result, True


async def locked_booking(db: AsyncSession, booking_id):
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(404, 'Booking not found')
    await get_flight(db, booking.flight_id, lock=True)
    booking = await db.scalar(select(Booking).where(Booking.id == booking_id)
                        .with_for_update(of=Booking).execution_options(populate_existing=True))
    if booking is None:
        raise HTTPException(404, 'Booking not found')
    return booking


async def update_booking(db: AsyncSession, booking_id, data):
    async with db.begin():
        booking = await locked_booking(db, booking_id)
        if booking.status != 'confirmed':
            raise HTTPException(409, 'A cancelled booking cannot be changed')
        check_departure(booking.flight)
        changes = data.model_dump(exclude_unset=True)
        if changes.get('seat') and changes['seat'] != booking.seat:
            if changes['seat'] in await occupied_seats(db, booking.flight_id):
                raise HTTPException(409, 'That seat is no longer available')
        for key, value in changes.items():
            setattr(booking, key, str(value))
        await db.flush()
        result = await booking_view(db, booking)
    return result
