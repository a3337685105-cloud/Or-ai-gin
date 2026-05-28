from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class OriginUnavailable(RuntimeError):
    """Raised when Origin/OriginPro or originpro cannot be used."""


@dataclass
class OriginArtifacts:
    project_path: Path
    figure_path: Path
    figure_paths: dict[str, Path] = field(default_factory=dict)
    render_metadata: dict[str, Any] = field(default_factory=dict)


class OriginClient:
    """Thin boundary around OriginLab's originpro package.

    Import originpro lazily so tests and non-Origin workflows can run on any machine.
    """

    def __init__(self, visible: bool = True) -> None:
        self.visible = visible
        self._op: Any | None = None

    def __enter__(self) -> "OriginClient":
        try:
            import originpro as op  # type: ignore[import-not-found]
        except ImportError as exc:
            raise OriginUnavailable(
                "originpro is not installed. Use the dedicated Origin Python environment "
                "or install the optional origin dependency on Windows."
            ) from exc

        self._op = op
        if getattr(op, "oext", False):
            op.set_show(self.visible)
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._op is not None and getattr(self._op, "oext", False):
            self._op.exit()

    @property
    def op(self) -> Any:
        if self._op is None:
            raise OriginUnavailable("OriginClient must be used as a context manager.")
        return self._op

    def create_scatter_project(
        self,
        csv_path: Path,
        output_dir: Path,
        x_column: str,
        y_column: str,
        plot_kind: str = "scatter",
        project_name: str = "origin_ai_analysis",
        import_csv_path: Path | None = None,
        title: str | None = None,
        x_title: str | None = None,
        y_title: str | None = None,
        x_limits: tuple[float | None, float | None] | None = None,
        y_limits: tuple[float | None, float | None] | None = None,
        fit_line: dict[str, float] | None = None,
        style: dict[str, Any] | None = None,
        peak_markers: tuple[dict[str, float], ...] = (),
        output_formats: tuple[str, ...] = ("png",),
    ) -> OriginArtifacts:
        output_dir.mkdir(parents=True, exist_ok=True)
        project_path = output_dir / f"{project_name}.opju"
        export_formats = _resolve_export_formats(output_formats)
        figure_paths = {fmt: output_dir / f"{project_name}.{fmt}" for fmt in export_formats}
        figure_path = figure_paths.get("png") or next(iter(figure_paths.values()))

        op = self.op
        op.new()
        worksheet = op.new_sheet("w")
        worksheet.from_file(str(import_csv_path or csv_path), False)

        template = "line" if plot_kind == "line" else "scatter"
        graph = op.new_graph(template=template)
        layer = graph[0]
        try:
            data_plot = layer.add_plot(worksheet, coly=y_column, colx=x_column)
        except Exception:
            # Some Origin templates prefer column letters or indexes. The MVP sample
            # uses the first two columns as a conservative fallback.
            data_plot = layer.add_plot(worksheet, coly=1, colx=0)
        layer.rescale()
        op.wait()

        applied_series_style = _apply_series_style(data_plot, style or {}, plot_kind)
        rendered_x_limits = _set_axis_limits(layer, "x", x_limits or _limits_from_style(style or {}, "x"))
        rendered_y_limits = _set_axis_limits(layer, "y", y_limits or _limits_from_style(style or {}, "y"))
        expected_x_title = x_title or x_column
        expected_y_title = y_title or y_column
        rendered_x_title = _set_axis_title(layer, "x", expected_x_title)
        rendered_y_title = _set_axis_title(layer, "y", expected_y_title)
        if title:
            _set_page_long_name(graph, title)

        fit_line_rendered = _add_fit_line(layer, fit_line, style or {})
        peak_markers_rendered = _add_peak_markers(layer, peak_markers, style or {})
        legend_text = _apply_legend_policy(layer, style or {})
        op.wait()

        exported_figures = _export_figures(graph, figure_paths, width=_export_width(style or {}))
        op.save(str(project_path))
        return OriginArtifacts(
            project_path=project_path,
            figure_path=figure_path,
            figure_paths=exported_figures,
            render_metadata={
                "project_path": str(project_path),
                "figure_path": str(figure_path),
                "figure_paths": {fmt: str(path) for fmt, path in exported_figures.items()},
                "requested_formats": list(output_formats),
                "exported_formats": list(exported_figures.keys()),
                "plot_kind": plot_kind,
                "title": title,
                "x_axis_title": rendered_x_title,
                "y_axis_title": rendered_y_title,
                "x_axis_limits": list(rendered_x_limits) if rendered_x_limits else None,
                "y_axis_limits": list(rendered_y_limits) if rendered_y_limits else None,
                "series_style": applied_series_style,
                "legend_text": legend_text,
                "legend_visible": bool(legend_text.strip()),
                "fit_line_rendered": fit_line_rendered,
                "peak_markers_rendered": peak_markers_rendered,
            },
        )


def _set_axis_title(layer: Any, axis: str, title: str) -> str:
    axis_object = layer.axis(axis)
    axis_object.title = title
    label_name = "xb" if axis == "x" else "yl"
    label = layer.label(label_name)
    if label is not None:
        label.text = title
    return str(axis_object.title or _read_label_text(layer, label_name) or "")


def _set_page_long_name(graph: Any, title: str) -> None:
    try:
        graph.set_str("longname", title)
    except Exception:
        return


def _apply_series_style(data_plot: Any, style: dict[str, Any], plot_kind: str) -> dict[str, Any]:
    if data_plot is None:
        return {}
    series_style = _series_style(style)
    applied: dict[str, Any] = {}
    color = series_style.get("color") or style.get("color")
    if color:
        try:
            data_plot.color = str(color)
            applied["color"] = str(color)
        except Exception:
            pass

    line_width = _number_from(series_style.get("line_width") or series_style.get("width"))
    if line_width is None and style.get("weight") == "bold":
        line_width = 3.0
    if line_width is not None:
        if _set_plot_num(data_plot, "line.width", line_width):
            applied["line_width"] = line_width

    marker_size = _number_from(series_style.get("marker_size") or series_style.get("symbol_size"))
    if marker_size is not None and _set_plot_num(data_plot, "symbol.size", marker_size):
        applied["marker_size"] = marker_size

    marker = str(series_style.get("marker") or series_style.get("symbol") or "").strip().lower()
    if marker:
        symbol_kind = _marker_kind(marker)
        if symbol_kind is not None and _set_plot_num(data_plot, "symbol.kind", symbol_kind):
            applied["marker"] = marker

    if plot_kind == "line" and line_width is None:
        _set_plot_num(data_plot, "line.width", 1.5)
    return applied


def _add_fit_line(layer: Any, fit_line: dict[str, float] | None, style: dict[str, Any]) -> bool:
    if not fit_line:
        return False
    try:
        line = layer.add_line(fit_line["x1"], fit_line["y1"], fit_line["x2"], fit_line["y2"])
    except Exception:
        return False
    if line is None:
        return False
    fit_style = style.get("fit_line") if isinstance(style.get("fit_line"), dict) else {}
    line.width = _number_from(fit_style.get("line_width") or fit_style.get("width")) or 2
    line.color = str(fit_style.get("color") or "Red")
    return True


def _add_peak_markers(layer: Any, peak_markers: tuple[dict[str, float], ...], style: dict[str, Any]) -> int:
    peak_style = style.get("peak_markers") if isinstance(style.get("peak_markers"), dict) else {}
    color = str(peak_style.get("color") or "Red")
    width = _number_from(peak_style.get("line_width") or peak_style.get("width")) or 1.0
    show_labels = _bool_from(peak_style.get("show_labels"), default=False)
    rendered = 0
    for marker in peak_markers:
        try:
            line = layer.add_line(marker["x"], marker["baseline_y"], marker["x"], marker["y"])
        except Exception:
            continue
        if line is None:
            continue
        line.width = width
        line.color = color
        if show_labels:
            _add_peak_label(layer, marker, peak_style)
        rendered += 1
    return rendered


def _add_peak_label(layer: Any, marker: dict[str, float], peak_style: dict[str, Any]) -> None:
    try:
        label = layer.add_label(f"{marker['x']:.2g}", marker["x"], marker["y"])
    except Exception:
        return
    if label is None:
        return
    try:
        label.set_int("attach", 2)
        label.set_float("x1", marker["x"])
        label.set_float("y1", marker["y"])
        label.color = str(peak_style.get("label_color") or peak_style.get("color") or "Red")
    except Exception:
        return


def _apply_legend_policy(layer: Any, style: dict[str, Any]) -> str:
    legend_style = style.get("legend") if isinstance(style.get("legend"), dict) else {}
    show = legend_style.get("show")
    label = layer.label("legend")
    if show is False:
        if label is not None:
            try:
                label.remove()
            except Exception:
                pass
        return ""
    return _read_label_text(layer, "legend")


def _read_label_text(layer: Any, name: str) -> str:
    label = layer.label(name)
    if label is None:
        return ""
    try:
        return str(label.text or "")
    except Exception:
        return ""


def _set_axis_limits(layer: Any, axis: str, limits: tuple[float | None, float | None] | None) -> tuple[float, float] | None:
    if limits is None:
        return _read_axis_limits(layer, axis)
    begin, end = limits
    try:
        if axis == "x":
            layer.set_xlim(begin=begin, end=end)
        else:
            layer.set_ylim(begin=begin, end=end)
    except Exception:
        return _read_axis_limits(layer, axis)
    return _read_axis_limits(layer, axis)


def _read_axis_limits(layer: Any, axis: str) -> tuple[float, float] | None:
    try:
        limits = layer.xlim if axis == "x" else layer.ylim
        if isinstance(limits, (list, tuple)) and len(limits) >= 2:
            return (float(limits[0]), float(limits[1]))
    except Exception:
        return None
    return None


def _limits_from_style(style: dict[str, Any], axis: str) -> tuple[float | None, float | None] | None:
    key = "x_limits" if axis == "x" else "y_limits"
    value = style.get(key)
    if value is None:
        axes = style.get("axes") if isinstance(style.get("axes"), dict) else {}
        axis_style = axes.get(axis) if isinstance(axes.get(axis), dict) else {}
        value = axis_style.get("limits")
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    begin = None if value[0] is None or value[0] == "" else float(value[0])
    end = None if value[1] is None or value[1] == "" else float(value[1])
    return (begin, end)


def _series_style(style: dict[str, Any]) -> dict[str, Any]:
    nested = style.get("series")
    if isinstance(nested, dict):
        return nested
    return {}


def _set_plot_num(data_plot: Any, prop: str, value: float) -> bool:
    try:
        data_plot.layer.SetNumProp(data_plot._format_property(prop), value)
    except Exception:
        return False
    return True


def _marker_kind(marker: str) -> int | None:
    markers = {
        "circle": 2,
        "round": 2,
        "square": 1,
        "box": 1,
        "triangle": 5,
        "diamond": 3,
    }
    return markers.get(marker)


def _number_from(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def _bool_from(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _resolve_export_formats(output_formats: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for item in output_formats or ("png",):
        fmt = str(item).strip().lower().lstrip(".")
        if fmt == "opju":
            continue
        if fmt in {"png", "svg", "pdf"} and fmt not in normalized:
            normalized.append(fmt)
    if "png" not in normalized:
        normalized.insert(0, "png")
    return tuple(normalized)


def _export_width(style: dict[str, Any]) -> int:
    export_style = style.get("export") if isinstance(style.get("export"), dict) else {}
    width = _number_from(export_style.get("width_px") or style.get("width_px"))
    if width is None:
        return 1400
    return max(int(width), 400)


def _export_figures(graph: Any, figure_paths: dict[str, Path], width: int) -> dict[str, Path]:
    exported: dict[str, Path] = {}
    for fmt, path in figure_paths.items():
        saved = graph.save_fig(str(path), width=width)
        if saved:
            exported[fmt] = Path(saved)
        elif path.exists():
            exported[fmt] = path
    return exported
