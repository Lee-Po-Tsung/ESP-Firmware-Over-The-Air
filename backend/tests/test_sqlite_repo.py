from __future__ import annotations

from datetime import datetime, timezone

import pytest
from domain.models import Device, Firmware, Role, User
from infrastructure.db import Base
from infrastructure.sqlite_repo import (
    SqliteDeviceRepository,
    SqliteFirmwareRepository,
    SqliteUserRepository,
)
from ports.repository import FirmwareAlreadyExists, UserAlreadyExists
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


def make_firmware(model="ESP32", version="1.0.0", sha256="a" * 64) -> Firmware:
    return Firmware(
        model=model,
        version=version,
        filename=f"{version}.bin",
        signature="sig",
        sha256=sha256,
        size_bytes=1,
    )


def test_add_assigns_id_and_persists_fields(session):
    repo = SqliteFirmwareRepository(session)

    added = repo.add(make_firmware())

    assert added.id is not None
    fetched = repo.get_by_id(added.id)
    assert fetched == added
    assert fetched.active is True


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


def test_get_latest_for_model_breaks_version_tie_by_newest_row(session):
    repo = SqliteFirmwareRepository(session)
    # Distinct versions can still parse to the same tuple: the parser reads at
    # most three segments and stops at the first non-digit. So the tie-break
    # picks the later upload rather than depending on the query's row order.
    first = repo.add(make_firmware(version="1.2.3"))
    second = repo.add(make_firmware(version="1.2.3.4"))

    latest = repo.get_latest_for_model("ESP32")

    assert latest.id == second.id
    assert second.id > first.id


def test_add_rejects_a_version_already_stored_for_the_model(session):
    repo = SqliteFirmwareRepository(session)
    repo.add(make_firmware(version="1.2.0"))

    with pytest.raises(FirmwareAlreadyExists):
        repo.add(make_firmware(version="1.2.0"))


def test_add_allows_the_same_version_on_another_model(session):
    repo = SqliteFirmwareRepository(session)
    repo.add(make_firmware(model="ESP32", version="1.2.0"))

    added = repo.add(make_firmware(model="ESP32-S3", version="1.2.0"))

    assert added.id is not None


def test_get_by_sha256_finds_a_binary_already_stored(session):
    repo = SqliteFirmwareRepository(session)
    added = repo.add(make_firmware(version="1.0.2", sha256="b" * 64))

    found = repo.get_by_sha256("ESP32", "b" * 64)

    assert found.id == added.id
    assert found.version == "1.0.2"


def test_get_by_sha256_returns_none_when_no_binary_matches(session):
    repo = SqliteFirmwareRepository(session)
    repo.add(make_firmware(sha256="b" * 64))

    assert repo.get_by_sha256("ESP32", "c" * 64) is None


def test_get_by_sha256_ignores_the_same_binary_on_another_model(session):
    repo = SqliteFirmwareRepository(session)
    repo.add(make_firmware(model="ESP32", sha256="b" * 64))

    assert repo.get_by_sha256("ESP32-S3", "b" * 64) is None


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


def test_get_latest_for_model_skips_inactive_row(session):
    repo = SqliteFirmwareRepository(session)
    repo.add(make_firmware(version="1.0.0"))
    newest = repo.add(make_firmware(version="1.1.0"))

    repo.deactivate(newest.id)

    latest = repo.get_latest_for_model("ESP32")
    assert latest is not None
    assert latest.version == "1.0.0"


def test_get_latest_for_model_returns_none_when_every_row_inactive(session):
    repo = SqliteFirmwareRepository(session)
    first = repo.add(make_firmware(version="1.0.0"))
    second = repo.add(make_firmware(version="1.1.0"))
    repo.deactivate(first.id)
    repo.deactivate(second.id)

    assert repo.get_latest_for_model("ESP32") is None


def test_list_all_still_returns_inactive_rows(session):
    repo = SqliteFirmwareRepository(session)
    repo.add(make_firmware(version="1.0.0"))
    second = repo.add(make_firmware(version="1.1.0"))

    repo.deactivate(second.id)

    listed = repo.list_all()

    assert len(listed) == 2
    assert {f.active for f in listed} == {True, False}


def test_deactivate_returns_updated_row_and_is_idempotent(session):
    repo = SqliteFirmwareRepository(session)
    added = repo.add(make_firmware())

    first = repo.deactivate(added.id)
    second = repo.deactivate(added.id)

    assert first is not None
    assert first.id == added.id
    assert first.active is False
    assert second is not None
    assert second.id == added.id
    assert second.active is False


def test_deactivate_returns_none_for_unknown_id(session):
    repo = SqliteFirmwareRepository(session)

    assert repo.deactivate(999) is None


def test_device_upsert_inserts_then_updates_same_device(session):
    repo = SqliteDeviceRepository(session)

    inserted = repo.upsert(Device(device_id="dev-1", model="ESP32", current_version="1.0.0"))
    updated = repo.upsert(Device(device_id="dev-1", model="ESP32", current_version="1.1.0"))

    assert updated.id == inserted.id
    assert updated.current_version == "1.1.0"
    assert repo.get_by_device_id("dev-1").current_version == "1.1.0"


def test_device_upsert_returns_the_winning_row_when_two_checkins_race(tmp_path):
    """Two check-ins for one device, both past the lookup before either commits.

    On a file-backed database so the two sessions hold separate connections;
    the shared in-memory one would serialize them and never collide. The winner
    is committed from inside the loser's lookup, which is the only ordering
    that reproduces this without threads.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'race.db'}")
    Base.metadata.create_all(engine)
    checkin = Device(device_id="dev-1", model="ESP32", current_version="1.1.0")

    with Session(engine) as winner_session, Session(engine) as loser_session:
        loser = SqliteDeviceRepository(loser_session)
        lookup = loser_session.scalar

        def commit_the_winner_mid_lookup(*args, **kwargs):
            result = lookup(*args, **kwargs)
            if result is None:
                SqliteDeviceRepository(winner_session).upsert(
                    Device(device_id="dev-1", model="ESP32", current_version="1.0.0")
                )
            return result

        loser_session.scalar = commit_the_winner_mid_lookup

        recorded = loser.upsert(checkin)

    assert recorded.device_id == "dev-1"
    # The losing check-in is dropped rather than raised: a 500 here is a check
    # the device treats as a failure, and it reboots after three of those.
    assert recorded.current_version == "1.0.0"


def test_get_by_device_id_returns_none_when_missing(session):
    repo = SqliteDeviceRepository(session)

    assert repo.get_by_device_id("unknown") is None


def test_device_list_all_orders_most_recently_seen_first(session):
    repo = SqliteDeviceRepository(session)
    older = datetime(2026, 7, 1, 12, 0, 0)
    newer = datetime(2026, 7, 2, 12, 0, 0)
    repo.upsert(Device(device_id="dev-old", model="ESP32", last_seen=older))
    repo.upsert(Device(device_id="dev-new", model="ESP32", last_seen=newer))
    repo.upsert(Device(device_id="dev-never", model="ESP32", last_seen=None))

    listed = repo.list_all()

    assert [d.device_id for d in listed] == ["dev-new", "dev-old", "dev-never"]


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


def test_get_user_by_username_returns_none_when_missing(session):
    repo = SqliteUserRepository(session)

    assert repo.get_by_username("nobody") is None


def test_every_repository_hands_back_aware_timestamps(session):
    """SQLite has no timezone type, so a round-trip strips the offset.

    Re-attaching it is the repository's job. If it were each caller's, the
    routes would have to remember, and one of them would eventually not.
    """
    firmware = SqliteFirmwareRepository(session).add(make_firmware())
    user = SqliteUserRepository(session).add(make_user())
    device = SqliteDeviceRepository(session).upsert(
        Device(
            device_id="aa:bb:cc",
            model="ESP32",
            current_version="1.0.0",
            last_seen=datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc),
        )
    )

    assert firmware.created_at.tzinfo is not None
    assert user.created_at.tzinfo is not None
    assert device.last_seen == datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
