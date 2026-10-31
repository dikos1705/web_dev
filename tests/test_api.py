from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models import HuntLog, WantedCriminal
from backend.seed import seed_database


def test_seed_and_details(client):
    criminals = client.get("/api/criminals/").json()
    assert len(criminals) == 5
    assert len(client.get("/api/hunts/").json()) == 10
    assert any(c["name"] is None for c in criminals)
    assert any(c["location_note"] is not None for c in criminals)
    assert any(c["latitude"] is not None for c in criminals)
    assert all(1 <= c["difficulty"] <= 10 for c in criminals)
    assert client.get("/api/criminals/1/").json()["nickname"] == "Red Comet"
    assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize("sort,reverse", [("reward", False), ("-reward", True)])
def test_sort(client, sort, reverse):
    rewards = [
        Decimal(c["reward"]) for c in client.get("/api/criminals/", params={"sort": sort}).json()
    ]
    assert rewards == sorted(rewards, reverse=reverse)


def test_all_filters_together_and_false(client):
    result = client.get(
        "/api/criminals/",
        params={
            "min_reward": 5000,
            "max_reward": 9000,
            "armed": True,
            "has_crew": False,
            "escape_master": False,
            "sort": "-reward",
        },
    )
    assert result.status_code == 200
    assert [c["nickname"] for c in result.json()] == ["Iron Fang"]
    assert [
        c["nickname"]
        for c in client.get(
            "/api/criminals/",
            params={
                "armed": False,
                "has_crew": False,
                "escape_master": False,
            },
        ).json()
    ] == ["Silver Fox"]
    assert client.get("/api/criminals/?min_reward=999999").json() == []


@pytest.mark.parametrize(
    "query",
    [
        "min_reward=-1",
        "max_reward=-1",
        "min_reward=NaN",
        "max_reward=Infinity",
        "min_reward=2&max_reward=1",
        "sort=name",
        "armed=perhaps",
        "has_crew=maybe",
        "escape_master=nope",
        "min_reward=1.001",
    ],
)
def test_invalid_filters(client, query):
    assert client.get("/api/criminals/?" + query).status_code == 422


def test_full_hunt_lifecycle_and_timestamp(client):
    before = datetime.now(UTC)
    result = client.post(
        "/api/hunts/",
        json={
            "criminal_id": 1,
            "success": False,
            "notes": " Target escaped. ",
        },
    )
    assert result.status_code == 201
    hunt = result.json()
    url = result.headers["Location"]
    created_at = datetime.fromisoformat(hunt["created_at"])
    assert before <= created_at <= datetime.now(UTC)
    assert hunt["notes"] == "Target escaped."
    assert client.get(url).json() == hunt
    filtered = client.get("/api/hunts/?criminal_id=1").json()
    assert len(filtered) == 3 and all(h["criminal_id"] == 1 for h in filtered)
    updated = client.patch(url, json={"success": True}).json()
    assert updated["success"] is True and updated["notes"] == hunt["notes"]
    updated = client.patch(url, json={"notes": "Captured."}).json()
    assert updated["success"] is True and updated["notes"] == "Captured."
    assert updated["created_at"] == hunt["created_at"]
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404
    assert client.delete(url).status_code == 404
    assert len(client.get("/api/hunts/").json()) == 10


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"criminal_id": 1, "success": "false", "notes": "x"},
        {"criminal_id": 1, "success": 1, "notes": "x"},
        {"criminal_id": 1, "success": False, "notes": "   "},
        {"criminal_id": 1, "success": False, "notes": "x" * 5001},
        {"criminal_id": 0, "success": False, "notes": "x"},
        {"criminal_id": "1", "success": False, "notes": "x"},
        {"criminal_id": 1, "success": False, "notes": "x", "created_at": "2000-01-01T00:00:00Z"},
    ],
)
def test_invalid_creation(client, body):
    assert client.post("/api/hunts/", json=body).status_code == 422
    assert len(client.get("/api/hunts/").json()) == 10


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"success": None},
        {"notes": None},
        {"success": "true"},
        {"notes": " "},
        {"criminal_id": 2},
        {"created_at": "2000-01-01T00:00:00Z"},
    ],
)
def test_invalid_patch(client, body):
    original = client.get("/api/hunts/1/").json()
    assert client.patch("/api/hunts/1/", json=body).status_code == 422
    assert client.get("/api/hunts/1/").json() == original


def test_missing_ids(client):
    assert client.get("/api/criminals/999999/").status_code == 404
    assert client.get("/api/hunts/999999/").status_code == 404
    assert client.patch("/api/hunts/999999/", json={"success": True}).status_code == 404
    assert client.delete("/api/hunts/999999/").status_code == 404
    assert (
        client.post(
            "/api/hunts/",
            json={
                "criminal_id": 999999,
                "success": False,
                "notes": "x",
            },
        ).status_code
        == 404
    )
    assert client.get("/api/hunts/?criminal_id=999999").json() == []


@pytest.mark.parametrize(
    "path",
    [
        "/api/criminals/0/",
        "/api/criminals/abc/",
        "/api/hunts/-1/",
        "/api/hunts/?criminal_id=0",
        "/api/hunts/?criminal_id=abc",
    ],
)
def test_invalid_ids(client, path):
    assert client.get(path).status_code == 422


def test_seed_is_idempotent(db_engine):
    with Session(db_engine) as session, session.begin():
        assert seed_database(session) is False
        assert session.scalar(select(func.count()).select_from(WantedCriminal)) == 5
        assert session.scalar(select(func.count()).select_from(HuntLog)) == 10


def test_database_enforces_foreign_key(db_engine):
    with Session(db_engine) as session:
        session.add(HuntLog(criminal_id=999999, success=False, notes="Invalid FK"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


@pytest.mark.parametrize(
    "changes",
    [
        {"difficulty": 11},
        {"reward": -1},
        {"latitude": 91},
        {"longitude": None},
        {"location_note": "Both representations"},
    ],
)
def test_database_constraints(db_engine, changes):
    with Session(db_engine) as session:
        criminal = session.get(WantedCriminal, 1)
        for key, value in changes.items():
            setattr(criminal, key, value)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_database_one_to_many(db_engine):
    with Session(db_engine) as session:
        criminal = session.get(WantedCriminal, 1)
        assert len(criminal.hunts) == 2
        assert all(hunt.criminal is criminal for hunt in criminal.hunts)


def test_openapi(client):
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "Space Bounty Hunters"
    assert set(schema["paths"]["/api/hunts/{id}/"]) == {"get", "patch", "delete"}
