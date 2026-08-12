"""Industrial ERP Simulator — Simulation engine.

Generates synthetic PP-PI / QM / CO data. See ``app/simulation/engine.py`` for
the :class:`SimulationEngine` and ``scripts/generate_data.py`` for the CLI.
"""

from app.simulation.config import SimulationConfig, SimulationSummary
from app.simulation.engine import SimulationEngine

__all__ = ["SimulationConfig", "SimulationEngine", "SimulationSummary"]
