import os
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Response, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.database import Base, get_session, make_engine, session_factory
from backend.models import HuntLog, WantedCriminal
from backend.schemas import CriminalRead, HuntCreate, HuntPatch, HuntRead
from backend.seed import seed_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = make_engine()
    try:
        Base.metadata.create_all(engine)
        app.state.session_factory = session_factory(engine)
        if os.getenv("SEED_DEMO", "true").lower() == "true":
            with app.state.session_factory() as session, session.begin():
                seed_database(session)
        yield
    finally:
        engine.dispose()


app = FastAPI(
    title="Space Bounty Hunters",
    version="1.0.0",
    description="Wanted criminals directory and bounty hunting journal. Midterm practical API.",
    lifespan=lifespan,
)
DB = Annotated[Session, Depends(get_session)]
PositiveID = Annotated[int, Path(gt=0)]
Reward = Annotated[Decimal | None, Query(ge=0, max_digits=14, decimal_places=2)]


def find_or_404(session: Session, model, entity_id: int):
    entity = session.get(model, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return entity


@app.get("/", include_in_schema=False)
def root():
    return {"name": "Space Bounty Hunters", "docs": "/docs"}


@app.get("/health", tags=["System"])
def health(session: DB):
    session.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/criminals/", response_model=list[CriminalRead], tags=["Criminals"])
def list_criminals(
    session: DB,
    min_reward: Reward = None,
    max_reward: Reward = None,
    armed: bool | None = None,
    has_crew: bool | None = None,
    escape_master: bool | None = None,
    sort: Literal["reward", "-reward"] = "reward",
):
    if min_reward is not None and max_reward is not None and min_reward > max_reward:
        raise HTTPException(status_code=422, detail="min_reward must not exceed max_reward")
    query = select(WantedCriminal)
    if min_reward is not None:
        query = query.where(WantedCriminal.reward >= min_reward)
    if max_reward is not None:
        query = query.where(WantedCriminal.reward <= max_reward)
    for field, value in (
        ("armed", armed),
        ("has_crew", has_crew),
        ("escape_master", escape_master),
    ):
        if value is not None:
            query = query.where(getattr(WantedCriminal, field) == value)
    order = WantedCriminal.reward.desc() if sort == "-reward" else WantedCriminal.reward.asc()
    return session.scalars(query.order_by(order, WantedCriminal.id)).all()


@app.get("/api/criminals/{id}/", response_model=CriminalRead, tags=["Criminals"])
def criminal_detail(id: PositiveID, session: DB):
    return find_or_404(session, WantedCriminal, id)


@app.get("/api/hunts/", response_model=list[HuntRead], tags=["Hunt journal"])
def list_hunts(session: DB, criminal_id: Annotated[int | None, Query(gt=0)] = None):
    query = select(HuntLog)
    if criminal_id is not None:
        query = query.where(HuntLog.criminal_id == criminal_id)
    return session.scalars(query.order_by(HuntLog.created_at.desc(), HuntLog.id.desc())).all()


@app.get("/api/hunts/{id}/", response_model=HuntRead, tags=["Hunt journal"])
def hunt_detail(id: PositiveID, session: DB):
    return find_or_404(session, HuntLog, id)


@app.post("/api/hunts/", response_model=HuntRead, status_code=201, tags=["Hunt journal"])
def create_hunt(body: HuntCreate, session: DB, response: Response):
    find_or_404(session, WantedCriminal, body.criminal_id)
    hunt = HuntLog(**body.model_dump())
    session.add(hunt)
    session.commit()
    session.refresh(hunt)
    response.headers["Location"] = f"/api/hunts/{hunt.id}/"
    return hunt


@app.patch("/api/hunts/{id}/", response_model=HuntRead, tags=["Hunt journal"])
def update_hunt(id: PositiveID, body: HuntPatch, session: DB):
    hunt = find_or_404(session, HuntLog, id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(hunt, key, value)
    session.commit()
    session.refresh(hunt)
    return hunt


@app.delete("/api/hunts/{id}/", status_code=status.HTTP_204_NO_CONTENT, tags=["Hunt journal"])
def delete_hunt(id: PositiveID, session: DB):
    hunt = find_or_404(session, HuntLog, id)
    session.delete(hunt)
    session.commit()
    return Response(status_code=204)
