from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .database import Base, SessionLocal, engine, get_db
from .models import Airport, Booking, Flight
from .schemas import (AirportOut, BookingCreate, BookingList, BookingOut, BookingPatch,
                      BookingReceipt, BookingReplace, FlightInput, FlightList, FlightOut)
from .security import authorize_booking, booking_header, require_admin
from .seed import seed_database
from .services import (SEATS, booking_view, check_airports, create_booking, flight_view,
                       get_flight, locked_booking, occupied_seats, update_booking)

ROOT = Path(__file__).resolve().parents[1]
DB = Annotated[AsyncSession, Depends(get_db)]
Token = Annotated[str | None, Depends(booking_header)]
Admin = [Depends(require_admin)]


@asynccontextmanager
async def lifespan(app):
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        if get_settings().seed_demo:
            async with SessionLocal() as db:
                await seed_database(db)
        yield
    finally:
        await engine.dispose()


app = FastAPI(title='Aeron Flight Booking API', version='1.0.0', lifespan=lifespan,
    description='Educational flight reservations with synthetic inventory. No payment is taken and no real ticket is issued. '
                'Flight writes and booking lists require X-Admin-Key. Booking management requires the X-Booking-Token returned on creation.')
app.mount('/static', StaticFiles(directory=ROOT / 'frontend'), name='static')


@app.middleware('http')
async def privacy_headers(request, call_next):
    response = await call_next(request)
    if '/bookings' in request.url.path:
        response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    return response


@app.exception_handler(IntegrityError)
async def conflict(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=409, content={'detail': 'This resource conflicts with an existing record'})


@app.exception_handler(OperationalError)
async def database_unavailable(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=503, content={'detail': 'Database temporarily unavailable'})


@app.get('/', include_in_schema=False)
async def home():
    return FileResponse(ROOT / 'frontend/index.html')


@app.get('/health', tags=['System'])
async def health(db: DB):
    await db.execute(text('SELECT 1'))
    return {'status': 'ok', 'database': 'connected'}


@app.get('/api/airports', response_model=list[AirportOut], tags=['Search'])
async def airports(db: DB):
    return (await db.scalars(select(Airport).order_by(Airport.city))).all()


@app.get('/api/flights', response_model=FlightList, tags=['Flights'])
async def flights(db: DB, origin: str | None = Query(default=None, pattern=r'^[A-Z]{3}$'),
            destination: str | None = Query(default=None, pattern=r'^[A-Z]{3}$'),
            departure_date: date | None = None,
            sort: str = Query(default='departure', pattern=r'^(departure|price)$'),
            limit: int = Query(default=100, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    filters = [Flight.departure_at > datetime.now(timezone.utc)]
    origin_airport = None
    if origin:
        origin_airport = await db.get(Airport, origin)
        if origin_airport is None:
            raise HTTPException(422, 'Unknown origin airport')
        filters.append(Flight.origin_code == origin)
    if destination:
        if await db.get(Airport, destination) is None:
            raise HTTPException(422, 'Unknown destination airport')
        filters.append(Flight.destination_code == destination)
    if origin and origin == destination:
        raise HTTPException(422, 'Choose different airports')
    if departure_date:
        # Without origin, the search date is interpreted in Kazakhstan time.
        tz = ZoneInfo(origin_airport.timezone if origin_airport else 'Asia/Almaty')
        start = datetime.combine(departure_date, time.min, tz)
        filters.extend([Flight.departure_at >= start, Flight.departure_at < start + timedelta(days=1)])
    total = await db.scalar(select(func.count()).select_from(Flight).where(*filters))
    order = (Flight.price_kzt, Flight.departure_at) if sort == 'price' else (Flight.departure_at, Flight.id)
    results = (await db.scalars(select(Flight).where(*filters).order_by(*order).limit(limit).offset(offset))).unique().all()
    counts = dict((await db.execute(select(Booking.flight_id, func.count()).where(
        Booking.flight_id.in_([f.id for f in results]), Booking.status == 'confirmed').group_by(Booking.flight_id))).all())
    return {'flights': [await flight_view(db, flight, counts.get(flight.id, 0)) for flight in results], 'total': total}


@app.get('/api/flights/{flight_id}', response_model=FlightOut, tags=['Flights'])
async def flight_by_id(flight_id: int, db: DB):
    return await flight_view(db, await get_flight(db, flight_id))


@app.get('/api/flights/{flight_id}/seats', tags=['Flights'])
async def seats(flight_id: int, db: DB):
    await get_flight(db, flight_id)
    taken = await occupied_seats(db, flight_id)
    return {'flight_id': flight_id, 'seats': [{'label': seat, 'available': seat not in taken} for seat in SEATS]}


@app.post('/api/flights', response_model=FlightOut, status_code=201, dependencies=Admin, tags=['Admin flights'])
async def add_flight(data: FlightInput, db: DB):
    async with db.begin():
        await check_airports(db, data)
        flight = Flight(**data.model_dump())
        db.add(flight)
        await db.flush()
        await db.refresh(flight, ['origin', 'destination'])
        result = await flight_view(db, flight)
    return result


@app.put('/api/flights/{flight_id}', response_model=FlightOut, dependencies=Admin, tags=['Admin flights'])
async def replace_flight(flight_id: int, data: FlightInput, db: DB):
    async with db.begin():
        flight = await get_flight(db, flight_id, lock=True)
        if await db.scalar(select(Booking.id).where(Booking.flight_id == flight_id).limit(1)):
            raise HTTPException(409, 'A flight with booking history cannot be changed')
        await check_airports(db, data)
        for key, value in data.model_dump().items():
            setattr(flight, key, value)
        await db.flush()
        await db.refresh(flight, ['origin', 'destination'])
        result = await flight_view(db, flight)
    return result


@app.delete('/api/flights/{flight_id}', status_code=204, dependencies=Admin, tags=['Admin flights'])
async def delete_flight(flight_id: int, db: DB):
    async with db.begin():
        flight = await get_flight(db, flight_id, lock=True)
        if await db.scalar(select(Booking.id).where(Booking.flight_id == flight_id).limit(1)):
            raise HTTPException(409, 'Delete associated cancelled bookings before deleting this flight')
        await db.delete(flight)
    return Response(status_code=204)


@app.post('/api/bookings', response_model=BookingReceipt, status_code=201, tags=['Bookings'])
async def book(data: BookingCreate, response: Response, db: DB):
    result, created = await create_booking(db, data)
    response.status_code = 201 if created else 200
    response.headers['Location'] = f'/api/bookings/{result["id"]}'
    return result


@app.get('/api/bookings', response_model=BookingList, dependencies=Admin, tags=['Admin bookings'])
async def list_bookings(db: DB, limit: int = Query(default=25, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    records = (await db.scalars(select(Booking).order_by(Booking.created_at.desc(), Booking.id).limit(limit).offset(offset))).unique().all()
    return {'bookings': [await booking_view(db, b) for b in records], 'total': await db.scalar(select(func.count()).select_from(Booking))}


@app.get('/api/bookings/{booking_id}', response_model=BookingOut, tags=['Bookings'])
async def booking_by_id(booking_id: UUID, token: Token, db: DB):
    authorize_booking(booking_id, token)
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(404, 'Booking not found')
    return await booking_view(db, booking)


@app.put('/api/bookings/{booking_id}', response_model=BookingOut, tags=['Bookings'])
async def booking_replace(booking_id: UUID, data: BookingReplace, token: Token, db: DB):
    authorize_booking(booking_id, token)
    return await update_booking(db, booking_id, data)


@app.patch('/api/bookings/{booking_id}', response_model=BookingOut, tags=['Bookings'])
async def booking_patch(booking_id: UUID, data: BookingPatch, token: Token, db: DB):
    authorize_booking(booking_id, token)
    return await update_booking(db, booking_id, data)


@app.post('/api/bookings/{booking_id}/cancel', response_model=BookingOut, tags=['Bookings'])
async def cancel_booking(booking_id: UUID, token: Token, db: DB):
    authorize_booking(booking_id, token)
    async with db.begin():
        booking = await locked_booking(db, booking_id)
        booking.status = 'cancelled'  # Idempotent; the partial unique seat index releases the seat.
        await db.flush()
        result = await booking_view(db, booking)
    return result


@app.delete('/api/bookings/{booking_id}', status_code=204, tags=['Bookings'])
async def delete_booking(booking_id: UUID, token: Token, db: DB):
    authorize_booking(booking_id, token)
    async with db.begin():
        booking = await locked_booking(db, booking_id)
        if booking.status != 'cancelled':
            raise HTTPException(409, 'Cancel the booking before deleting it')
        await db.delete(booking)
    return Response(status_code=204)


@app.get('/api/bookings/{booking_id}/itinerary', response_class=PlainTextResponse, tags=['Bookings'])
async def itinerary(booking_id: UUID, token: Token, db: DB):
    authorize_booking(booking_id, token)
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(404, 'Booking not found')
    flight = booking.flight
    content = (f'AERON - DEMO RESERVATION\nReference: {booking.reference}\nStatus: {booking.status}\n'
        f'Passenger: {booking.passenger_name}\nFlight: {flight.number}\n'
        f'Route: {flight.origin_code} - {flight.destination_code}\n'
        f'Departure (UTC): {flight.departure_at.astimezone(timezone.utc).isoformat()}\n'
        f'Seat: {booking.seat}\nFare: {booking.fare}\nTotal: {booking.total_kzt} KZT\n'
        'Educational demo only. No payment was taken; this is not a real ticket.\n')
    return PlainTextResponse(content, headers={'Content-Disposition': f'attachment; filename="Aeron-{booking.reference}.txt"'})
