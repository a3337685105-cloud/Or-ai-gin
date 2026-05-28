from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from typing import Any


STORE_VERSION = 1
BACKEND_WINDOWS_DPAPI = "windows-dpapi"


class SecretStoreError(RuntimeError):
    """Raised when local secret storage cannot safely read or write data."""


def config_dir() -> Path:
    override = os.getenv("ORIGIN_AI_CONFIG_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    appdata = os.getenv("APPDATA", "").strip()
    if appdata:
        return Path(appdata) / "OriginAILab"
    return Path.home() / ".origin_ai_lab"


def store_path() -> Path:
    return config_dir() / "secrets.json"


def save_secret(name: str, value: str) -> None:
    if not value:
        raise SecretStoreError("Secret value cannot be empty.")
    payload = _read_store()
    payload.setdefault("secrets", {})[name] = {
        "backend": BACKEND_WINDOWS_DPAPI,
        "value": base64.b64encode(_protect(value.encode("utf-8"))).decode("ascii"),
    }
    _write_store(payload)


def get_secret(name: str) -> str | None:
    payload = _read_store()
    item = payload.get("secrets", {}).get(name)
    if not item:
        return None
    if item.get("backend") != BACKEND_WINDOWS_DPAPI:
        raise SecretStoreError(f"Unsupported secret backend: {item.get('backend')}")
    encrypted = base64.b64decode(str(item.get("value", "")))
    return _unprotect(encrypted).decode("utf-8")


def delete_secret(name: str) -> bool:
    payload = _read_store()
    secrets = payload.setdefault("secrets", {})
    existed = name in secrets
    secrets.pop(name, None)
    _write_store(payload)
    return existed


def secret_exists(name: str) -> bool:
    payload = _read_store()
    return name in payload.get("secrets", {})


def store_status() -> dict[str, Any]:
    return {
        "path": str(store_path()),
        "backend": BACKEND_WINDOWS_DPAPI if sys.platform == "win32" else "unsupported",
        "available": sys.platform == "win32",
    }


def _read_store() -> dict[str, Any]:
    path = store_path()
    if not path.exists():
        return {"version": STORE_VERSION, "secrets": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SecretStoreError("Secret store is invalid.")
    data.setdefault("version", STORE_VERSION)
    data.setdefault("secrets", {})
    return data


def _write_store(payload: dict[str, Any]) -> None:
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _protect(data: bytes) -> bytes:
    if sys.platform != "win32":
        raise SecretStoreError("Secure local key storage currently requires Windows DPAPI.")
    return _windows_crypt_protect(data)


def _unprotect(data: bytes) -> bytes:
    if sys.platform != "win32":
        raise SecretStoreError("Secure local key storage currently requires Windows DPAPI.")
    return _windows_crypt_unprotect(data)


def _windows_crypt_protect(data: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DataBlob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    in_buffer = ctypes.create_string_buffer(data)
    in_blob = DataBlob(len(data), ctypes.cast(in_buffer, ctypes.POINTER(ctypes.c_char)))
    out_blob = DataBlob()
    ok = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise SecretStoreError("Windows DPAPI CryptProtectData failed.")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _windows_crypt_unprotect(data: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DataBlob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    in_buffer = ctypes.create_string_buffer(data)
    in_blob = DataBlob(len(data), ctypes.cast(in_buffer, ctypes.POINTER(ctypes.c_char)))
    out_blob = DataBlob()
    ok = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise SecretStoreError("Windows DPAPI CryptUnprotectData failed.")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)
