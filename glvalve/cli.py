"""CLI layer for glvalve — parsing, formatting, exit codes.

Exit-code contract:
    0  success
    1  domain error (GlValveError) — message on stderr, stdout untouched
    2  usage error — argparse SystemExit(2) (missing flag / unknown subcommand)

``main`` never lets a domain exception escape as a traceback.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from glvalve.core import (
    MAX_DECIMALS,
    MODE_FIXED_DISC,
    VALID_MODES,
    GlValveError,
    check_int,
    hydrostatic_pressure,
    round_half_up,
    valve_depth,
    valve_train,
)


def _fmt(value: float, decimals: int) -> str:
    """Present with ROUND_HALF_UP at the requested precision."""
    return f"{round_half_up(value, decimals):.{decimals}f}"


def _decimals(args) -> int:
    return check_int("decimals", args.decimals, minimum=0, maximum=MAX_DECIMALS)


def _dump(obj) -> str:
    # allow_nan=False: strict JSON — Infinity/NaN must never reach a consumer.
    return json.dumps(obj, allow_nan=False)


def cmd_hydrostatic(args) -> int:
    dec = _decimals(args)
    pressure = hydrostatic_pressure(args.mw_ppg, args.tvd_ft)
    if args.json:
        print(_dump({
            "mw_ppg": args.mw_ppg,
            "tvd_ft": args.tvd_ft,
            "pressure_psi": pressure,
        }))
    else:
        print(f"{_fmt(pressure, dec)} psi")
    return 0


def cmd_valve(args) -> int:
    dec = _decimals(args)
    depth = valve_depth(args.disc, args.tubing, args.gradient, args.margin)
    if args.json:
        print(_dump({
            "p_disc_psi": args.disc,
            "p_tubing_psi": args.tubing,
            "gradient_psi_per_ft": args.gradient,
            "margin_psi": args.margin,
            "depth_ft": depth,
        }))
    else:
        print(f"{_fmt(depth, dec)} ft")
    return 0


def cmd_train(args) -> int:
    dec = _decimals(args)
    train = valve_train(args.disc, args.tubing, args.gradient, args.margin,
                       args.n, args.spacing, mode=args.mode)
    if args.json:
        print(_dump([asdict(v) for v in train]))
        return 0
    # Table is materialized BEFORE anything is printed (no partial output).
    lines = ["#  Profundidade (ft)  p_tubing (psi)  p_disc (psi)"]
    for v in train:
        lines.append(
            f"{v.index}  {_fmt(v.depth_ft, dec):>17}  "
            f"{_fmt(v.p_tubing_psi, dec):>15}  {_fmt(v.p_disc_psi, dec):>14}"
        )
    print("\n".join(lines))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glvalve",
        description="Gas-lift unloading valve train calculator "
                    "(hydrostatic, valve depth, valve train).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--decimals", type=int, default=2,
                      help="output decimals, 0..%d (default 2)" % MAX_DECIMALS)
        p.add_argument("--json", action="store_true",
                      help="emit strict JSON instead of formatted text")

    p_h = sub.add_parser("hydrostatic",
                        help="hydrostatic pressure = 0.052 * MW[ppg] * TVD[ft]")
    p_h.add_argument("mw_ppg", type=float, help="mud weight [ppg]")
    p_h.add_argument("tvd_ft", type=float, help="true vertical depth [ft]")
    common(p_h)
    p_h.set_defaults(func=cmd_hydrostatic)

    p_v = sub.add_parser("valve",
                        help="valve depth = (p_disc - margin - p_tubing)/gradient")
    p_v.add_argument("--disc", type=float, required=True,
                     help="valve dome/charging pressure p_disc [psi]")
    p_v.add_argument("--tubing", type=float, required=True,
                     help="tubing/flowline pressure p_tubing [psi]")
    p_v.add_argument("--gradient", type=float, required=True,
                     help="gradient [psi/ft] (must be > 0)")
    p_v.add_argument("--margin", type=float, default=0.0,
                     help="safety margin [psi] (default 0)")
    common(p_v)
    p_v.set_defaults(func=cmd_valve)

    p_t = sub.add_parser("train", help="build an unloading valve train")
    p_t.add_argument("--disc", type=float, required=True)
    p_t.add_argument("--tubing", type=float, required=True)
    p_t.add_argument("--gradient", type=float, required=True)
    p_t.add_argument("--margin", type=float, default=0.0)
    p_t.add_argument("--n", type=int, required=True, help="number of valves")
    p_t.add_argument("--spacing", type=float, required=True,
                     help="valve spacing (ft in fixed_depth, pressure-step "
                          "distance in fixed_disc)")
    p_t.add_argument("--mode", default=MODE_FIXED_DISC,
                     help="train model: %s (default: fixed_disc — literal; "
                          "see DECISAO:D-001)" % " | ".join(VALID_MODES))
    common(p_t)
    p_t.set_defaults(func=cmd_train)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except GlValveError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
