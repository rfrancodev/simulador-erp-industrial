#!/usr/bin/env python
"""Reset all domain tables, preserving user accounts.

Usage:
    .venv/bin/python -m scripts.reset_database --yes

Deletes every PP-PI / QM / CO record so a fresh simulation can be seeded. The
``users`` table (authentication) is intentionally preserved. A confirmation is
required unless ``--yes`` is passed, to prevent accidental data loss.
"""

from __future__ import annotations

import argparse

from sqlalchemy.orm import Session

from app.database.connection import get_engine
from app.domain.entities import Base

_PRESERVED_TABLES = {"users"}


def reset_domain_data(session: Session) -> None:
    """Delete every domain table (children first), preserving ``users``."""
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in _PRESERVED_TABLES:
            continue
        session.execute(table.delete())
    session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset all domain tables.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation prompt.",
    )
    args = parser.parse_args()

    if not args.yes:
        answer = input(
            "This will delete ALL production, quality and cost data "
            "(user accounts are preserved). Type 'yes' to continue: "
        )
        if answer.strip().lower() != "yes":
            print("Aborted.")
            return

    engine = get_engine()
    with Session(engine) as session:
        reset_domain_data(session)
        print("Database reset complete (user accounts preserved).")


if __name__ == "__main__":
    main()
