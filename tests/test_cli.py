"""CLI tests for glvalve — written before the CLI implementation (red-first).

Contract:
  domain error  -> return 1, message on stderr, stdout EMPTY, no traceback
  usage error   -> argparse SystemExit(2)
  success       -> return 0, formatted output on stdout
"""

import json
import subprocess
import sys

import pytest

from glvalve.cli import main


class TestHydrostaticCli:
    def test_cli_hydrostatic_prints_psi_and_returns_zero(self, capsys):
        rc = main(["hydrostatic", "15", "3500"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "2730.00" in out
        assert "psi" in out

    def test_cli_hydrostatic_json_is_parseable_dict(self, capsys):
        rc = main(["hydrostatic", "15", "3500", "--json"])
        out = capsys.readouterr().out
        assert rc == 0
        data = json.loads(out)
        assert isinstance(data, dict)
        assert data["pressure_psi"] == pytest.approx(2730.0, rel=1e-9)

    def test_cli_hydrostatic_negative_writes_stderr_and_returns_one(self, capsys):
        rc = main(["hydrostatic", "-15", "3500"])
        captured = capsys.readouterr()
        assert rc == 1
        assert captured.out == ""
        assert "mw_ppg" in captured.err


class TestValveCli:
    def test_cli_valve_prints_depth_and_returns_zero(self, capsys):
        rc = main(["valve", "--disc", "1200", "--tubing", "300",
                   "--gradient", "0.4", "--margin", "100"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "2000.00" in out
        assert "ft" in out

    def test_cli_valve_margin_defaults_to_zero(self, capsys):
        rc = main(["valve", "--disc", "1200", "--tubing", "300",
                   "--gradient", "0.4"])
        assert rc == 0
        assert "2250.00" in capsys.readouterr().out

    def test_cli_valve_json_emits_dict(self, capsys):
        rc = main(["valve", "--disc", "1200", "--tubing", "300",
                   "--gradient", "0.4", "--margin", "100", "--json"])
        data = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert isinstance(data, dict)
        assert data["depth_ft"] == pytest.approx(2000.0, rel=1e-9)

    def test_cli_zero_gradient_returns_one_with_clear_message(self, capsys):
        rc = main(["valve", "--disc", "1200", "--tubing", "300",
                   "--gradient", "0", "--margin", "100"])
        captured = capsys.readouterr()
        assert rc == 1
        assert captured.out == ""
        assert "gradient" in captured.err


class TestTrainCli:
    TRAIN = ["train", "--disc", "1200", "--tubing", "300", "--gradient", "0.4",
             "--margin", "100", "--n", "4", "--spacing", "500"]

    def test_cli_train_prints_table_with_n_rows(self, capsys):
        rc = main(list(self.TRAIN))
        lines = capsys.readouterr().out.rstrip("\n").split("\n")
        assert rc == 0
        assert len(lines) == 5  # 1 header + 4 data rows (no separator line)
        assert "Profundidade" in lines[0]
        for depth in ("2000.00", "1500.00", "1000.00", "500.00"):
            assert depth in "\n".join(lines[1:])

    def test_cli_train_json_is_list_of_valve_dicts(self, capsys):
        rc = main(self.TRAIN + ["--json"])
        data = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert isinstance(data, list) and len(data) == 4
        assert {d["index"] for d in data} == {1, 2, 3, 4}
        assert data[0]["depth_ft"] == pytest.approx(2000.0, rel=1e-9)

    def test_cli_train_n_zero_json_emits_empty_list(self, capsys):
        rc = main(self.TRAIN[:-2] + ["--n", "0", "--spacing", "500", "--json"])
        assert rc == 0
        assert json.loads(capsys.readouterr().out) == []

    def test_cli_train_n_zero_table_emits_header_only(self, capsys):
        rc = main(self.TRAIN[:-2] + ["--n", "0", "--spacing", "500"])
        lines = capsys.readouterr().out.rstrip("\n").split("\n")
        assert rc == 0
        assert len(lines) == 1  # header only, pinned behavior

    def test_cli_train_mode_fixed_depth(self, capsys):
        rc = main(self.TRAIN + ["--mode", "fixed_depth"])
        out = capsys.readouterr().out
        assert rc == 0
        for depth in ("2000.00", "2500.00", "3000.00", "3500.00"):
            assert depth in out

    def test_cli_train_failure_leaves_stdout_empty(self, capsys):
        # B11: no partial table before the error — stdout must be EMPTY.
        rc = main(self.TRAIN[:-2] + ["--n", "5", "--spacing", "500"])
        captured = capsys.readouterr()
        assert rc == 1
        assert captured.out == ""
        assert "valve 5" in captured.err

    def test_cli_train_unknown_mode_returns_one(self, capsys):
        rc = main(self.TRAIN + ["--mode", "bogus"])
        captured = capsys.readouterr()
        assert rc == 1
        assert captured.out == ""
        assert "mode" in captured.err


class TestExitCodesAndUsage:
    def test_cli_missing_required_flag_returns_two(self):
        with pytest.raises(SystemExit) as exc:
            main(["valve"])
        assert exc.value.code == 2

    def test_cli_unknown_subcommand_returns_two(self):
        with pytest.raises(SystemExit) as exc:
            main(["bogus"])
        assert exc.value.code == 2

    def test_cli_no_subcommand_returns_two(self):
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code == 2

    def test_cli_main_does_not_raise_on_domain_error(self):
        # Domain errors return 1 — never propagate a traceback.
        assert main(["hydrostatic", "-1", "100"]) == 1
        assert main(["valve", "--disc", "1", "--tubing", "1",
                    "--gradient", "0", "--margin", "1"]) == 1
        assert main(["train", "--disc", "1200", "--tubing", "300",
                    "--gradient", "0.4", "--margin", "100",
                    "--n", "5", "--spacing", "500"]) == 1


class TestDecimalsFlag:
    def test_cli_decimals_zero(self, capsys):
        rc = main(["hydrostatic", "15", "3500", "--decimals", "0"])
        assert rc == 0
        assert "2730 psi" in capsys.readouterr().out

    def test_cli_decimals_four(self, capsys):
        rc = main(["hydrostatic", "15", "3500", "--decimals", "4"])
        assert rc == 0
        assert "2730.0000 psi" in capsys.readouterr().out

    def test_cli_decimals_30_rejected_not_traceback(self, capsys):
        rc = main(["hydrostatic", "15", "3500", "--decimals", "30"])
        captured = capsys.readouterr()
        assert rc == 1
        assert captured.out == ""
        assert "decimals" in captured.err

    def test_cli_decimals_negative_rejected_not_traceback(self, capsys):
        rc = main(["hydrostatic", "15", "3500", "--decimals", "-1"])
        captured = capsys.readouterr()
        assert rc == 1
        assert captured.out == ""
        assert "decimals" in captured.err

    def test_cli_rounding_is_half_up_not_bankers(self, capsys):
        # 5.35/2 == the double whose repr is '2.675'; round() gives 2.67.
        rc = main(["valve", "--disc", "5.35", "--tubing", "0",
                   "--gradient", "2", "--margin", "0"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "2.68" in out
        assert "2.67" not in out


class TestJsonRobustness:
    def test_cli_json_disallows_nan_infinity(self, capsys):
        # allow_nan=False: output must be strict JSON, never Infinity/NaN.
        rc = main(["train", "--disc", "1200", "--tubing", "300",
                   "--gradient", "0.4", "--margin", "100",
                   "--n", "4", "--spacing", "500", "--json"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "Infinity" not in out and "NaN" not in out
        json.loads(out)  # strict parse


class TestModuleEntryPoint:
    """B7: __main__.py must be exercised — gate cannot be green with it broken."""

    def test_python_m_glvalve_runs(self):
        proc = subprocess.run(
            [sys.executable, "-m", "glvalve", "hydrostatic", "15", "3500"],
            cwd="/home/fbr/agent-chain-test",
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert "2730.00 psi" in proc.stdout

    def test_python_m_glvalve_domain_error_exit_one(self):
        proc = subprocess.run(
            [sys.executable, "-m", "glvalve", "hydrostatic", "-15", "3500"],
            cwd="/home/fbr/agent-chain-test",
            capture_output=True, text=True,
        )
        assert proc.returncode == 1
        assert proc.stdout == ""
        assert "Traceback" not in proc.stderr
