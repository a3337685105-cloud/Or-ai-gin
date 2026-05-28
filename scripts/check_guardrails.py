#!/usr/bin/env python3
"""Project guardrail preflight check.

Checks staged/unstaged git changes for forbidden paths, confirmation paths,
large diffs, and secret-looking content. Configure with .codex/harness-policy.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def run_git(root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def path_matches(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    for pattern in patterns:
        p = pattern.replace("\\", "/")
        if normalized == p or normalized.startswith(p.rstrip("/") + "/"):
            return True
    return False


def changed_files(root: Path) -> list[str]:
    output = run_git(root, ["status", "--porcelain"])
    files: list[str] = []
    for line in output.splitlines():
        if not line:
            continue
        raw = line[3:]
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        files.append(raw.replace("\\", "/"))
    return sorted(set(files))


def diff_line_count(root: Path) -> int:
    output = run_git(root, ["diff", "--numstat", "HEAD"])
    total = 0
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        for value in parts[:2]:
            if value.isdigit():
                total += int(value)
    return total


def scan_secrets(root: Path, files: list[str], patterns: list[str], exclude_paths: list[str] | None = None) -> list[str]:
    findings: list[str] = []
    regexes = [re.compile(p, re.IGNORECASE) for p in patterns]
    excludes = exclude_paths or []
    for file_name in files:
        if path_matches(file_name, excludes):
            continue
        path = root / file_name
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for idx, line in enumerate(content.splitlines(), start=1):
            for regex in regexes:
                if regex.search(line):
                    findings.append(f"{file_name}:{idx} matches {regex.pattern}")
                    break
    return findings


def load_policy(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Policy file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Project root")
    parser.add_argument("--policy", default=".codex/harness-policy.json", help="Policy JSON path")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = root / policy_path

    policy = load_policy(policy_path)
    files = changed_files(root)
    line_count = diff_line_count(root)

    errors: list[str] = []
    warnings: list[str] = []

    forbidden = policy.get("forbidden_paths", [])
    confirmation = policy.get("require_confirmation_paths", [])
    secret_patterns = policy.get("secret_patterns", [])
    secret_excludes = policy.get("secret_scan_exclude_paths", [])
    max_lines = int(policy.get("max_changed_lines_warning", 0) or 0)
    mode = policy.get("mode", "warn")

    for file_name in files:
        if path_matches(file_name, forbidden):
            errors.append(f"Forbidden path modified: {file_name}")
        if path_matches(file_name, confirmation):
            warnings.append(f"Requires confirmation/review: {file_name}")

    if max_lines and line_count > max_lines:
        warnings.append(f"Large diff: {line_count} changed lines exceeds {max_lines}")

    for finding in scan_secrets(root, files, secret_patterns, secret_excludes):
        errors.append(f"Potential secret: {finding}")

    print("Harness guardrail check")
    print(f"Root: {root}")
    print(f"Changed files: {len(files)}")
    print(f"Changed lines: {line_count}")

    if warnings:
        print("\nWarnings:")
        for item in warnings:
            print(f"- {item}")

    if errors:
        print("\nErrors:")
        for item in errors:
            print(f"- {item}")

    should_fail = bool(errors) or args.strict and bool(warnings) or mode == "enforce" and bool(warnings)
    if should_fail:
        print("\nResult: blocked")
        return 1

    print("\nResult: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
