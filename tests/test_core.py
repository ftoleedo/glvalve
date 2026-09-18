"""Core tests for glvalve.

Written BEFORE the core implementation (red-first protocol).
Every expected number was hand-derived; derivations are in the docstrings.

Units: pressure psi, depth ft, gradient psi/ft, mud weight ppg.
"""

import inspect
import json
from dataclasses import asdict

import pytest

from glvalve import (
    GlValveError,
    ValidationError,
    ValveTrainError,
    Valve,
    gradient_psi_per_ft,
    hydrostatic_pressure,
    round_half_up,
    valve_depth,
    valve_train,
)

# Worked example (fixed_disc / literal reading):
#   disc=1200, tubing=300, G=0.4, margin=100, spacing=500, N=4
#   T_i = 300 + (i-1)*0.4*500 = 300,500,700,900
#   D_i = (1200 - 100 - T_i)/0.4 = 2000,1500,1000,500
CLEAN = dict(p_disc_psi=1200.0, p_tubing_psi=300.0, gradient_psi_per_ft=0.4,
             margin_psi=100.0)


def approx(x):
    """Relative tolerance: abs=1e-9 is meaningless across 30 orders of magnitude."""
    return pytest.approx(x, rel=1e-9)


class TestHydrostatic:
    def test_hydrostatic_known_value(self):
        # 0.052 * 15 * 3500 = 2730.0
        assert hydrostatic_pressure(15.0, 3500.0) == approx(2730.0)

    def test_hydrostatic_zero_tvd_is_zero(self):
        assert hydrostatic_pressure(15.0, 0.0) == 0.0

    def test_hydrostatic_proportional_to_mw_and_tvd(self):
        base = hydrostatic_pressure(10.0, 1000.0)
        assert hydrostatic_pressure(20.0, 1000.0) == approx(2 * base)
        assert hydrostatic_pressure(10.0, 2000.0) == approx(2 * base)

    def test_hydrostatic_negative_mw_raises(self):
        with pytest.raises(ValidationError) as exc:
            hydrostatic_pressure(-1.0, 1000.0)
        assert "mw_ppg" in str(exc.value)

    def test_hydrostatic_negative_tvd_raises(self):
        with pytest.raises(ValidationError) as exc:
            hydrostatic_pressure(15.0, -1.0)
        assert "tvd_ft" in str(exc.value)

    def test_hydrostatic_nan_and_inf_raise(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with pytest.raises(ValidationError):
                hydrostatic_pressure(bad, 1000.0)
            with pytest.raises(ValidationError):
                hydrostatic_pressure(15.0, bad)

    def test_hydrostatic_accepts_int_inputs(self):
        result = hydrostatic_pressure(15, 3500)
        assert isinstance(result, float)
        assert result == approx(2730.0)

    def test_hydrostatic_returns_unrounded_float(self):
        # 0.052 * 10.1 * 1234 = 648.0968  (plan said 647.5248 — wrong, DA B4)
        value = hydrostatic_pressure(10.1, 1234.0)
        assert value == approx(648.0968)
        assert value != round(value, 2)  # core does NOT round

    def test_hydrostatic_rejects_non_numeric(self):
        with pytest.raises(ValidationError):
            hydrostatic_pressure("15", 1000.0)
        with pytest.raises(ValidationError):
            hydrostatic_pressure(True, 1000.0)


class TestGradientHelper:
    def test_gradient_from_mw(self):
        # 0.052 * 8.33 = 0.43316
        assert gradient_psi_per_ft(8.33) == approx(0.43316)

    def test_gradient_zero_mw_is_zero(self):
        assert gradient_psi_per_ft(0.0) == 0.0

    def test_gradient_negative_mw_raises(self):
        with pytest.raises(ValidationError) as exc:
            gradient_psi_per_ft(-8.0)
        assert "mw_ppg" in str(exc.value)


class TestValveDepth:
    def test_valve_depth_clean_value(self):
        # (1200 - 100 - 300) / 0.4 = 800/0.4 = 2000
        assert valve_depth(1200.0, 300.0, 0.4, 100.0) == approx(2000.0)

    def test_valve_depth_margin_shifts_depth_by_margin_over_gradient(self):
        # (1200 - 200 - 300)/0.4 = 1750 ; delta = 100/0.4 = 250 ft
        assert valve_depth(1200.0, 300.0, 0.4, 200.0) == approx(1750.0)

    def test_valve_depth_zero_gradient_raises_validation_error_not_zero_division(self):
        with pytest.raises(ValidationError) as exc:
            valve_depth(1200.0, 300.0, 0.0, 100.0)
        assert excinfo_type_is(exc, ValidationError)
        assert "gradient" in str(exc.value)

    def test_valve_depth_negative_gradient_raises(self):
        with pytest.raises(ValidationError) as exc:
            valve_depth(1200.0, 300.0, -0.4, 100.0)
        assert "gradient" in str(exc.value)

    def test_valve_depth_negative_result_raises(self):
        # (300 - 100 - 300)/0.4 = -250 ft -> impossible well
        with pytest.raises(ValidationError) as exc:
            valve_depth(300.0, 300.0, 0.4, 100.0)
        assert "depth" in str(exc.value)

    def test_valve_depth_zero_result_raises(self):
        # (400 - 100 - 300)/0.4 = 0 ft -> valve at surface is invalid
        with pytest.raises(ValidationError) as exc:
            valve_depth(400.0, 300.0, 0.4, 100.0)
        assert "depth" in str(exc.value)

    def test_valve_depth_zero_margin_is_valid(self):
        # (1200 - 0 - 300)/0.4 = 2250
        assert valve_depth(1200.0, 300.0, 0.4, 0.0) == approx(2250.0)

    def test_valve_depth_margin_defaults_to_zero(self):
        assert valve_depth(1200.0, 300.0, 0.4) == approx(2250.0)

    def test_valve_depth_negative_pressures_raise(self):
        with pytest.raises(ValidationError) as exc:
            valve_depth(-1200.0, 300.0, 0.4, 100.0)
        assert "p_disc_psi" in str(exc.value)
        with pytest.raises(ValidationError) as exc:
            valve_depth(1200.0, -300.0, 0.4, 100.0)
        assert "p_tubing_psi" in str(exc.value)

    def test_valve_depth_tiny_gradient_does_not_leak_infinity(self):
        # 800 / 5e-324 -> inf. Must be caught, never returned.
        with pytest.raises(ValidationError) as exc:
            valve_depth(1200.0, 300.0, 5e-324, 100.0)
        assert "finite" in str(exc.value)

    def test_valve_depth_nan_inputs_raise(self):
        for bad in (float("nan"), float("inf")):
            with pytest.raises(ValidationError):
                valve_depth(bad, 300.0, 0.4, 100.0)


def excinfo_type_is(exc, expected):
    return type(exc.value) is expected


class TestValveTrainFixedDisc:
    def test_valve_train_n_zero_returns_empty_list(self):
        result = valve_train(n_valves=0, spacing_ft=500.0, **CLEAN)
        assert result == []

    def test_valve_train_n_one_matches_valve_depth(self):
        train = valve_train(n_valves=1, spacing_ft=500.0, **CLEAN)
        assert len(train) == 1
        # two different code paths -> approx, never ==
        assert train[0].depth_ft == approx(valve_depth(1200.0, 300.0, 0.4, 100.0))
        assert train[0].spacing_from_previous_ft == 0.0

    def test_valve_train_spacing_recursion(self):
        train = valve_train(n_valves=4, spacing_ft=500.0, **CLEAN)
        assert [v.depth_ft for v in train] == approx([2000.0, 1500.0, 1000.0, 500.0])
        assert [v.p_tubing_psi for v in train] == approx([300.0, 500.0, 700.0, 900.0])

    def test_valve_train_depth_step_equals_spacing(self):
        # DECISAO:D-001 fixed_disc: D_{i+1} = D_i - spacing (literal reading)
        train = valve_train(n_valves=4, spacing_ft=500.0, **CLEAN)
        for a, b in zip(train, train[1:]):
            assert b.depth_ft - a.depth_ft == approx(-500.0)

    def test_valve_train_negative_n_raises(self):
        with pytest.raises(ValidationError) as exc:
            valve_train(n_valves=-1, spacing_ft=500.0, **CLEAN)
        assert "n_valves" in str(exc.value)

    def test_valve_train_zero_or_negative_spacing_raises(self):
        for bad in (0.0, -500.0):
            with pytest.raises(ValidationError) as exc:
                valve_train(n_valves=3, spacing_ft=bad, **CLEAN)
            assert "spacing" in str(exc.value)

    def test_valve_train_raises_when_depth_reaches_surface(self):
        # 5th valve would be at 0 ft
        with pytest.raises(ValveTrainError) as exc:
            valve_train(n_valves=5, spacing_ft=500.0, **CLEAN)
        msg = str(exc.value)
        assert "5" in msg      # offending index
        assert "0" in msg     # violated depth

    def test_valve_train_indices_are_one_based_and_contiguous(self):
        train = valve_train(n_valves=4, spacing_ft=500.0, **CLEAN)
        assert [v.index for v in train] == [1, 2, 3, 4]

    def test_valve_train_is_eager_not_generator(self):
        # A lazy generator would let cmd_train print a partial table then crash.
        train = valve_train(n_valves=4, spacing_ft=500.0, **CLEAN)
        assert isinstance(train, list)
        assert not inspect.isgenerator(train)
        assert not inspect.isgeneratorfunction(valve_train)

    def test_valve_train_echoes_inputs_on_every_valve(self):
        train = valve_train(n_valves=4, spacing_ft=500.0, **CLEAN)
        for v in train:
            assert v.p_disc_psi == 1200.0
            assert v.margin_psi == 100.0
            assert v.gradient_psi_per_ft == 0.4
            assert v.mode == "fixed_disc"

    def test_valve_train_spacing_recorded_on_every_valve_after_first(self):
        train = valve_train(n_valves=4, spacing_ft=500.0, **CLEAN)
        assert [v.spacing_from_previous_ft for v in train] == [0.0, 500.0, 500.0, 500.0]


class TestValveTrainFixedDepth:
    def test_fixed_depth_goes_deeper(self):
        # D_i = 2000 + (i-1)*500 = 2000,2500,3000,3500
        train = valve_train(n_valves=4, spacing_ft=500.0, mode="fixed_depth", **CLEAN)
        assert [v.depth_ft for v in train] == approx([2000.0, 2500.0, 3000.0, 3500.0])

    def test_fixed_depth_required_disc_grows_by_gradient_times_spacing(self):
        # p_disc_i = margin + T1 + G*D_i = 100+300+0.4*D_i = 1200,1400,1600,1800
        train = valve_train(n_valves=4, spacing_ft=500.0, mode="fixed_depth", **CLEAN)
        assert [v.p_disc_psi for v in train] == approx([1200.0, 1400.0, 1600.0, 1800.0])

    def test_fixed_depth_p_tubing_is_constant(self):
        train = valve_train(n_valves=4, spacing_ft=500.0, mode="fixed_depth", **CLEAN)
        assert [v.p_tubing_psi for v in train] == approx([300.0] * 4)

    def test_fixed_depth_never_hits_surface(self):
        train = valve_train(n_valves=10, spacing_ft=500.0, mode="fixed_depth", **CLEAN)
        assert all(v.depth_ft > 0 for v in train)


class TestValveInvariant:
    """Strongest oracle available: the Valve must be self-describing in BOTH modes."""

    @pytest.mark.parametrize("mode", ["fixed_disc", "fixed_depth"])
    def test_valve_is_self_describing(self, mode):
        train = valve_train(n_valves=4, spacing_ft=500.0, mode=mode, **CLEAN)
        for v in train:
            recomputed = (v.p_disc_psi - v.margin_psi - v.p_tubing_psi) / v.gradient_psi_per_ft
            assert recomputed == approx(v.depth_ft)

    @pytest.mark.parametrize("mode", ["fixed_disc", "fixed_depth"])
    def test_every_depth_is_positive_and_finite(self, mode):
        import math
        train = valve_train(n_valves=4, spacing_ft=500.0, mode=mode, **CLEAN)
        for v in train:
            assert math.isfinite(v.depth_ft) and v.depth_ft > 0
            assert math.isfinite(v.p_disc_psi) and math.isfinite(v.p_tubing_psi)


class TestValveTrainContractConsistency:
    def test_surface_violation_is_train_error_at_index_one(self):
        # Same physical violation must be ValveTrainError at ANY index, not
        # ValidationError at index 1 and ValveTrainError at index 5.
        with pytest.raises(ValveTrainError) as exc:
            valve_train(p_disc_psi=300.0, p_tubing_psi=300.0,
                      gradient_psi_per_ft=0.4, margin_psi=100.0,
                      n_valves=1, spacing_ft=500.0)
        assert "1" in str(exc.value)

    def test_train_error_is_a_glvalve_error(self):
        with pytest.raises(GlValveError):
            valve_train(n_valves=5, spacing_ft=500.0, **CLEAN)

    def test_unknown_mode_raises(self):
        with pytest.raises(ValidationError) as exc:
            valve_train(n_valves=2, spacing_ft=500.0, mode="bogus", **CLEAN)
        assert "mode" in str(exc.value)

    def test_n_above_cap_raises_before_building(self):
        with pytest.raises(ValidationError) as exc:
            valve_train(n_valves=1001, spacing_ft=500.0, **CLEAN)
        assert "n_valves" in str(exc.value)

    def test_non_integer_n_raises_validation_error_not_type_error(self):
        with pytest.raises(ValidationError) as exc:
            valve_train(n_valves=2.5, spacing_ft=500.0, **CLEAN)
        assert "n_valves" in str(exc.value)

    def test_integral_float_n_is_accepted(self):
        assert len(valve_train(n_valves=3.0, spacing_ft=500.0, **CLEAN)) == 3

    def test_derived_tubing_pressure_must_stay_finite(self):
        # huge spacing x gradient overflows -> must raise, not emit inf
        with pytest.raises(ValveTrainError):
            valve_train(p_disc_psi=1e308, p_tubing_psi=1e308,
                       gradient_psi_per_ft=1e308, margin_psi=0.0,
                       n_valves=3, spacing_ft=1e308)


class TestValveDataclass:
    def test_valve_is_frozen(self):
        train = valve_train(n_valves=1, spacing_ft=500.0, **CLEAN)
        with pytest.raises(Exception):
            train[0].depth_ft = 1.0

    def test_valve_serializes_to_json_friendly_dict(self):
        train = valve_train(n_valves=2, spacing_ft=500.0, **CLEAN)
        payload = json.dumps([asdict(v) for v in train], allow_nan=False)
        parsed = json.loads(payload)
        assert len(parsed) == 2
        assert set(parsed[0]) == {
            "index", "depth_ft", "p_tubing_psi", "p_disc_psi",
            "margin_psi", "gradient_psi_per_ft", "spacing_from_previous_ft", "mode",
        }


class TestRoundHalfUp:
    def test_half_rounds_up_not_bankers(self):
        # Decimal(str(2.675)) == Decimal('2.675') exactly -> 2.68
        assert round_half_up(2.675, 2) == 2.68

    def test_negative_half_rounds_away_from_zero(self):
        assert round_half_up(-2.675, 2) == -2.68

    def test_below_half_rounds_down(self):
        assert round_half_up(2.674, 2) == 2.67

    def test_zero_decimals(self):
        assert round_half_up(2.5, 0) == 3.0
        assert round_half_up(-2.5, 0) == -3.0

    def test_four_decimals(self):
        assert round_half_up(1.23455, 4) == 1.2346

    def test_out_of_range_decimals_raise(self):
        for bad in (-1, 13, 30):
            with pytest.raises(ValidationError) as exc:
                round_half_up(1.0, bad)
            assert "decimals" in str(exc.value)

    def test_non_finite_value_raises(self):
        with pytest.raises(ValidationError):
            round_half_up(float("nan"), 2)
