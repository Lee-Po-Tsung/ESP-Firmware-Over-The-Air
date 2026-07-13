"""Create a dashboard account from the command line.

Solves the bootstrap problem: the first admin cannot be made through the
admin-only paths, so seed it here. Also handy for scripted operator accounts.

    uv run python backend/scripts/create_user.py --username admin --role admin
    uv run python backend/scripts/create_user.py --username bob      # operator

The password is read interactively (or from the OTA_USER_PASSWORD env var for
non-interactive use) so it never lands in shell history.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from application.auth import RegisterUser, RegisterUserRequest  # noqa: E402
from domain.models import Role  # noqa: E402
from infrastructure.db import SessionLocal  # noqa: E402
from infrastructure.sqlite_repo import SqliteUserRepository  # noqa: E402
from ports.repository import UserAlreadyExists  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a dashboard user.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--role", choices=[r.value for r in Role], default=Role.OPERATOR.value)
    args = parser.parse_args()

    password = os.environ.get("OTA_USER_PASSWORD") or getpass.getpass("Password: ")
    if not password:
        print("Password must not be empty.", file=sys.stderr)
        return 1

    session = SessionLocal()
    try:
        use_case = RegisterUser(SqliteUserRepository(session))
        try:
            user = use_case.execute(
                RegisterUserRequest(username=args.username, password=password, role=Role(args.role))
            )
        except UserAlreadyExists:
            print(f"User '{args.username}' already exists.", file=sys.stderr)
            return 1
    finally:
        session.close()

    print(f"Created {user.role.value} '{user.username}' (id={user.id}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
