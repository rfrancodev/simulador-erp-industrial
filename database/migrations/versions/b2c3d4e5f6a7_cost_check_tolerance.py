"""relax cost_records CHECK constraints to tolerance-based comparison

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-12 00:00:00.000000

The original equality CHECK constraints (planned_total_cost = sum of components)
fail on SQLite for non-round Decimal values because SQLite stores NUMERIC as
REAL and floating-point rounding breaks exact equality. PostgreSQL NUMERIC is
exact, so a tolerance (< 0.01) preserves the invariant while remaining exact
enough to catch real inconsistencies (>= 1 cent drift).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_PLANNED = (
    "ABS(planned_total_cost - (planned_material_cost + planned_labor_cost "
    "+ planned_machine_cost + planned_energy_cost)) < 0.01"
)
_NEW_ACTUAL = (
    "actual_total_cost IS NULL OR ABS(actual_total_cost - "
    "(COALESCE(actual_material_cost, 0) + COALESCE(actual_labor_cost, 0) "
    "+ COALESCE(actual_machine_cost, 0) + COALESCE(actual_energy_cost, 0))) < 0.01"
)

_OLD_PLANNED = (
    "planned_total_cost = planned_material_cost + planned_labor_cost "
    "+ planned_machine_cost + planned_energy_cost"
)
_OLD_ACTUAL = (
    "actual_total_cost IS NULL OR actual_total_cost = "
    "COALESCE(actual_material_cost, 0) + COALESCE(actual_labor_cost, 0) "
    "+ COALESCE(actual_machine_cost, 0) + COALESCE(actual_energy_cost, 0)"
)


def upgrade() -> None:
    with op.batch_alter_table("cost_records") as batch_op:
        batch_op.drop_constraint("ck_cost_planned_total", type_="check")
        batch_op.drop_constraint("ck_cost_actual_total", type_="check")
        batch_op.create_check_constraint("ck_cost_planned_total", _NEW_PLANNED)
        batch_op.create_check_constraint("ck_cost_actual_total", _NEW_ACTUAL)


def downgrade() -> None:
    with op.batch_alter_table("cost_records") as batch_op:
        batch_op.drop_constraint("ck_cost_planned_total", type_="check")
        batch_op.drop_constraint("ck_cost_actual_total", type_="check")
        batch_op.create_check_constraint("ck_cost_planned_total", _OLD_PLANNED)
        batch_op.create_check_constraint("ck_cost_actual_total", _OLD_ACTUAL)
