from __future__ import annotations

import json
import mimetypes
import argparse
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from origin_ai_lab.agents.planner_adapter import active_planner_name, infer_requirement_auto
from origin_ai_lab.agents.research_intake_harness import build_research_work_order, intake_question_bank
from origin_ai_lab.agents.qwen_planner import (
    DEFAULT_QWEN_BASE_URL,
    DEFAULT_QWEN_MODEL,
    SECRET_DASHSCOPE_API_KEY,
    SECRET_QWEN_BASE_URL,
    SECRET_QWEN_ENABLE_THINKING,
    SECRET_QWEN_MODEL,
    qwen_status,
)
from origin_ai_lab.connectors.csv_table import profile_csv
from origin_ai_lab.models import AnalysisTask, PlotKind, TaskType
from origin_ai_lab.secrets_store import SecretStoreError, delete_secret, save_secret
from origin_ai_lab.workflows.modify_plot import (
    create_initial_plot_revision,
    load_plot_revision,
    modify_plot_revision,
)

ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = ROOT / "web"
DEFAULT_DATASET = ROOT / "examples" / "sample_xy.csv"
RUNS_ROOT = ROOT / "runs"


class OriginAIWebHandler(BaseHTTPRequestHandler):
    server_version = "OriginAIWeb/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            status = qwen_status()
            self._send_json(
                {
                    "ai_mode": active_planner_name(),
                    "qwen": status,
                    "origin_mode": "optional; enable it to let the backend call originpro",
                    "sample_dataset": str(DEFAULT_DATASET.relative_to(ROOT)),
                }
            )
            return
        if parsed.path == "/api/secrets/qwen":
            self._send_json(qwen_status())
            return
        if parsed.path == "/api/revision":
            self._handle_get_revision(parsed.query)
            return
        if parsed.path == "/file":
            self._serve_file_query(parsed.query)
            return
        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
            if parsed.path == "/api/research-intake":
                self._handle_research_intake(payload)
                return
            if parsed.path == "/api/intake":
                self._handle_intake(payload)
                return
            if parsed.path == "/api/analyze":
                self._handle_analyze(payload)
                return
            if parsed.path == "/api/modify":
                self._handle_modify(payload)
                return
            if parsed.path == "/api/feedback":
                self._handle_feedback(payload)
                return
            if parsed.path == "/api/secrets/qwen":
                self._handle_save_qwen_secret(payload)
                return
            self._send_json({"error": "Unknown API endpoint."}, status=404)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=400)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/secrets/qwen":
                self._handle_delete_qwen_secret()
                return
            self._send_json({"error": "Unknown API endpoint."}, status=404)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=400)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _handle_intake(self, payload: dict[str, Any]) -> None:
        request = str(payload.get("request") or "").strip()
        if not request:
            raise ValueError("请输入绘图或分析需求。")
        dataset = self._resolve_dataset(payload.get("dataset"))
        profile = profile_csv(dataset)
        intent = infer_requirement_auto(request, profile)
        self._send_json({"profile": profile.to_dict(), "intent": intent.to_dict()})

    def _handle_research_intake(self, payload: dict[str, Any]) -> None:
        self._send_json(self._research_intake_payload(payload))

    def _research_intake_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        goal = str(payload.get("goal") or payload.get("request") or "").strip()
        if not goal:
            raise ValueError("请输入研究目标。")
        raw_answers = payload.get("answers")
        answers = dict(raw_answers) if isinstance(raw_answers, dict) else {}
        context = str(payload.get("context") or "").strip()
        if context:
            answers["additional_context"] = context
        files = _files_from_value(payload.get("files"))
        if files:
            answers["files"] = files
        work_order = build_research_work_order(goal, answers)
        return {
            "work_order": work_order.to_dict(),
            "question_bank": intake_question_bank(),
        }

    def _handle_analyze(self, payload: dict[str, Any]) -> None:
        request = str(payload.get("request") or "").strip()
        if not request:
            raise ValueError("请输入绘图或分析需求。")
        dataset = self._resolve_dataset(payload.get("dataset"))
        profile = profile_csv(dataset)
        intent = infer_requirement_auto(request, profile)
        overrides = self._analysis_overrides(payload)
        style = dict(intent.style)
        for key in ("title", "x_title", "y_title"):
            if key in overrides and overrides[key]:
                style[key] = overrides[key]
        task = AnalysisTask(
            dataset_path=dataset,
            goal=request,
            task_type=TaskType(intent.task_type),
            x_column=overrides.get("x_column", intent.x_column),
            y_column=overrides.get("y_column", intent.y_column),
            group_column=overrides.get("group_column", intent.group_column),
            plot_kind=PlotKind(overrides.get("plot_kind", intent.plot_kind)),
            style=style,
            output_formats=overrides.get("output_formats") or tuple(intent.output_formats) or ("png",),
            fit_enabled=overrides.get("fit_enabled"),
            use_origin=bool(payload.get("use_origin")),
        )
        workflow = create_initial_plot_revision(task, RUNS_ROOT)
        self._send_json(self._workflow_payload(workflow, profile=profile, intent=intent))

    def _handle_modify(self, payload: dict[str, Any]) -> None:
        run_id = str(payload.get("run_id") or "").strip()
        request = str(payload.get("request") or "").strip()
        if not run_id:
            raise ValueError("Missing run_id. Please generate a plot before modifying it.")
        if not request:
            raise ValueError("请输入要修改图的要求。")
        revision_value = payload.get("revision")
        revision = int(revision_value) if revision_value is not None and revision_value != "" else None
        workflow = modify_plot_revision(
            run_id=run_id,
            request=request,
            runs_root=RUNS_ROOT,
            revision=revision,
            use_origin=bool(payload.get("use_origin")),
        )
        self._send_json(self._workflow_payload(workflow))

    def _handle_get_revision(self, query: str) -> None:
        params = parse_qs(query)
        run_id = params.get("run_id", [""])[0]
        revision = int(params.get("revision", ["0"])[0])
        workflow = load_plot_revision(run_id, revision, RUNS_ROOT)
        self._send_json(self._workflow_payload(workflow))

    def _handle_save_qwen_secret(self, payload: dict[str, Any]) -> None:
        api_key = str(payload.get("api_key") or "").strip()
        model = str(payload.get("model") or DEFAULT_QWEN_MODEL).strip() or DEFAULT_QWEN_MODEL
        base_url = str(payload.get("base_url") or DEFAULT_QWEN_BASE_URL).strip() or DEFAULT_QWEN_BASE_URL
        enable_thinking = bool(payload.get("enable_thinking", True))
        if api_key:
            save_secret(SECRET_DASHSCOPE_API_KEY, api_key)
        elif not qwen_status()["configured"]:
            raise SecretStoreError("请输入 DashScope API Key。")
        save_secret(SECRET_QWEN_MODEL, model)
        save_secret(SECRET_QWEN_BASE_URL, base_url)
        save_secret(SECRET_QWEN_ENABLE_THINKING, "true" if enable_thinking else "false")
        self._send_json(qwen_status())

    def _handle_delete_qwen_secret(self) -> None:
        for name in (
            SECRET_DASHSCOPE_API_KEY,
            SECRET_QWEN_MODEL,
            SECRET_QWEN_BASE_URL,
            SECRET_QWEN_ENABLE_THINKING,
        ):
            delete_secret(name)
        self._send_json(qwen_status())

    def _handle_feedback(self, payload: dict[str, Any]) -> None:
        record = self._feedback_record(payload)
        feedback_dir = RUNS_ROOT / "feedback"
        feedback_dir.mkdir(parents=True, exist_ok=True)
        feedback_path = feedback_dir / "feedback_samples.jsonl"
        with feedback_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._send_json(
            {
                "saved": True,
                "feedback_path": str(feedback_path),
                "record": record,
            }
        )

    def _feedback_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = str(payload.get("run_id") or "").strip()
        feedback = str(payload.get("feedback") or "").strip()
        correction = str(payload.get("correction") or "").strip()
        if not run_id:
            raise ValueError("Missing run_id. Please generate a plot before sending feedback.")
        if not feedback and not correction:
            raise ValueError("Please describe what was wrong or how the result should change.")
        revision_value = payload.get("revision")
        return {
            "schema_version": "feedback-sample/v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "revision": int(revision_value) if revision_value is not None and revision_value != "" else None,
            "feedback": feedback,
            "correction": correction,
            "request": str(payload.get("request") or ""),
            "plot_spec": payload.get("plot_spec") if isinstance(payload.get("plot_spec"), dict) else None,
            "artifact_urls": payload.get("artifact_urls") if isinstance(payload.get("artifact_urls"), dict) else {},
        }

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")
        return data

    def _resolve_dataset(self, value: Any) -> Path:
        if not value:
            return DEFAULT_DATASET
        candidate = Path(str(value).strip())
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        candidate = candidate.resolve()
        root = ROOT.resolve()
        if not str(candidate).lower().startswith(str(root).lower()):
            raise ValueError("当前原型只允许读取项目目录内的数据文件。")
        if not candidate.exists():
            raise ValueError(f"数据文件不存在：{candidate}")
        return candidate

    def _analysis_overrides(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw = payload.get("overrides")
        overrides = raw if isinstance(raw, dict) else {}
        parsed: dict[str, Any] = {}
        for key in ("x_column", "y_column", "group_column", "title", "x_title", "y_title"):
            if key in overrides:
                parsed[key] = _optional_text(overrides.get(key))
        if parsed.get("group_column") == "__none__":
            parsed["group_column"] = None

        if "plot_kind" in overrides and _optional_text(overrides.get("plot_kind")):
            parsed["plot_kind"] = _optional_text(overrides.get("plot_kind"))
        if "fit_enabled" in overrides:
            parsed["fit_enabled"] = bool(overrides.get("fit_enabled"))
        if "output_formats" in overrides:
            formats = _formats_from_value(overrides.get("output_formats"))
            if formats:
                parsed["output_formats"] = formats
        return parsed

    def _artifact_urls(self, artifacts: dict[str, str]) -> dict[str, str]:
        urls: dict[str, str] = {}
        for name, artifact in artifacts.items():
            path = Path(artifact)
            if not path.is_absolute():
                path = ROOT / path
            try:
                path.resolve().relative_to(ROOT.resolve())
            except ValueError:
                continue
            urls[name] = f"/file?path={path.resolve().as_posix()}"
        return urls

    def _workflow_payload(
        self,
        workflow: dict[str, Any],
        profile: Any | None = None,
        intent: Any | None = None,
    ) -> dict[str, Any]:
        result = workflow.get("result")
        result_dict = result.to_dict() if hasattr(result, "to_dict") else result
        plot_spec = workflow.get("plot_spec")
        plot_spec_dict = plot_spec.to_dict() if hasattr(plot_spec, "to_dict") else plot_spec
        edit_plan = workflow.get("edit_plan")
        edit_plan_dict = edit_plan.to_dict() if hasattr(edit_plan, "to_dict") else edit_plan
        artifacts = workflow.get("artifacts")
        if artifacts is None and hasattr(result, "artifacts"):
            artifacts = result.artifacts
        if artifacts is None and isinstance(result_dict, dict):
            artifacts = result_dict.get("artifacts", {})
        payload: dict[str, Any] = {
            "run_id": workflow.get("run_id"),
            "base_revision": workflow.get("base_revision"),
            "revision": workflow.get("revision"),
            "manifest": workflow.get("manifest"),
            "plot_spec": plot_spec_dict,
            "edit_plan": edit_plan_dict,
            "result": result_dict,
            "points": workflow.get("points", []),
            "artifact_urls": self._artifact_urls(artifacts or {}),
        }
        if profile is not None:
            payload["profile"] = profile.to_dict()
        if intent is not None:
            payload["intent"] = intent.to_dict()
        return payload

    def _serve_static(self, url_path: str) -> None:
        if url_path in {"", "/"}:
            file_path = WEB_ROOT / "index.html"
        else:
            file_path = (WEB_ROOT / unquote(url_path.lstrip("/"))).resolve()
            try:
                file_path.relative_to(WEB_ROOT.resolve())
            except ValueError:
                self._send_json({"error": "Forbidden."}, status=403)
                return
        if not file_path.exists() or not file_path.is_file():
            self._send_json({"error": "Not found."}, status=404)
            return
        self._send_file(file_path)

    def _serve_file_query(self, query: str) -> None:
        params = parse_qs(query)
        raw_path = params.get("path", [""])[0]
        file_path = Path(raw_path).resolve()
        try:
            file_path.relative_to(ROOT.resolve())
        except ValueError:
            self._send_json({"error": "Forbidden."}, status=403)
            return
        if not file_path.exists() or not file_path.is_file():
            self._send_json({"error": "Not found."}, status=404)
            return
        self._send_file(file_path)

    def _send_file(self, file_path: Path) -> None:
        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type = f"{content_type}; charset=utf-8"
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = False) -> None:
    server = ThreadingHTTPServer((host, port), OriginAIWebHandler)
    url = f"http://{host}:{port}"
    print(f"Origin AI Lab web UI: {url}")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    server.serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="origin-ai-web")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="Open the web UI in the default browser.")
    args = parser.parse_args(argv)
    run(host=args.host, port=args.port, open_browser=args.open)
    return 0


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _formats_from_value(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        raw_items = value.replace(";", ",").replace(" ", ",").split(",")
    elif isinstance(value, (list, tuple)):
        raw_items = value
    else:
        raw_items = []
    formats: list[str] = []
    for item in raw_items:
        fmt = str(item).strip().lower().lstrip(".")
        if fmt in {"png", "svg", "pdf", "opju"} and fmt not in formats:
            formats.append(fmt)
    return tuple(formats)


def _files_from_value(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_items = value.replace(";", "\n").splitlines()
    elif isinstance(value, (list, tuple)):
        raw_items = value
    else:
        raw_items = []
    files: list[str] = []
    for item in raw_items:
        text = str(item).strip()
        if text and text not in files:
            files.append(text)
    return files


if __name__ == "__main__":
    raise SystemExit(main())
