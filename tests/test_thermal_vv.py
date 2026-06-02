from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from origin_ai_lab.models import SimulationBackend, ThermalSimulationTask
from origin_ai_lab.simulations.thermal import build_thermal_spec
from origin_ai_lab.simulations.thermal_harness import build_golden_case_registry
from origin_ai_lab.simulations.vv import (
    PUBLICATION_EVIDENCE_LEVEL,
    build_boundary_condition_audit_from_proposal,
    build_convergence_study_plan,
    build_energy_balance_check,
    infer_thermal_evidence_level,
    parse_comsol_solver_log,
)
from origin_ai_lab.workflows.thermal_simulation import run_thermal_simulation


class ThermalVVTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="origin-ai-vv-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp)

    def test_parse_comsol_solver_log_extracts_completion_runtime_warning_and_iterations(self) -> None:
        log_text = """
        Stationary Solver 1
        Progress: 12 %
        Iteration 1: Relative residual = 1.2e-2
        Iteration 2: Relative residual = 3.4e-6
        Warning: Reusing previous solution as initial value.
        Elapsed time: 00:00:12
        Progress: 100 %
        Completed.
        """

        summary = parse_comsol_solver_log(log_text, return_code=0)

        self.assertEqual(summary.status, "complete_with_warnings")
        self.assertTrue(summary.completed)
        self.assertEqual(summary.completion_percent, 100.0)
        self.assertEqual(summary.runtime_seconds, 12.0)
        self.assertEqual(summary.warning_count, 1)
        self.assertEqual(summary.iterations[-1].iteration, 2)
        self.assertAlmostEqual(summary.iterations[-1].residual, 3.4e-6)

        localized = parse_comsol_solver_log(
            "\u8fd0\u884c\u65f6\u95f4: 9 s.\n\u603b\u65f6\u95f4: 30 s.\n"
            "---------- \u5f53\u524d\u8fdb\u5ea6: 100 % - \u5b8c\u6210",
            return_code=0,
        )
        self.assertTrue(localized.completed)
        self.assertEqual(localized.runtime_seconds, 30.0)

    def test_parse_comsol_solver_log_detects_failure(self) -> None:
        summary = parse_comsol_solver_log(
            """
            Iteration 1: Relative residual = 1.0e-1
            Error: Failed to assemble the stiffness matrix.
            Elapsed time: 3 s
            """,
            return_code=1,
        )

        self.assertEqual(summary.status, "failed")
        self.assertFalse(summary.completed)
        self.assertEqual(summary.error_count, 1)
        self.assertEqual(summary.runtime_seconds, 3.0)

    def test_boundary_condition_audit_flags_missing_heat_sink(self) -> None:
        audit = build_boundary_condition_audit_from_proposal(
            {
                "heat_sources": [{"id": "chip_heat", "type": "total_power", "target": "chip", "value_W": 5}],
                "boundary_conditions": [{"id": "symmetry", "type": "symmetry", "target": "side_faces"}],
            }
        )

        self.assertEqual(audit.status, "incomplete")
        self.assertTrue(audit.has_heat_input)
        self.assertFalse(audit.has_heat_sink_or_reference)
        self.assertIn("No heat sink or reference temperature boundary was found.", audit.gaps)

    def test_energy_balance_check_accepts_reported_residual(self) -> None:
        balance = build_energy_balance_check({"chip_power_W": 4.0, "energy_balance_error_percent": 0.25})

        self.assertEqual(balance.status, "passed")
        self.assertTrue(balance.passed)
        self.assertEqual(balance.residual_percent, 0.25)
        self.assertEqual(balance.terms[0].value_W, 4.0)

    def test_convergence_plan_defines_mesh_and_time_step_runner_interface(self) -> None:
        spec = build_thermal_spec(
            ThermalSimulationTask(
                goal="validation benchmark for a transient thermal case",
                backend=SimulationBackend.DRY_RUN,
                study_type="transient",
            )
        )
        plan = build_convergence_study_plan(spec)
        data = plan.to_dict()

        self.assertEqual(plan.automation_status, "interface_only")
        self.assertGreaterEqual(len([point for point in plan.points if point.kind == "mesh"]), 3)
        self.assertGreaterEqual(len([point for point in plan.points if point.kind == "time_step"]), 3)
        self.assertEqual(data["runner_interface"]["input_contract"], "thermal-convergence-study-plan/v1")

    def test_golden_case_registry_has_comparator_metadata(self) -> None:
        registry = build_golden_case_registry(self.tmp / "missing-comsol-root")
        by_id = {item["case_id"]: item for item in registry}

        self.assertIn("busbar_smoke", by_id)
        self.assertIn("chip_cooling_reference", by_id)
        self.assertEqual(by_id["busbar_smoke"]["golden_role"], "installation_and_solver_smoke")
        self.assertEqual(by_id["busbar_smoke"]["comparator"]["type"], "artifact_and_log")
        self.assertIn("credibility_card", by_id["busbar_smoke"]["required_artifacts"])
        self.assertEqual(by_id["chip_cooling_reference"]["comparator"]["type"], "published_reference_values")

    def test_credibility_card_upgrades_publication_requests(self) -> None:
        task = ThermalSimulationTask(
            goal="Prepare publication paper evidence for the chip thermal result.",
            backend=SimulationBackend.MOCK,
            parameters={
                "chip_power_W": 1.0,
                "ambient_temp_C": 25.0,
                "h_conv_W_m2K": 50.0,
                "cooling_area_m2": 0.02,
                "base_resistance_K_W": 2.0,
            },
        )

        result = run_thermal_simulation(task, self.tmp)
        card = json.loads((self.tmp / "credibility_card.json").read_text(encoding="utf-8"))
        required_ids = {item["id"]: item for item in card["required_evidence"]}

        self.assertTrue(result.passed)
        self.assertEqual(infer_thermal_evidence_level(task.goal), PUBLICATION_EVIDENCE_LEVEL)
        self.assertEqual(card["evidence_level"], PUBLICATION_EVIDENCE_LEVEL)
        self.assertEqual(card["credibility_status"], "insufficient_for_publication_or_external_claim")
        self.assertTrue(required_ids["official_golden_case_or_benchmark"]["required"])
        self.assertFalse(required_ids["official_golden_case_or_benchmark"]["satisfied"])
        self.assertTrue((self.tmp / "boundary_condition_audit.json").exists())
        self.assertTrue((self.tmp / "energy_balance_check.json").exists())
        self.assertTrue((self.tmp / "convergence_study_plan.json").exists())


if __name__ == "__main__":
    unittest.main()
