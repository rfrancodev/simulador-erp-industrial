"""QM data generator — quality inspections and non-conformities.

Synthetic data — for educational and simulation purposes only.
"""

from __future__ import annotations

from app.domain.entities import Batch, NonConformity, QualityInspection
from app.domain.quality.inspection import (
    DefectDisposition,
    DefectSeverity,
    InspectionStatus,
)
from app.simulation.config import MonthParams, SimulationContext, to_decimal

_DEFECTS = [
    ("CO2_LEVEL", "CO2 level below specification", DefectSeverity.MAJOR, DefectDisposition.REWORK),
    ("PH_OFF_SPEC", "pH outside specification range", DefectSeverity.MAJOR, DefectDisposition.REWORK),
    ("ALCOHOL_LOW", "Alcohol content below target", DefectSeverity.CRITICAL, DefectDisposition.SCRAP),
    ("APPEARANCE", "Haze or turbidity detected", DefectSeverity.MINOR, DefectDisposition.USE_AS_IS),
    ("MICROBIAL", "Microbiological contamination", DefectSeverity.CRITICAL, DefectDisposition.SCRAP),
]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def generate_inspection(
    ctx: SimulationContext,
    batch: Batch,
    alcohol_target: float,
    params: MonthParams,
) -> QualityInspection:
    """Generate a quality inspection for a batch (PASSED or FAILED)."""
    rng = ctx.rng
    failed = rng.random() < params.inspection_failure_rate

    if failed:
        ph_raw = _clamp(rng.gauss(3.8, 0.3), 0.0, 9.99)
        appearance = rng.choice(["HAZY", "TURBID"])
        microbiological = "POSITIVE" if rng.random() < 0.2 else "NEGATIVE"
    else:
        ph_raw = _clamp(rng.gauss(4.2, 0.1), 0.0, 9.99)
        appearance = "CLEAR"
        microbiological = "NEGATIVE"

    ctx.seq_inspection += 1
    completed_at = batch.completed_at
    inspection = QualityInspection(
        batch_id=batch.id,
        inspection_lot=f"QI-{completed_at.year}-{ctx.seq_inspection:05d}",
        inspection_status=(
            InspectionStatus.FAILED.value if failed else InspectionStatus.PASSED.value
        ),
        pH=to_decimal(ph_raw, 2),
        alcohol_percent=to_decimal(_clamp(rng.gauss(alcohol_target, 0.2), 0.0, 99.9), 1),
        temperature=to_decimal(_clamp(rng.gauss(20.0, 1.0), -50.0, 150.0), 1),
        co2_level=to_decimal(_clamp(rng.gauss(2.5, 0.15), 0.0, 99.99), 2),
        appearance=appearance,
        microbiological_status=microbiological,
        inspection_date=completed_at,
        result_date=completed_at,
    )
    ctx.session.add(inspection)
    ctx.summary.inspections += 1
    ctx.session.flush()  # populate inspection.id before adding non-conformities

    if failed:
        for defect_type, description, severity, disposition in rng.sample(
            _DEFECTS, rng.randint(1, 2)
        ):
            ctx.seq_defect += 1
            ctx.session.add(
                NonConformity(
                    inspection_id=inspection.id,
                    defect_type=defect_type,
                    defect_code=f"NC-{ctx.seq_defect:04d}",
                    description=description,
                    severity=severity.value,
                    disposition=disposition.value,
                )
            )
            ctx.summary.non_conformities += 1

    return inspection
