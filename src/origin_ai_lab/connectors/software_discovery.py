from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SoftwareInstall:
    name: str
    found: bool
    version: str | None = None
    install_path: Path | None = None
    executable_path: Path | None = None
    source: str = "unknown"
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "found": self.found,
            "version": self.version,
            "install_path": str(self.install_path) if self.install_path else None,
            "executable_path": str(self.executable_path) if self.executable_path else None,
            "source": self.source,
            "notes": list(self.notes),
        }


def discover_all() -> dict[str, SoftwareInstall]:
    return {
        "origin": discover_origin(),
        "comsol": discover_comsol(),
    }


def discover_comsol() -> SoftwareInstall:
    env_exe = _path_from_env("COMSOLBATCH_PATH")
    if env_exe:
        return _with_comsol_version(env_exe, source="COMSOLBATCH_PATH")

    for command in ("comsolbatch", "comsolbatch.exe", "comsol", "comsol.exe"):
        path = shutil.which(command)
        if path:
            return _with_comsol_version(Path(path), source="PATH")

    registry_hit = _find_uninstall_entry("COMSOL")
    for root in _comsol_candidate_roots(registry_hit):
        exe = _first_existing(
            root / "Multiphysics" / "bin" / "win64" / "comsolbatch.exe",
            root / "Multiphysics" / "bin" / "win64" / "comsol.exe",
            root / "bin" / "win64" / "comsolbatch.exe",
            root / "bin" / "win64" / "comsol.exe",
        )
        if exe:
            return _with_comsol_version(exe, install_path=root, source="registry/common-path")

    exe = _find_under_roots(
        [Path("C:/Program Files/COMSOL"), Path("C:/Program Files (x86)/COMSOL")],
        "comsolbatch.exe",
    ) or _find_under_roots([Path("C:/Program Files/COMSOL"), Path("C:/Program Files (x86)/COMSOL")], "comsol.exe")
    if exe:
        install_path = _infer_comsol_install_root(exe)
        return _with_comsol_version(exe, install_path=install_path, source="common-path-scan")

    return SoftwareInstall(
        name="COMSOL",
        found=False,
        version=_registry_value(registry_hit, "DisplayVersion"),
        source="not-found",
        notes=("Set COMSOLBATCH_PATH or add COMSOL bin/win64 to PATH if installed in a custom location.",),
    )


def discover_origin() -> SoftwareInstall:
    registry_hit = _find_uninstall_entry("OriginLab") or _find_uninstall_entry("Origin")
    install_location = _registry_value(registry_hit, "InstallLocation")
    version = _registry_value(registry_hit, "DisplayVersion")
    roots = [Path(install_location)] if install_location else []
    roots.extend([Path("C:/Program Files/OriginLab"), Path("C:/Program Files (x86)/OriginLab")])

    exe = None
    for root in roots:
        exe = _first_existing(
            root / "Origin64.exe",
            root / "Origin.exe",
            root / "OriginPro.exe",
        )
        if exe:
            break
    if exe is None:
        exe = _find_under_roots([root for root in roots if root.exists()], "Origin64.exe")

    originpro_available = _python_module_available("originpro")
    if exe:
        notes = ("originpro Python package is importable in this Python environment.",) if originpro_available else (
            "Origin executable was found; install/use an environment with the originpro Python package for automation.",
        )
        return SoftwareInstall(
            name="Origin/OriginPro",
            found=True,
            version=version,
            install_path=exe.parent,
            executable_path=exe,
            source="registry/common-path",
            notes=notes,
        )

    if registry_hit:
        return SoftwareInstall(
            name="Origin/OriginPro",
            found=True,
            version=version,
            install_path=Path(install_location) if install_location else None,
            source="registry",
            notes=("Origin is registered, but the executable was not found at the registered install path.",),
        )

    return SoftwareInstall(
        name="Origin/OriginPro",
        found=originpro_available,
        source="python-module" if originpro_available else "not-found",
        notes=(
            ("originpro is importable, but Origin itself was not found from registry/common paths.",)
            if originpro_available
            else ("Install Origin/OriginPro and the originpro Python package for automation.",)
        ),
    )


def _with_comsol_version(
    executable_path: Path,
    install_path: Path | None = None,
    source: str = "unknown",
) -> SoftwareInstall:
    version = _read_comsol_version(executable_path)
    return SoftwareInstall(
        name="COMSOL",
        found=True,
        version=version,
        install_path=install_path or _infer_comsol_install_root(executable_path),
        executable_path=executable_path,
        source=source,
    )


def _read_comsol_version(executable_path: Path) -> str | None:
    try:
        completed = subprocess.run(
            [str(executable_path), "-version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return None
    text = (completed.stdout or completed.stderr or "").strip()
    return text.splitlines()[0].strip() if text else None


def _comsol_candidate_roots(registry_hit: dict[str, Any] | None) -> list[Path]:
    roots: list[Path] = []
    install_location = _registry_value(registry_hit, "InstallLocation")
    if install_location:
        roots.append(Path(install_location))
    roots.extend(
        [
            Path("C:/Program Files/COMSOL/COMSOL64"),
            Path("C:/Program Files/COMSOL/COMSOL63"),
            Path("C:/Program Files/COMSOL/COMSOL62"),
            Path("C:/Program Files/COMSOL"),
            Path("C:/Program Files (x86)/COMSOL"),
        ]
    )
    return [root for root in roots if root.exists()]


def _infer_comsol_install_root(executable_path: Path) -> Path | None:
    parts = list(executable_path.parents)
    for parent in parts:
        if parent.name.lower().startswith("comsol") and (parent / "Multiphysics").exists():
            return parent
    for parent in parts:
        if parent.name == "Multiphysics":
            return parent
    return executable_path.parent


def _path_from_env(name: str) -> Path | None:
    value = os.environ.get(name)
    if not value:
        return None
    path = Path(value)
    return path if path.exists() else None


def _first_existing(*paths: Path) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _find_under_roots(roots: list[Path], filename: str) -> Path | None:
    for root in roots:
        if not root.exists():
            continue
        try:
            for path in root.rglob(filename):
                return path
        except OSError:
            continue
    return None


def _python_module_available(name: str) -> bool:
    try:
        __import__(name)
    except Exception:
        return False
    return True


def _find_uninstall_entry(name_fragment: str) -> dict[str, Any] | None:
    if os.name != "nt":
        return None
    try:
        import winreg
    except ImportError:
        return None

    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    needle = name_fragment.lower()
    for hive, subkey in roots:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                for index in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        child_name = winreg.EnumKey(key, index)
                        with winreg.OpenKey(key, child_name) as child:
                            entry = _registry_key_values(child)
                    except OSError:
                        continue
                    display_name = str(entry.get("DisplayName") or "").lower()
                    publisher = str(entry.get("Publisher") or "").lower()
                    if needle in display_name or needle in publisher:
                        return entry
        except OSError:
            continue
    return None


def _registry_key_values(key: Any) -> dict[str, Any]:
    try:
        import winreg
    except ImportError:
        return {}
    values: dict[str, Any] = {}
    for index in range(winreg.QueryInfoKey(key)[1]):
        try:
            name, value, _kind = winreg.EnumValue(key, index)
        except OSError:
            continue
        values[name] = value
    return values


def _registry_value(entry: dict[str, Any] | None, key: str) -> str | None:
    if not entry:
        return None
    value = entry.get(key)
    return str(value) if value not in {None, ""} else None
