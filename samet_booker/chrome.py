"""Najde a spustí skutečný Chrome (nebo Edge) s vlastním profilem a ladicím portem.

Chrome spouštíme sami, bez automatizačních přepínačů, aby šlo normálně
přihlásit školním Google účtem. Playwright se pak jen připojí přes CDP.
"""
from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
import time
from pathlib import Path


def _windows_candidates() -> list[str]:
    env = os.environ
    roots = [env.get("ProgramFiles"), env.get("ProgramFiles(x86)"), env.get("LocalAppData")]
    out = []
    for root in filter(None, roots):
        out.append(os.path.join(root, "Google", "Chrome", "Application", "chrome.exe"))
    for root in filter(None, roots):
        out.append(os.path.join(root, "Microsoft", "Edge", "Application", "msedge.exe"))
    return out


def find_browser() -> str | None:
    custom = os.environ.get("SAMET_CHROME")
    if custom and Path(custom).exists():
        return custom
    system = platform.system()
    if system == "Windows":
        candidates = _windows_candidates()
    elif system == "Darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    else:
        candidates = [
            shutil.which(n) or ""
            for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge")
        ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) == 0


def launch(exe: str, profile_dir: Path, debug_port: int, app_url: str, extra_args: list[str] | None = None) -> subprocess.Popen | None:
    """Spustí Chrome s ovládacím panelem v okně aplikace. Když už běží, nic nedělá."""
    if port_open(debug_port):
        return None
    profile_dir.mkdir(parents=True, exist_ok=True)
    args = [
        exe,
        f"--remote-debugging-port={debug_port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        # Ať časovače stránky běží naplno i v pozadí.
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-backgrounding-occluded-windows",
        f"--app={app_url}",
        "--window-size=560,900",
    ]
    if extra_args:
        args.extend(extra_args)
    if os.environ.get("SAMET_CHROME_ARGS"):
        args.extend(os.environ["SAMET_CHROME_ARGS"].split())
    kwargs = {}
    if platform.system() == "Windows":
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
    deadline = time.time() + 20
    while time.time() < deadline:
        if port_open(debug_port):
            return proc
        time.sleep(0.2)
    raise RuntimeError("Chrome se nepodařilo spustit. Pokud je otevřené staré okno SAMET Booker, zavři ho a spusť appku znovu.")
