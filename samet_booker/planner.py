"""Výpočet nejlepšího platného programu z tvých voleb a aktuální obsazenosti.

Pravidla webu (Samet 2026):
- dopoledne se musí beze zbytku pokrýt 1.–4. hodina: A+B+C+D, AB+C+D, A+B+CD nebo AB+CD,
- studenti s plným programem navíc vybírají právě jednu odpolední akci (ODPO),
- stejnou akci nelze vybrat dvakrát.
"""
from __future__ import annotations

import difflib
import itertools
import re
import unicodedata

SLOTS = ["A", "B", "AB", "C", "D", "CD", "ODPO"]
SLOT_NAMES = {
    "A": "1. hodina", "B": "2. hodina", "AB": "1. + 2. hodina",
    "C": "3. hodina", "D": "4. hodina", "CD": "3. + 4. hodina", "ODPO": "Odpoledne",
}
STRUCTURES = [("A", "B", "C", "D"), ("AB", "C", "D"), ("A", "B", "CD"), ("AB", "CD")]
FALLBACK_RANK = 10  # „cokoli volného“ je až za všemi tvými volbami


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "")
    return " ".join(s.split()).casefold()


def key(s: str) -> str:
    """Název bez diakritiky, interpunkce a mezer, aby „...“ vs „…“ apod. nevadilo."""
    s = unicodedata.normalize("NFKD", norm(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s)


def similarity(a: str, b: str) -> float:
    ka, kb = key(a), key(b)
    if not ka or not kb:
        return 0.0
    if ka == kb:
        return 1.0
    if min(len(ka), len(kb)) >= 8 and (ka in kb or kb in ka):
        return 0.95
    return difflib.SequenceMatcher(None, ka, kb).ratio()


def find(title: str, items: list[dict], threshold: float = 0.85) -> dict | None:
    """Najde akci podle názvu, odolně vůči drobným rozdílům v zápisu."""
    best, score = None, 0.0
    for o in items:
        sc = similarity(title, o["title"])
        if sc > score:
            best, score = o, sc
    return best if score >= threshold else None


# Nepreferovaná varianta (dvouhodinovka místo hodin nebo naopak) přijde na řadu
# až po tvém náhradníkovi, ale před „cokoli volného“.
STRUCT_PENALTY = 1.5


def structure_penalty(struct: tuple[str, ...], prefer: dict) -> float:
    pen = 0.0
    first_double = "AB" in struct
    second_double = "CD" in struct
    if prefer.get("p1") == "double" and not first_double:
        pen += STRUCT_PENALTY
    if prefer.get("p1", "single") == "single" and first_double:
        pen += STRUCT_PENALTY
    if prefer.get("p2") == "double" and not second_double:
        pen += STRUCT_PENALTY
    if prefer.get("p2", "single") == "single" and second_double:
        pen += STRUCT_PENALTY
    return pen


def best_program(options: list[dict], plan: dict, prefer: dict, need_odpo: bool,
                 fill_any: bool = True) -> tuple[list[dict] | None, list[str]]:
    """options: [{id, blok, title, free (int|None), mine (bool)}].

    Vrátí (vybrané možnosti, poznámky). Když nejde složit platný program, vrátí (None, poznámky).
    """
    notes: list[str] = []
    by_slot: dict[str, list[dict]] = {s: [] for s in SLOTS}
    for o in options:
        if o.get("blok") in by_slot:
            by_slot[o["blok"]].append(o)

    def available(o):
        return o.get("mine") or o.get("free") is None or o["free"] > 0

    cands: dict[str, list[tuple[int, dict]]] = {}
    for slot in SLOTS:
        lst: list[tuple[int, dict]] = []
        used = set()
        for rank, title in enumerate(plan.get(slot) or []):
            if not title:
                continue
            o = find(title, by_slot[slot])
            if not o:
                notes.append(f"{SLOT_NAMES[slot]}: „{title}“ v nabídce není.")
                continue
            if not available(o):
                notes.append(f"{SLOT_NAMES[slot]}: „{title}“ je obsazené.")
                continue
            lst.append((rank, o))
            used.add(o["id"])
        if fill_any:
            rest = [o for o in by_slot[slot] if o["id"] not in used and available(o)]
            rest.sort(key=lambda o: -(o.get("free") or 0))
            lst += [(FALLBACK_RANK + i, o) for i, o in enumerate(rest)]
        cands[slot] = lst

    best = None
    for struct in STRUCTURES:
        slots = list(struct) + (["ODPO"] if need_odpo else [])
        if any(not cands[s] for s in slots):
            continue
        # Stačí pár nejlepších kandidátů na slot, aby kombinací nebylo moc.
        pools = [cands[s][:6] for s in slots]
        for combo in itertools.product(*pools):
            titles = [key(o["title"]) for _, o in combo]
            if len(set(titles)) != len(titles):
                continue
            cost = sum(r for r, _ in combo) + structure_penalty(struct, prefer)
            if best is None or cost < best[0]:
                best = (cost, [o for _, o in combo])
    if best is None:
        return None, notes
    return best[1], notes
