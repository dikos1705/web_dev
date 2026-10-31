"""Idempotent demo import: python -m backend.seed."""

from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from backend.database import Base, make_engine
from backend.models import HuntLog, WantedCriminal

CRIMINALS = [
    {
        "name": "Viktor Voss",
        "nickname": "Red Comet",
        "reward": "25000.00",
        "difficulty": 9,
        "latitude": 43.24,
        "longitude": 76.95,
        "armed": True,
        "has_crew": True,
        "escape_master": True,
    },
    {
        "name": None,
        "nickname": "Ghost",
        "reward": "12000.00",
        "difficulty": 8,
        "location_note": "Abandoned station near Europa",
        "armed": False,
        "has_crew": False,
        "escape_master": True,
    },
    {
        "name": "Mara Quill",
        "nickname": "Iron Fang",
        "reward": "8000.00",
        "difficulty": 6,
        "latitude": -12.5,
        "longitude": 130.8,
        "armed": True,
        "has_crew": False,
        "escape_master": False,
    },
    {
        "name": "Leon Rake",
        "nickname": "Asteroid Jack",
        "reward": "3500.00",
        "difficulty": 4,
        "location_note": "Mining outpost in the asteroid belt",
        "armed": True,
        "has_crew": True,
        "escape_master": False,
    },
    {
        "name": "Nia Sol",
        "nickname": "Silver Fox",
        "reward": "1500.00",
        "difficulty": 2,
        "latitude": 0.0,
        "longitude": 15.2,
        "armed": False,
        "has_crew": False,
        "escape_master": False,
    },
]


def seed_database(session: Session) -> bool:
    # Serialize simultaneous seed commands across workers on PostgreSQL.
    session.execute(text("SELECT pg_advisory_xact_lock(17052026)"))
    if session.scalar(select(func.count()).select_from(WantedCriminal)):
        return False
    criminals = [
        WantedCriminal(**{**item, "reward": Decimal(item["reward"])}) for item in CRIMINALS
    ]
    session.add_all(criminals)
    session.flush()
    for criminal in criminals:
        session.add_all(
            [
                HuntLog(
                    criminal_id=criminal.id,
                    success=False,
                    notes=f"First contact with {criminal.nickname}; target escaped.",
                ),
                HuntLog(
                    criminal_id=criminal.id,
                    success=True,
                    notes=f"Second operation: {criminal.nickname} captured at the outpost.",
                ),
            ]
        )
    session.flush()
    return True


def main():
    engine = make_engine()
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        imported = seed_database(session)
    engine.dispose()
    print("Imported 5 criminals and 10 hunt logs." if imported else "Already seeded; no changes.")


if __name__ == "__main__":
    main()
