from __future__ import annotations

import pytest
from domain.models import Device, Firmware, Role, User
from infrastructure.db import Base
from infrastructure.sqlite_repo import (
    SqliteDeviceRepository,
    SqliteFirmwareRepository,
    SqliteUserRepository,
)
from ports.repository import UserAlreadyExists
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture
def session():
    # A single shared in-memory connection: plain `sqlite://` would hand each
    # connection its own throwaway database, so `StaticPool` keeps every use
    # of this engine on the same connection.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def make_firmware(model="ESP32", version="1.0.0") -> Firmware:
    return Firmware(
        model=model, version=version, filename=f"{version}.bin", signature="sig", sha256="a" * 64
    )


def test_add_assigns_id_and_persists_fields(session):
    repo = SqliteFirmwareRepository(session)

    added = repo.add(make_firmware())

    assert added.id is not None
    fetched = repo.get_by_id(added.id)
    assert fetched == added


def test_get_by_id_returns_none_when_missing(session):
    repo = SqliteFirmwareRepository(session)

    assert repo.get_by_id(999) is None


def test_get_latest_for_model_picks_highest_dotted_version(session):
    repo = SqliteFirmwareRepository(session)
    # Out of insertion order, and "1.2.9" would sort after "1.2.10" lexically.
    for version in ["1.0.0", "1.2.10", "1.2.9", "1.2.2"]:
        repo.add(make_firmware(version=version))

    latest = repo.get_latest_for_model("ESP32")

    assert latest.version == "1.2.10"


def test_get_latest_for_model_ignores_other_models(session):
    repo = SqliteFirmwareRepository(session)
    repo.add(make_firmware(model="ESP32", version="1.0.0"))
    repo.add(make_firmware(model="ESP32-S3", version="9.9.9"))

    latest = repo.get_latest_for_model("ESP32")

    assert latest.version == "1.0.0"


def test_get_latest_for_model_returns_none_when_no_firmware(session):
    repo = SqliteFirmwareRepository(session)

    assert repo.get_latest_for_model("ESP32") is None


def test_list_all_orders_newest_first(session):
    repo = SqliteFirmwareRepository(session)
    first = repo.add(make_firmware(version="1.0.0"))
    second = repo.add(make_firmware(version="1.1.0"))

    listed = repo.list_all()

    assert [f.id for f in listed] == [second.id, first.id]


def test_device_upsert_inserts_then_updates_same_device(session):
    repo = SqliteDeviceRepository(session)

    inserted = repo.upsert(Device(device_id="dev-1", model="ESP32", current_version="1.0.0"))
    updated = repo.upsert(Device(device_id="dev-1", model="ESP32", current_version="1.1.0"))

    assert updated.id == inserted.id
    assert updated.current_version == "1.1.0"
    assert repo.get_by_device_id("dev-1").current_version == "1.1.0"


def test_get_by_device_id_returns_none_when_missing(session):
    repo = SqliteDeviceRepository(session)

    assert repo.get_by_device_id("unknown") is None


def make_user(username="alice", role=Role.OPERATOR) -> User:
    return User(username=username, password_hash="hash", role=role)


def test_user_add_assigns_id_and_round_trips(session):
    repo = SqliteUserRepository(session)

    added = repo.add(make_user(role=Role.ADMIN))

    assert added.id is not None
    fetched = repo.get_by_username("alice")
    assert fetched == added
    assert fetched.role is Role.ADMIN
    assert repo.get_by_id(added.id) == added


def test_user_add_rejects_duplicate_username(session):
    repo = SqliteUserRepository(session)
    repo.add(make_user())

    with pytest.raises(UserAlreadyExists):
        repo.add(make_user())


def test_user_count_reflects_inserts(session):
    repo = SqliteUserRepository(session)

    assert repo.count() == 0
    repo.add(make_user(username="a"))
    repo.add(make_user(username="b"))
    assert repo.count() == 2


def test_get_user_by_username_returns_none_when_missing(session):
    repo = SqliteUserRepository(session)

    assert repo.get_by_username("nobody") is None
