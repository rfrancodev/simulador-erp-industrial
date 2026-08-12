#!/usr/bin/env python
"""Bootstrap CLI to create user accounts.

Usage:
    .venv/bin/python -m scripts.create_user --username admin --role admin

If ``--password`` is omitted the password is read interactively (recommended, so
it does not appear in the process list or shell history).

For convenience this creates any missing tables, so it can also bootstrap the
first admin on a fresh database. In production prefer ``alembic upgrade head``.
"""

from __future__ import annotations

import argparse
import getpass

from sqlalchemy.orm import Session

from app.database.connection import get_engine
from app.domain.auth import UserCreate, UserRole
from app.domain.entities import Base
from app.services.auth_service import AuthService


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an ERP user account.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", help="Omit to prompt securely (recommended)")
    parser.add_argument(
        "--role",
        choices=[r.value for r in UserRole],
        default=UserRole.VIEWER.value,
    )
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password: ")

    engine = get_engine()
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = AuthService(session).create_user(
            UserCreate(username=args.username, password=password, role=UserRole(args.role))
        )
        print(f"User '{user.username}' created with role '{user.role}'.")


if __name__ == "__main__":
    main()
