"""Idempotent synthetic schedules. Never reset or delete a user's bookings."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Airport, Flight

AIRPORTS = [
    ('ALA', 'Almaty', 'Almaty International', 'Kazakhstan', 'Asia/Almaty'),
    ('NQZ', 'Astana', 'Nursultan Nazarbayev International', 'Kazakhstan', 'Asia/Almaty'),
    ('CIT', 'Shymkent', 'Shymkent International', 'Kazakhstan', 'Asia/Almaty'),
    ('SCO', 'Aktau', 'Aktau International', 'Kazakhstan', 'Asia/Almaty'),
    ('DXB', 'Dubai', 'Dubai International', 'United Arab Emirates', 'Asia/Dubai'),
    ('IST', 'Istanbul', 'Istanbul Airport', 'Turkey', 'Europe/Istanbul'),
]
ROUTES = [
    ('AE101', 'ALA', 'NQZ', 7, 20, 100, 24900),
    ('AE103', 'ALA', 'NQZ', 13, 40, 100, 33900),
    ('AE105', 'ALA', 'NQZ', 19, 10, 100, 28900),
    ('AE102', 'NQZ', 'ALA', 10, 0, 105, 26900),
    ('AE201', 'ALA', 'DXB', 9, 15, 290, 89900),
    ('AE202', 'DXB', 'ALA', 17, 30, 260, 94900),
    ('AE301', 'ALA', 'IST', 11, 0, 360, 119900),
    ('AE401', 'NQZ', 'CIT', 14, 25, 120, 29900),
    ('AE501', 'ALA', 'SCO', 16, 45, 185, 45900),
]


async def seed_database(db: AsyncSession):
    async with db.begin():
        for code, city, name, country, tz in AIRPORTS:
            await db.execute(insert(Airport).values(code=code, city=city, name=name, country=country,
                       timezone=tz).on_conflict_do_nothing(index_elements=['code']))
        zones = {a[0]: a[4] for a in AIRPORTS}
        today = datetime.now(ZoneInfo('Asia/Almaty')).date()
        for offset in range(1, 8):
            day = today + timedelta(days=offset)
            for number, origin, destination, hour, minute, duration, price in ROUTES:
                departure = datetime.combine(day, time(hour, minute), ZoneInfo(zones[origin]))
                await db.execute(insert(Flight).values(number=number, origin_code=origin,
                    destination_code=destination, departure_at=departure,
                    arrival_at=departure.astimezone(timezone.utc) + timedelta(minutes=duration),
                    price_kzt=price).on_conflict_do_nothing(index_elements=['number', 'departure_at']))
