from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class WantedCriminal(Base):
    __tablename__ = "wanted_criminals"
    __table_args__ = (
        CheckConstraint("reward >= 0", name="reward_nonnegative"),
        CheckConstraint("difficulty BETWEEN 1 AND 10", name="difficulty_range"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_range"),
        CheckConstraint(
            "(latitude IS NOT NULL AND longitude IS NOT NULL AND location_note IS NULL) "
            "OR (latitude IS NULL AND longitude IS NULL AND location_note IS NOT NULL)",
            name="coordinates_or_note",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    nickname: Mapped[str] = mapped_column(String(120), nullable=False)
    reward: Mapped[Decimal] = mapped_column(Numeric(14, 2), index=True)
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)
    location_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[int] = mapped_column(Integer)
    armed: Mapped[bool] = mapped_column(Boolean, default=False)
    has_crew: Mapped[bool] = mapped_column(Boolean, default=False)
    escape_master: Mapped[bool] = mapped_column(Boolean, default=False)
    hunts: Mapped[list["HuntLog"]] = relationship(back_populates="criminal")


class HuntLog(Base):
    __tablename__ = "hunt_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    criminal_id: Mapped[int] = mapped_column(
        ForeignKey("wanted_criminals.id", ondelete="RESTRICT"),
        index=True,
    )
    success: Mapped[bool] = mapped_column(Boolean)
    notes: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    criminal: Mapped[WantedCriminal] = relationship(back_populates="hunts")
