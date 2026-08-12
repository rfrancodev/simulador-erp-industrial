"""Test Alembic migrations."""

from alembic import command
from alembic.config import Config


def test_migration_upgrade_and_downgrade() -> None:
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "-1")
    command.upgrade(alembic_cfg, "head")
