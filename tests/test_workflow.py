from __future__ import annotations

import shutil
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from origin_ai_lab.connectors.csv_table import profile_csv
from origin_ai_lab.agents.data_router import route_dataset_rule
from origin_ai_lab.agents.requirement_intake import infer_requirement
from origin_ai_lab.models import AnalysisTask, PlotEditOperation, PlotEditPlan, PlotKind, PlotSpec, TaskType
from origin_ai_lab.evaluation.plot_accuracy import detect_peak_candidates, evaluate_plot_accuracy
from origin_ai_lab.evaluation.visual_quality import evaluate_image_quality
from origin_ai_lab.origin_analysis_adapters import planned_origin_adapters
from origin_ai_lab.origin_templates import select_origin_template
from origin_ai_lab.plotting.spec_editor import PlotSpecValidationError, apply_edit_plan
from origin_ai_lab.secrets_store import get_secret, save_secret, secret_exists
from origin_ai_lab.web_server import OriginAIWebHandler
from origin_ai_lab.workflows.analyze_and_plot import run_analysis
from origin_ai_lab.workflows.modify_plot import create_initial_plot_revision, modify_plot_revision


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="origin-ai-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp)

    def test_profile_detects_numeric_columns(self) -> None:
        profile = profile_csv(ROOT / "examples" / "sample_xy.csv")
        self.assertEqual(profile.row_count, 6)
        self.assertEqual(profile.numeric_columns(), ["time_s", "signal_v"])

    def test_profile_detects_instrument_export_tables(self) -> None:
        xrd = profile_csv(ROOT / "examples" / "materials_xrd_export.csv")
        raman = profile_csv(ROOT / "examples" / "materials_raman_export.txt")
        tga = profile_csv(ROOT / "examples" / "materials_tga_export.csv")
        dsc = profile_csv(ROOT / "examples" / "materials_dsc_export.tsv")

        self.assertEqual(xrd.row_count, 24)
        self.assertEqual(xrd.numeric_columns(), ["two_theta_deg", "intensity_counts"])
        self.assertEqual(raman.numeric_columns(), ["Raman_shift_cm-1", "Intensity_a.u."])
        self.assertEqual(tga.numeric_columns(), ["temperature_C", "mass_percent", "derivative_percent_per_C"])
        self.assertEqual(dsc.numeric_columns(), ["temperature_C", "heat_flow_mW"])

    def test_profile_detects_xlsx_export_with_metadata_and_units(self) -> None:
        xlsx_path = self.tmp / "instrument_export.xlsx"
        _write_minimal_xlsx(
            xlsx_path,
            {
                "Meta": [["Instrument", "Synthetic"]],
                "Data": [
                    ["Operator", "demo"],
                    [],
                    ["time_s", "signal_v"],
                    ["s", "V"],
                    [0, 1.1],
                    [1, 1.7],
                    [2, 2.4],
                ],
            },
        )

        profile = profile_csv(xlsx_path)

        self.assertEqual(profile.row_count, 3)
        self.assertEqual(profile.numeric_columns(), ["time_s", "signal_v"])

    def test_material_requirement_intake_infers_spectrum_plot(self) -> None:
        profile = profile_csv(ROOT / "examples" / "materials_xrd_export.csv")
        intent = infer_requirement("生成 XRD 图谱，横轴 two_theta_deg，纵轴 intensity_counts，导出 png", profile)
        self.assertTrue(intent.ready_to_execute)
        self.assertEqual(intent.plot_kind, PlotKind.LINE)
        self.assertEqual(intent.x_column, "two_theta_deg")
        self.assertEqual(intent.y_column, "intensity_counts")

    def test_rule_route_infers_material_plot_path(self) -> None:
        profile = profile_csv(ROOT / "examples" / "materials_eis_export.csv")
        route = route_dataset_rule("画 Nyquist 图", profile)

        self.assertTrue(route.ready_to_execute)
        self.assertEqual(route.instrument_family, "eis")
        self.assertEqual(route.plot_kind, PlotKind.SCATTER)
        self.assertEqual(route.x_column, "z_real_ohm")
        self.assertEqual(route.y_column, "z_imag_neg_ohm")

    def test_run_analysis_without_origin(self) -> None:
        task = AnalysisTask(
            dataset_path=ROOT / "examples" / "sample_xy.csv",
            goal="test",
            task_type=TaskType.PLOT_XY,
            use_origin=False,
        )
        result = run_analysis(task, self.tmp)
        self.assertTrue(result.passed)
        self.assertIsNotNone(result.regression)
        self.assertTrue((self.tmp / "result.json").exists())
        self.assertTrue((self.tmp / "plot_spec.json").exists())
        self.assertTrue((self.tmp / "normalized_data.csv").exists())

    def test_run_analysis_material_export_writes_origin_ready_csv(self) -> None:
        task = AnalysisTask(
            dataset_path=ROOT / "examples" / "materials_xrd_export.csv",
            goal="生成 XRD 图谱",
            task_type=TaskType.PLOT_XY,
            plot_kind=PlotKind.AUTO,
            use_origin=False,
        )
        result = run_analysis(task, self.tmp)
        normalized = self.tmp / "normalized_data.csv"
        first_lines = normalized.read_text(encoding="utf-8").splitlines()[:3]

        self.assertTrue(result.passed)
        self.assertEqual(result.plot_spec.plot_kind, PlotKind.LINE)
        self.assertEqual(result.plot_spec.x_column, "two_theta_deg")
        self.assertEqual(result.plot_spec.y_column, "intensity_counts")
        self.assertEqual(result.plot_spec.title, "XRD Pattern")
        self.assertEqual(result.plot_spec.x_title, "2Theta (deg)")
        self.assertEqual(result.plot_spec.y_title, "Intensity (counts)")
        self.assertFalse(result.plot_spec.fit_enabled)
        self.assertEqual(result.plot_spec.style["theme"], "origin-ai-clean-v1")
        self.assertEqual(result.plot_spec.style["series"]["color"], "Black")
        self.assertGreaterEqual(result.plot_spec.style["series"]["line_width"], 2.0)
        self.assertFalse(result.plot_spec.style["legend"]["show"])
        self.assertIsNone(result.regression)
        self.assertEqual(first_lines[0], "two_theta_deg,intensity_counts")
        self.assertEqual(first_lines[1], "20.0,118")
        self.assertNotIn("#", "\n".join(first_lines))
        self.assertTrue((self.tmp / "route_decision.json").exists())
        self.assertTrue((self.tmp / "origin_template.json").exists())
        self.assertTrue((self.tmp / "origin_analysis_adapters.json").exists())
        self.assertTrue((self.tmp / "peak_summary.json").exists())

    def test_origin_template_keeps_xrd_inside_origin_plotting_scope(self) -> None:
        profile = profile_csv(ROOT / "examples" / "materials_xrd_export.csv")
        route = route_dataset_rule("生成 XRD 图谱", profile)
        template = select_origin_template(route, profile, PlotKind.AUTO)

        self.assertEqual(template.template_id, "xrd_pattern")
        self.assertEqual(template.plot_kind, PlotKind.LINE)
        self.assertFalse(template.default_fit_enabled)
        self.assertIn("PDF database search/match", template.non_goals)

    def test_origin_adapters_record_peak_markers_not_database_matching(self) -> None:
        profile = profile_csv(ROOT / "examples" / "materials_xrd_export.csv")
        route = route_dataset_rule("生成 XRD 图谱", profile)
        spec = PlotSpec(
            dataset_path=ROOT / "examples" / "materials_xrd_export.csv",
            plot_kind=PlotKind.LINE,
            x_column="two_theta_deg",
            y_column="intensity_counts",
            fit_enabled=False,
        )
        peaks = detect_peak_candidates(spec.dataset_path, spec.x_column, spec.y_column)
        adapters = planned_origin_adapters(spec, route, peaks)
        by_id = {adapter.adapter_id: adapter for adapter in adapters}

        self.assertIn("origin_graph_export", by_id)
        self.assertIn("spectrum_peak_markers", by_id)
        self.assertNotIn("phase_identification", by_id)
        self.assertIn("phase identification", by_id["spectrum_peak_markers"].non_goals)

    def test_web_analyze_overrides_parse_editable_slots(self) -> None:
        payload = {
            "overrides": {
                "plot_kind": "line",
                "x_column": "time_s",
                "y_column": "signal_v",
                "group_column": "__none__",
                "title": "Manual title",
                "x_title": "Time / s",
                "y_title": "Signal / V",
                "fit_enabled": False,
                "output_formats": "svg, pdf",
            }
        }
        overrides = OriginAIWebHandler._analysis_overrides(None, payload)

        self.assertEqual(overrides["plot_kind"], "line")
        self.assertEqual(overrides["x_column"], "time_s")
        self.assertEqual(overrides["group_column"], None)
        self.assertEqual(overrides["title"], "Manual title")
        self.assertEqual(overrides["x_title"], "Time / s")
        self.assertEqual(overrides["y_title"], "Signal / V")
        self.assertFalse(overrides["fit_enabled"])
        self.assertEqual(overrides["output_formats"], ("svg", "pdf"))

    def test_web_feedback_record_requires_actionable_text(self) -> None:
        record = OriginAIWebHandler._feedback_record(
            None,
            {
                "run_id": "test-run",
                "revision": 2,
                "request": "draw plot",
                "feedback": "axis title is wrong",
                "correction": "use Time / s",
                "plot_spec": {"x_title": "time_s"},
            },
        )

        self.assertEqual(record["schema_version"], "feedback-sample/v1")
        self.assertEqual(record["run_id"], "test-run")
        self.assertEqual(record["revision"], 2)
        self.assertEqual(record["feedback"], "axis title is wrong")
        self.assertEqual(record["correction"], "use Time / s")

        with self.assertRaises(ValueError):
            OriginAIWebHandler._feedback_record(None, {"run_id": "test-run"})

    def test_run_analysis_uses_user_confirmed_titles_and_fit_override(self) -> None:
        task = AnalysisTask(
            dataset_path=ROOT / "examples" / "sample_xy.csv",
            goal="confirmed slots",
            task_type=TaskType.PLOT_XY,
            x_column="time_s",
            y_column="signal_v",
            plot_kind=PlotKind.LINE,
            style={
                "title": "Manual title",
                "x_title": "Time / s",
                "y_title": "Signal / V",
            },
            output_formats=("svg",),
            fit_enabled=False,
            use_origin=False,
        )
        result = run_analysis(task, self.tmp)

        self.assertTrue(result.passed)
        self.assertEqual(result.plot_spec.plot_kind, PlotKind.LINE)
        self.assertEqual(result.plot_spec.title, "Manual title")
        self.assertEqual(result.plot_spec.x_title, "Time / s")
        self.assertEqual(result.plot_spec.y_title, "Signal / V")
        self.assertFalse(result.plot_spec.fit_enabled)
        self.assertIsNone(result.regression)

    def test_visual_quality_rejects_blank_image(self) -> None:
        Image = _load_pillow_image()
        image_path = self.tmp / "blank.png"
        Image.new("RGB", (900, 600), "white").save(image_path)

        checks, report = evaluate_image_quality(image_path)
        by_name = {check.name: check for check in checks}

        self.assertFalse(by_name["visual_nonblank"].passed)
        self.assertFalse(by_name["visual_content_visible"].passed)
        self.assertFalse(report["passed"])

    def test_visual_quality_accepts_plot_like_image(self) -> None:
        Image = _load_pillow_image()
        from PIL import ImageDraw

        image_path = self.tmp / "plot.png"
        image = Image.new("RGB", (1000, 700), "white")
        draw = ImageDraw.Draw(image)
        draw.line((100, 600, 900, 600), fill="black", width=3)
        draw.line((100, 600, 100, 100), fill="black", width=3)
        draw.line((120, 560, 250, 500, 400, 390, 650, 250, 880, 180), fill="red", width=5)
        image.save(image_path)

        checks, report = evaluate_image_quality(image_path)
        by_name = {check.name: check for check in checks}

        self.assertTrue(by_name["visual_nonblank"].passed)
        self.assertTrue(by_name["visual_content_visible"].passed)
        self.assertTrue(report["passed"])

    def test_plot_accuracy_detects_axes_fit_and_material_peaks(self) -> None:
        profile = profile_csv(ROOT / "examples" / "materials_xrd_export.csv")
        route = route_dataset_rule("XRD pattern", profile)
        spec = PlotSpec(
            dataset_path=ROOT / "examples" / "materials_xrd_export.csv",
            plot_kind=PlotKind.LINE,
            x_column="two_theta_deg",
            y_column="intensity_counts",
            title="XRD pattern",
            x_title="two_theta_deg",
            y_title="intensity_counts",
            fit_enabled=False,
        )
        peaks = detect_peak_candidates(spec.dataset_path, spec.x_column, spec.y_column)
        checks, report = evaluate_plot_accuracy(spec, profile, route_decision=route, peak_candidates=peaks)
        by_name = {check.name: check for check in checks}

        self.assertTrue(by_name["plot_axis_titles_declared"].passed)
        self.assertTrue(by_name["plot_label_text_safe"].passed)
        self.assertTrue(by_name["plot_fit_expectation"].passed)
        self.assertTrue(by_name["plot_peak_candidates_detected"].passed)
        self.assertGreaterEqual(len(peaks), 3)
        self.assertAlmostEqual(peaks[0]["x"], 25.3, places=1)
        self.assertTrue(report["passed"])

    def test_plot_accuracy_rejects_bad_rendered_axis_title(self) -> None:
        profile = profile_csv(ROOT / "examples" / "materials_xrd_export.csv")
        route = route_dataset_rule("XRD pattern", profile)
        spec = PlotSpec(
            dataset_path=ROOT / "examples" / "materials_xrd_export.csv",
            plot_kind=PlotKind.LINE,
            x_column="two_theta_deg",
            y_column="intensity_counts",
            x_title="two_theta_deg",
            y_title="intensity_counts",
            fit_enabled=False,
        )
        peaks = detect_peak_candidates(spec.dataset_path, spec.x_column, spec.y_column)
        checks, report = evaluate_plot_accuracy(
            spec,
            profile,
            route_decision=route,
            peak_candidates=peaks,
            render_metadata={
                "x_axis_title": "wrong_label",
                "y_axis_title": "intensity_counts",
                "fit_line_rendered": False,
                "peak_markers_rendered": len(peaks),
            },
        )
        by_name = {check.name: check for check in checks}

        self.assertFalse(by_name["origin_axis_titles_match"].passed)
        self.assertFalse(report["passed"])

    def test_requirement_intake_turns_request_into_slots(self) -> None:
        profile = profile_csv(ROOT / "examples" / "sample_xy.csv")
        intent = infer_requirement("帮我画散点图，加线性拟合，导出 png", profile)
        self.assertTrue(intent.ready_to_execute)
        self.assertEqual(intent.x_column, "time_s")
        self.assertEqual(intent.y_column, "signal_v")
        self.assertIn("png", intent.output_formats)
        self.assertNotEqual(intent.style.get("mark"), "line")

    def test_plot_spec_edit_plan_updates_style_fit_and_export(self) -> None:
        profile = profile_csv(ROOT / "examples" / "sample_xy.csv")
        spec = PlotSpec(
            dataset_path=ROOT / "examples" / "sample_xy.csv",
            plot_kind=PlotKind.SCATTER,
            x_column="time_s",
            y_column="signal_v",
        )
        plan = PlotEditPlan(
            user_request="改红色，去掉拟合，导出 svg",
            operations=(
                PlotEditOperation("set_series_style", properties={"color": "red"}),
                PlotEditOperation("set_fit", properties={"enabled": False}),
                PlotEditOperation("set_export_formats", properties={"formats": ["svg"]}),
            ),
        )
        updated = apply_edit_plan(spec, plan, profile)
        self.assertEqual(updated.style["series"]["color"], "red")
        self.assertFalse(updated.fit_enabled)
        self.assertEqual(updated.output_formats, ("svg",))

    def test_plot_spec_rejects_missing_column(self) -> None:
        profile = profile_csv(ROOT / "examples" / "sample_xy.csv")
        spec = PlotSpec(
            dataset_path=ROOT / "examples" / "sample_xy.csv",
            plot_kind=PlotKind.SCATTER,
            x_column="time_s",
            y_column="signal_v",
        )
        plan = PlotEditPlan(
            user_request="换列",
            operations=(PlotEditOperation("set_columns", properties={"x_column": "missing"}),),
        )
        with self.assertRaises(PlotSpecValidationError):
            apply_edit_plan(spec, plan, profile)

    def test_modify_workflow_creates_revision_chain(self) -> None:
        task = AnalysisTask(
            dataset_path=ROOT / "examples" / "sample_xy.csv",
            goal="帮我画散点图，加线性拟合，导出 png",
            task_type=TaskType.PLOT_XY,
            use_origin=False,
        )
        runs_root = self.tmp / "runs"
        previous = os.environ.get("ORIGIN_AI_EDIT_PLANNER")
        os.environ["ORIGIN_AI_EDIT_PLANNER"] = "rule"
        try:
            initial = create_initial_plot_revision(task, runs_root, run_id="test-run")
            first = modify_plot_revision("test-run", "把点改成红色", runs_root)
            second = modify_plot_revision("test-run", "去掉拟合，导出 svg", runs_root)
        finally:
            if previous is None:
                os.environ.pop("ORIGIN_AI_EDIT_PLANNER", None)
            else:
                os.environ["ORIGIN_AI_EDIT_PLANNER"] = previous
        self.assertEqual(initial["revision"], 0)
        self.assertEqual(first["revision"], 1)
        self.assertEqual(second["revision"], 2)
        self.assertTrue((runs_root / "test-run" / "revisions" / "0000" / "plot_spec.json").exists())
        self.assertTrue((runs_root / "test-run" / "revisions" / "0001" / "result.json").exists())
        self.assertTrue((runs_root / "test-run" / "revisions" / "0002" / "plot_spec.json").exists())
        self.assertFalse(second["plot_spec"].fit_enabled)
        self.assertEqual(second["plot_spec"].output_formats, ("svg",))

    @unittest.skipUnless(sys.platform == "win32", "Windows DPAPI is required for secret storage.")
    def test_secret_store_round_trip(self) -> None:
        previous = os.environ.get("ORIGIN_AI_CONFIG_DIR")
        os.environ["ORIGIN_AI_CONFIG_DIR"] = str(self.tmp / "config")
        try:
            save_secret("test_secret", "sk-test-value")
            self.assertTrue(secret_exists("test_secret"))
            self.assertEqual(get_secret("test_secret"), "sk-test-value")
        finally:
            if previous is None:
                os.environ.pop("ORIGIN_AI_CONFIG_DIR", None)
            else:
                os.environ["ORIGIN_AI_CONFIG_DIR"] = previous


def _load_pillow_image():
    try:
        from PIL import Image
    except ImportError as exc:
        raise unittest.SkipTest("Pillow is required for visual quality tests.") from exc
    return Image


def _write_minimal_xlsx(path: Path, sheets: dict[str, list[list[object]]]) -> None:
    sheet_names = list(sheets)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
""" + "".join(
                f'  <Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>\n'
                for index, _ in enumerate(sheet_names, start=1)
            ) + "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
""" + "".join(
                f'    <sheet name="{_xml_escape(name)}" sheetId="{index}" r:id="rId{index}"/>\n'
                for index, name in enumerate(sheet_names, start=1)
            ) + "  </sheets>\n</workbook>",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
""" + "".join(
                f'  <Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>\n'
                for index, _ in enumerate(sheet_names, start=1)
            ) + "</Relationships>",
        )
        for index, name in enumerate(sheet_names, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(sheets[name]))


def _sheet_xml(rows: list[list[object]]) -> str:
    xml_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            if value is None:
                continue
            ref = f"{_column_name(column_index)}{row_index}"
            if isinstance(value, (int, float)):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{_xml_escape(str(value))}</t></is></c>')
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(xml_rows)}</sheetData></worksheet>'
    )


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(ord("A") + remainder) + name
    return name


def _xml_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


if __name__ == "__main__":
    unittest.main()
