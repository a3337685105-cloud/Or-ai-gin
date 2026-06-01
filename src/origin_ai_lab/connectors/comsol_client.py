from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from origin_ai_lab.connectors.software_discovery import discover_comsol
from origin_ai_lab.models import ThermalSimulationSpec


class ComsolUnavailable(RuntimeError):
    """Raised when COMSOL execution is requested but no local bridge is configured."""


class ComsolThermalClient:
    """Boundary for future COMSOL thermal template execution.

    This first implementation uses COMSOL's documented batch boundary. It runs
    validated MPH templates and records artifacts, but does not yet mutate model
    internals. Parameterized model editing should be added through reviewed
    template methods or a Java/MATLAB bridge.
    """

    def __init__(self, executable_path: Path | None = None) -> None:
        self.executable_path = executable_path

    def run_thermal_study(self, spec: ThermalSimulationSpec, output_dir: Path) -> dict[str, Any]:
        if spec.template_path is None:
            raise ComsolUnavailable("COMSOL backend requires an existing .mph template path.")
        template_path = spec.template_path.resolve()
        if not template_path.exists():
            raise ComsolUnavailable(f"COMSOL template does not exist: {template_path}")

        executable_path = self.executable_path or _default_comsolbatch_path()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_mph = output_dir / f"{template_path.stem}_solved.mph"
        batch_log = output_dir / f"{template_path.stem}_comsolbatch.log"
        status_file = output_dir / f"{template_path.stem}_solved.mph.status"

        command = [
            str(executable_path),
            "-inputfile",
            str(template_path),
            "-outputfile",
            str(output_mph),
            "-batchlog",
            str(batch_log),
        ]
        if spec.study_type and spec.study_type.lower().startswith("std"):
            command.extend(["-study", spec.study_type])

        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        log_text = _read_text_lossy(batch_log)
        if completed.returncode != 0:
            raise ComsolUnavailable(
                "COMSOL batch execution failed with exit code "
                f"{completed.returncode}. See {batch_log}."
            )
        if not output_mph.exists():
            raise ComsolUnavailable(f"COMSOL batch completed but did not create {output_mph}.")

        return {
            "solver": "comsolbatch",
            "solver_converged": _log_indicates_success(log_text),
            "return_code": completed.returncode,
            "command": command,
            "output_mph": str(output_mph),
            "batch_log": str(batch_log),
            "status_file": str(status_file) if status_file.exists() else None,
            "log_summary": _summarize_log(log_text),
            "parameter_updates_applied": False,
            "parameter_update_note": (
                "This smoke-test connector solves an existing MPH template. "
                "Parameter mutation will be enabled through reviewed COMSOL template methods."
            ),
        }


def _default_comsolbatch_path() -> Path:
    install = discover_comsol()
    if not install.found or install.executable_path is None:
        raise ComsolUnavailable("COMSOL batch executable was not found. Run `origin-ai doctor` for details.")
    executable_path = install.executable_path
    if executable_path.name.lower() == "comsol.exe":
        sibling_batch = executable_path.with_name("comsolbatch.exe")
        if sibling_batch.exists():
            return sibling_batch
    return executable_path


def _read_text_lossy(path: Path) -> str:
    if not path.exists():
        return ""
    for encoding in ("utf-8", "gb18030", "utf-16"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeError:
            continue
    return path.read_bytes().decode("utf-8", errors="replace")


def _log_indicates_success(log_text: str) -> bool:
    normalized = log_text.lower()
    return (
        "completed" in normalized
        or "100 %" in normalized
        or "100%" in normalized
        or "完成" in log_text
    ) and "error" not in normalized


def _summarize_log(log_text: str) -> dict[str, Any]:
    lines = [line.strip() for line in log_text.splitlines() if line.strip()]
    tail = lines[-12:]
    return {
        "line_count": len(lines),
        "tail": tail,
    }
