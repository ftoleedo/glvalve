"""Core physics and validation for glvalve.

Pure module: no print, no input, no sys.exit (verifiable by grep).
All domain errors are :class:`GlValveError` subclasses — never raw
``ValueError``/``TypeError``/``ZeroDivisionError``.

Units
-----
pressure            psi
depth (TVD)         ft            (vertical well assumed)
gradient            psi/ft
mud weight (MW)     ppg

Reference for ``p_tubing_psi``
-----------------------------
Tubing pressure at the top of the valve step (flowline/tubing pressure seen
by the valve's opening calculation), NOT hydrostatic of the column. The
hydrostatic model of the annulus column is captured by ``gradient_psi_per_ft``.

Models (DECISAO:D-001 — see DECISOES.md)
----------------------------------------
``fixed_disc`` (literal reading of the requirement):
    T_i = T_1 + (i-1) * G * spacing          (accumulated tubing pressure)
    D_i = (p_disc - margin - T_i) / G        (depth DECREASES by spacing)
    p_disc constant across the train.

``fixed_depth`` (physically coherent unloading train):
    D_i = D_1 + (i-1) * spacing             (depth INCREASES by spacing)
    p_disc_i = margin + T_1 + G * D_i       (required disc pressure grows)
    p_tubing constant at T_1.

In BOTH modes the Valve invariant holds exactly:
    depth_ft == (p_disc_psi - margin_psi - p_tubing_psi) / gradient_psi_per_ft
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

HYDROSTATIC_CONSTANT: float = 0.052  # psi / (ppg * ft)

MODE_FIXED_DISC = "fixed_disc"
MODE_FIXED_DEPTH = "fixed_depth"
VALID_MODES = (MODE_FIXED_DISC, MODE_FIXED_DEPTH)

MAX_VALVES = 1000
MAX_DECIMALS = 12


class GlValveError(Exception):
    """Base class for all domain errors."""


class ValidationError(GlValveError):
    """Invalid *input*: negative, NaN/inf, zero gradient, non-integer count."""


class ValveTrainError(GlValveError):
    """Invalid *derived result* of a train: depth <= 0 or non-finite at step i."""


@dataclass(frozen=True)
class Valve:
    """One valve of the train, self-describing.

    Invariant (holds in both modes, tested):
        (p_disc_psi - margin_psi - p_tubing_psi) / gradient_psi_per_ft == depth_ft
    """

    index: int
    depth_ft: float
    p_tubing_psi: float
    p_disc_psi: float
    margin_psi: float
    gradient_psi_per_ft: float
    spacing_from_previous_ft: float  # 0.0 for the first valve
    mode: str


def check_number(name: str, value, *, minimum=None, exclusive: bool = False) -> float:
    """Validate a scalar input; return it as float. Raise ValidationError otherwise."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(
            f"{name} must be a number, got {type(value).__name__}: {value!r}"
        )
    v = float(value)
    if not math.isfinite(v):
        raise ValidationError(f"{name} must be finite (got {v!r})")
    if minimum is not None:
        if exclusive and v <= minimum:
            raise ValidationError(f"{name} must be > {minimum} (got {v})")
        if not exclusive and v < minimum:
            raise ValidationError(f"{name} must be >= {minimum} (got {v})")
    return v


def check_int(name: str, value, *, minimum=None, maximum=None) -> int:
    """Validate an integral input (int or integer-valued float)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(
            f"{name} must be an integer, got {type(value).__name__}: {value!r}"
        )
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise ValidationError(f"{name} must be an integer (got {value!r})")
        value = int(value)
    if minimum is not None and value < minimum:
        raise ValidationError(f"{name} must be >= {minimum} (got {value})")
    if maximum is not None and value > maximum:
        raise ValidationError(
            f"{name} must be <= {maximum} (got {value})"
        )
    return value


def hydrostatic_pressure(mw_ppg, tvd_ft) -> float:
    """Hydrostatic pressure [psi] = 0.052 * MW[ppg] * TVD[ft]. Unrounded."""
    mw = check_number("mw_ppg", mw_ppg, minimum=0)
    tvd = check_number("tvd_ft", tvd_ft, minimum=0)
    return HYDROSTATIC_CONSTANT * mw * tvd


def gradient_psi_per_ft(mw_ppg) -> float:
    """Mud hydrostatic gradient [psi/ft] = 0.052 * MW[ppg]."""
    return HYDROSTATIC_CONSTANT * check_number("mw_ppg", mw_ppg, minimum=0)


def valve_depth(p_disc_psi, p_tubing_psi, gradient_psi_per_ft, margin_psi=0.0) -> float:
    """Valve opening depth [ft] = (p_disc - margin - p_tubing) / gradient.

    gradient must be > 0; a non-positive or non-finite *result* is a
    ValidationError (a valve at or above the surface is impossible).
    """
    disc = check_number("p_disc_psi", p_disc_psi, minimum=0)
    tubing = check_number("p_tubing_psi", p_tubing_psi, minimum=0)
    grad = check_number("gradient_psi_per_ft", gradient_psi_per_ft,
                       minimum=0, exclusive=True)
    margin = check_number("margin_psi", margin_psi, minimum=0)
    depth = (disc - margin - tubing) / grad
    if not math.isfinite(depth):
        raise ValidationError(
            "valve depth is not finite (gradient_psi_per_ft too small: "
            f"{grad!r})"
        )
    if depth <= 0:
        raise ValidationError(
            f"valve depth must be > 0 ft (got {depth} ft): p_disc too low for "
            f"p_tubing + margin"
        )
    return depth


def valve_train(p_disc_psi, p_tubing_psi, gradient_psi_per_ft, margin_psi,
               n_valves, spacing_ft, mode=MODE_FIXED_DISC):
    """Build a valve train of ``n_valves`` valves. Eager: returns a list.

    All inputs are validated BEFORE any valve is built (no partial results).
    Any invalid *derived* depth (<= 0 or non-finite) raises ValveTrainError
    carrying the offending valve index and depth — at index 1 or at index N,
    the same physical violation always has the same exception type.
    ``ValidationError`` is reserved for bad *inputs*.
    """
    disc = check_number("p_disc_psi", p_disc_psi, minimum=0)
    tubing = check_number("p_tubing_psi", p_tubing_psi, minimum=0)
    grad = check_number("gradient_psi_per_ft", gradient_psi_per_ft,
                       minimum=0, exclusive=True)
    margin = check_number("margin_psi", margin_psi, minimum=0)
    spacing = check_number("spacing_ft", spacing_ft, minimum=0, exclusive=True)
    n = check_int("n_valves", n_valves, minimum=0, maximum=MAX_VALVES)
    if mode not in VALID_MODES:
        raise ValidationError(
            f"mode must be one of {VALID_MODES}, got {mode!r}"
        )
    if n == 0:
        return []

    increment = grad * spacing  # pressure step per valve (fixed_disc)
    valves = []
    for i in range(1, n + 1):
        step = i - 1
        if mode == MODE_FIXED_DISC:
            # Literal reading: p_disc fixed, tubing pressure accumulates.
            t_i = tubing + step * increment
            if not math.isfinite(t_i):
                raise ValveTrainError(
                    f"valve {i}: accumulated p_tubing is not finite "
                    f"(gradient*spacing overflow at step {step})"
                )
            d_i = (disc - margin - t_i) / grad
            p_disc_i = disc
        else:  # MODE_FIXED_DEPTH
            # Physical train: spacing in depth, required disc pressure grows.
            d_1 = (disc - margin - tubing) / grad
            d_i = d_1 + step * spacing
            p_disc_i = margin + tubing + grad * d_i
            t_i = tubing
        if not math.isfinite(d_i):
            raise ValveTrainError(
                f"valve {i}: depth is not finite (inputs overflow at step {step})"
            )
        if d_i <= 0:
            raise ValveTrainError(
                f"valve {i}: depth {d_i} ft <= 0 — train cannot be set deeper "
                f"than the surface with p_disc={disc} psi"
            )
        valves.append(
            Valve(
                index=i,
                depth_ft=d_i,
                p_tubing_psi=t_i,
                p_disc_psi=p_disc_i,
                margin_psi=margin,
                gradient_psi_per_ft=grad,
                spacing_from_previous_ft=0.0 if i == 1 else spacing,
                mode=mode,
            )
        )
    return valves


def round_half_up(value, ndigits=2) -> float:
    """Round half UP (away from zero) on the *decimal* value, not the binary float.

    Uses ``Decimal(str(value))`` on purpose: ``Decimal(2.675)`` is
    2.67499999... in binary and would round to 2.67; the human typed a
    decimal, so we round the decimal representation.
    ``ndigits`` must be within [0, MAX_DECIMALS].
    """
    v = check_number("value", value)
    nd = check_int("decimals", ndigits, minimum=0, maximum=MAX_DECIMALS)
    quantum = Decimal(1).scaleb(-nd)
    return float(Decimal(str(v)).quantize(quantum, rounding=ROUND_HALF_UP))
