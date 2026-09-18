"""glvalve — gas-lift unloading valve train calculator (stdlib only).

Public API (see README.md for formulas and units).

DECISAO:D-001 — the valve-train model is ambiguous in the source requirement.
Two explicit modes are provided: ``fixed_disc`` (literal reading) and
``fixed_depth`` (physically coherent unloading train). See DECISOES.md.
"""

from glvalve.core import (
    GlValveError,
    ValidationError,
    ValveTrainError,
    Valve,
    hydrostatic_pressure,
    gradient_psi_per_ft,
    valve_depth,
    valve_train,
    round_half_up,
)

__version__ = "0.1.0"

__all__ = [
    "GlValveError",
    "ValidationError",
    "ValveTrainError",
    "Valve",
    "hydrostatic_pressure",
    "gradient_psi_per_ft",
    "valve_depth",
    "valve_train",
    "round_half_up",
    "__version__",
]
