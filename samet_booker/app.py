"""Spouští ovládací panel (malý lokální web) a Chrome, propojuje je s botem."""
from __future__ import annotations

import json
import queue
import sys
import threading
import time
import traceback
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources

from . import __version__, chrome, config, demo
from .bot import Bot, Cancelled


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.logs: list[dict] = []
        self.status = {"phase": "idle", "target": None, "busy": False, "chrome": False}
        self.settings = config.load_settings()
        self.ui_port = config.UI_PORT

    def log(self, msg: str, level: str = "info"):
        line = {"t": time.time(), "msg": msg, "level": level}
        with self.lock:
            self.logs.append(line)
            self.logs = self.logs[-500:]
        print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)
        try:
            with open(config.logs_dir() / "log.txt", "a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S.%f} [{level}] {msg}\n")
        except Exception:
            pass

    def set_status(self, **kw):
        with self.lock:
            self.status.update(kw)

    def snapshot(self, since: float = 0) -> dict:
        with self.lock:
            return {
                "status": dict(self.status),
                "logs": [l for l in self.logs if l["t"] > since],
                "settings": self.settings,
                "now": time.time(),
                "version": __version__,
            }


STATE = State()
JOBS: "queue.Queue[tuple[str, dict]]" = queue.Queue()
BOT = Bot(STATE.log, STATE.set_status)


def worker():
    while True:
        name, args = JOBS.get()
        STATE.set_status(busy=True, job=name)
        try:
            run_job(name, args)
        except Cancelled:
            STATE.log("Zrušeno.", "warn")
        except Exception as e:
            STATE.log(f"Chyba: {e}", "err")
            traceback.print_exc()
        finally:
            STATE.set_status(busy=False, job=None, phase="idle", target=None)


def apply_mode():
    if STATE.settings.get("demo"):
        BOT.set_base(f"http://127.0.0.1:{STATE.ui_port}/demo/")
    else:
        BOT.set_base(config.BASE_URL)


def run_job(name: str, args: dict):
    apply_mode()
    st = STATE.settings
    plan, prefer = st.get("plan") or {}, st.get("prefer") or {}
    has_plan = any(any(v) for v in plan.values())
    if name == "connect":
        BOT.connect()
        STATE.set_status(chrome=True)
        BOT.open_site()
    elif name == "open_site":
        BOT.open_site()
    elif name == "catalog":
        items = BOT.load_catalog()
        with STATE.lock:
            st["catalog"] = items
        config.save_settings(st)
    elif name == "probe":
        BOT.probe(plan, prefer)
    elif name in ("arm", "book_now"):
        if not has_plan:
            STATE.log("Nejdřív vyber akce.", "warn")
            return
        if name == "book_now":
            BOT.goto_block_page()
            ok = BOT.book(plan, prefer, bool(st.get("dry_run")), bool(st.get("fill_any", True)))
            return
        open_at = datetime.fromisoformat(st.get("open_at") or config.DEFAULT_OPEN_AT)
        if st.get("demo"):
            demo.reset(open_at.timestamp())
            STATE.log("Demo: zkušební stránka se otevře v nastavený čas, Berlínská zeď (1. hodina) se hned zaplní.", "info")
        STATE.set_status(result=None)
        ok = BOT.run_at(open_at, plan, prefer, bool(st.get("dry_run")), bool(st.get("fill_any", True)))
        STATE.set_status(result="ok" if ok else "err", result_at=time.time())


def _web(name: str) -> bytes:
    return resources.files("samet_booker").joinpath("web/" + name).read_bytes()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, _web("index.html"), "text/html; charset=utf-8")
        if self.path in ("/demo", "/demo/"):
            return self._send(200, _web("demo_program.html"), "text/html; charset=utf-8")
        if self.path.startswith("/demo/samet"):
            return self._send(200, _web("demo_samet.html"), "text/html; charset=utf-8")
        if self.path == "/demo/api/state":
            return self._json(demo.state())
        if self.path == "/demo/api/program":
            return self._json(demo.program_cards())
        if self.path.startswith("/api/state"):
            since = 0.0
            if "since=" in self.path:
                try:
                    since = float(self.path.split("since=")[1])
                except ValueError:
                    pass
            return self._json(STATE.snapshot(since))
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            body = {}
        path = self.path
        if path == "/demo/api/save":
            return self._json(demo.save(list(body.get("terminIds") or [])))
        if path == "/api/settings":
            with STATE.lock:
                for k in ("plan", "prefer", "open_at", "dry_run", "fill_any", "demo"):
                    if k in body:
                        STATE.settings[k] = body[k]
            config.save_settings(STATE.settings)
            return self._json({"ok": True})
        if path == "/api/cancel":
            BOT.cancel.set()
            return self._json({"ok": True})
        job = path.removeprefix("/api/")
        if job in ("connect", "open_site", "catalog", "probe", "arm", "book_now"):
            if STATE.status.get("busy"):
                return self._json({"ok": False, "error": "Právě něco běží."}, 409)
            BOT.cancel.clear()
            JOBS.put((job, body))
            return self._json({"ok": True})
        self._json({"ok": False, "error": "neznámá akce"}, 404)


def main():
    server = None
    for port in range(config.UI_PORT, config.UI_PORT + 20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if server is None:
        print("Nepodařilo se otevřít port pro ovládací panel.")
        sys.exit(1)
    STATE.ui_port = server.server_address[1]
    url = f"http://127.0.0.1:{STATE.ui_port}/"
    if STATE.settings.get("demo") and demo.STATE["open_at"] == 0:
        demo.reset(time.time() + 120)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Thread(target=worker, daemon=True).start()
    STATE.log(f"SAMET Booker {__version__} běží. Data: {config.data_dir()}", "info")

    exe = chrome.find_browser()
    if not exe:
        STATE.log("Nenašel jsem Google Chrome ani Edge. Nainstaluj Chrome a spusť znovu.", "err")
        webbrowser.open(url)
    else:
        try:
            chrome.launch(exe, config.data_dir() / "chrome-profile", config.DEBUG_PORT, url)
            JOBS.put(("connect", {}))
        except Exception as e:
            STATE.log(str(e), "err")
            webbrowser.open(url)

    print(f"Ovládací panel: {url}  (okno nech otevřené, Ctrl+C ukončí)")
    try:
        while True:
            time.sleep(1)
            if exe and not chrome.port_open(config.DEBUG_PORT) and STATE.status.get("chrome"):
                print("Chrome byl zavřen, končím.")
                break
    except KeyboardInterrupt:
        pass
