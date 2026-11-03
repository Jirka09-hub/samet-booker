"""Zkušební (demo) verze stránky Bloková rezervace, běží jen lokálně.

Kopíruje strukturu skutečné stránky (stejné data-testid), takže si na ní jde
vyzkoušet celé přihlášení nanečisto. Jedna akce se schválně hned po otevření
zaplní, aby bylo vidět, že funguje náhradník.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime

DAY = "2026-11-11"
_T = {
    "A": ("08:00", 45), "B": ("09:00", 45), "AB": ("08:00", 90),
    "C": ("10:00", 45), "D": ("11:00", 45), "CD": ("10:00", 90), "ODPO": ("12:00", 120),
}
_EVENTS = [
    ("A", "Berlínská zeď", "JAZ 1", 3), ("A", "Básnicky bydlí člověk…?", "3.B", 16),
    ("A", "Listopad v dobovém tisku", "2.A", 20), ("A", "Disent a undergound", "4.C", 18),
    ("B", "Berlínská zeď", "JAZ 1", 25), ("B", "Hlasy z ulice", "1.B", 15),
    ("B", "Šifry StB", "INF", 12), ("B", "Plakáty revoluce", "VV", 20),
    ("AB", "Bratři Okamurovi (film)", "6.S", 32), ("AB", "Beseda s pamětníkem", "AULA", 60),
    ("C", "Studentská stávka", "2.B", 20), ("C", "Normalizace v kuchyni", "CHEM", 14),
    ("C", "Rocková scéna 80. let", "HV", 18),
    ("D", "Charta 77", "3.A", 22), ("D", "Pražské jaro", "4.A", 20), ("D", "Ekologické hnutí", "BIO", 16),
    ("CD", "Pelíšky (film)", "6.S", 32), ("CD", "Workshop: samizdat", "KNIH", 12),
    ("ODPO", "Koncert", "AULA", 120), ("ODPO", "Debata s politology", "6.S", 40),
    ("ODPO", "Procházka po stopách revoluce", "SRAZ U VCHODU", 25),
]

LOCK = threading.Lock()
STATE: dict = {"open_at": 0.0, "terminy": [], "vyber": []}


def reset(open_at: float):
    terminy = []
    for i, (blok, nazev, mistnost, kap) in enumerate(_EVENTS):
        hhmm, delka = _T[blok]
        start = datetime.fromisoformat(f"{DAY}T{hhmm}:00").timestamp() * 1000
        terminy.append({"id": f"demo{i:02d}", "akceId": nazev, "blok": blok, "nazev": nazev, "mistnost": mistnost,
                        "kapacita": kap, "obsazeno": 0, "startMs": start, "delkaMinut": delka})
    with LOCK:
        STATE.update(open_at=open_at, terminy=terminy, vyber=[])


def _simulate_rush():
    """Po otevření se „Berlínská zeď“ v 1. hodině rychle zaplní."""
    now = time.time()
    with LOCK:
        if STATE["open_at"] and now > STATE["open_at"] + 0.8:
            for t in STATE["terminy"]:
                if t["id"] == "demo00" and t["id"] not in STATE["vyber"]:
                    t["obsazeno"] = t["kapacita"]


def state() -> dict:
    _simulate_rush()
    with LOCK:
        is_open = STATE["open_at"] and time.time() >= STATE["open_at"]
        return {
            "stav": "ok",
            "faze": "otevreno",
            "uroven": "full",
            "terminy": STATE["terminy"] if is_open else [],
            "vyber": list(STATE["vyber"]),
            "openAt": STATE["open_at"],
        }


def save(ids: list[str]) -> dict:
    _simulate_rush()
    time.sleep(0.4)  # jako skutečný server
    with LOCK:
        if not (STATE["open_at"] and time.time() >= STATE["open_at"]):
            return {"ok": False, "message": "Přihlašování ještě není otevřené."}
        by = {t["id"]: t for t in STATE["terminy"]}
        for i in ids:
            t = by.get(i)
            if not t:
                return {"ok": False, "message": "Neznámý termín."}
            if i not in STATE["vyber"] and t["obsazeno"] >= t["kapacita"]:
                return {"ok": False, "message": f"Akce „{t['nazev']}“ se mezitím zaplnila. Vyberte prosím jinou."}
        for i in STATE["vyber"]:
            by[i]["obsazeno"] -= 1
        for i in ids:
            by[i]["obsazeno"] += 1
        changed = sorted(ids) != sorted(STATE["vyber"])
        STATE["vyber"] = list(ids)
        return {"ok": True, "zmeneno": changed, "vyber": list(ids)}


def program_cards() -> list[dict]:
    out = []
    for blok, nazev, mistnost, kap in _EVENTS:
        hhmm, delka = _T[blok]
        key = (nazev, hhmm)
        if key in {(c["nazev"], c["cas"]) for c in out}:
            continue
        out.append({"nazev": nazev, "cas": hhmm, "delka": delka, "mistnost": mistnost, "kapacita": kap})
    return out
