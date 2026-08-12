#!/usr/bin/env python
"""Generate and seed synthetic industrial ERP data.

Usage:
    .venv/bin/python -m scripts.generate_data --months 12 --scenario normal

For convenience this creates any missing tables. In production prefer
``alembic upgrade head`` before seeding.
"""

from __future__ import annotations

import argparse

from sqlalchemy.orm import Session

from app.database.connection import get_engine
from app.domain.entities import Base
from app.simulation.config import SimulationConfig
from app.simulation.engine import SimulationEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic ERP data.")
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scenario", choices=["normal", "crisis"], default="normal")
    parser.add_argument("--orders-per-month", type=int, default=15)
    args = parser.parse_args()

    engine = get_engine()
    Base.metadata.create_all(engine)

    config = SimulationConfig.from_env(
        months=args.months,
        seed=args.seed,
        scenario=args.scenario,
        orders_per_month=args.orders_per_month,
    )

    with Session(engine) as session:
        summary = SimulationEngine(session, config).run()
        print(f"Simulation complete ({config.scenario} scenario, {config.months} months).")
        print(f"  production orders: {summary.orders}")
        print(f"  batches:           {summary.batches}")
        print(f"  inspections:       {summary.inspections}")
        print(f"  non-conformities:  {summary.non_conformities}")
        print(f"  cost records:      {summary.cost_records}")
        print(f"  total records:     {summary.total_records()}")


if __name__ == "__main__":
    main()
