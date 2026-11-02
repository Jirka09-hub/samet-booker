from __future__ import annotations

import json
import os
import platform
from pathlib import Path

BASE_URL = os.environ.get("SAMET_URL", "https://rezervace.gympb.cz/")
SAMET_DATE = "2026-11-11"
DEFAULT_OPEN_AT = "2026-11-03T19:00:00"
DEBUG_PORT = int(os.environ.get("SAMET_DEBUG_PORT", "9333"))
UI_PORT = int(os.environ.get("SAMET_UI_PORT", "8765"))


def data_dir() -> Path:
    if platform.system() == "Windows" and os.environ.get("LOCALAPPDATA"):
        d = Path(os.environ["LOCALAPPDATA"]) / "samet-booker"
    else:
        d = Path.home() / ".samet-booker"
    d.mkdir(parents=True, exist_ok=True)
    return d


def logs_dir() -> Path:
    d = data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def settings_path() -> Path:
    return data_dir() / "settings.json"


def load_settings() -> dict:
    defaults = {"open_at": DEFAULT_OPEN_AT, "plan": {}, "prefer": {"p1": "single", "p2": "single"},
                "catalog": [], "dry_run": False, "fill_any": True, "demo": False}
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
        if not isinstance(data.get("plan"), dict):
            data["plan"] = {}
        defaults.update(data)
    except Exception:
        pass
    return defaults


def save_settings(s: dict) -> None:
    settings_path().write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
