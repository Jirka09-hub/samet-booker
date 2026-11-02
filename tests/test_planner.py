from samet_booker import planner


def opt(i, blok, title, free=5):
    return {"id": str(i), "blok": blok, "title": title, "free": free}


OPTS = [
    opt(1, "A", "Berlínská zeď", 0), opt(2, "A", "Básně"), opt(3, "A", "Disent"),
    opt(4, "B", "Hlasy"), opt(5, "AB", "Film"), opt(6, "C", "Stávka"), opt(7, "D", "Charta"),
    opt(8, "CD", "Pelíšky"), opt(9, "ODPO", "Koncert"),
]
PREF = {"p1": "single", "p2": "single"}


def titles(picks):
    return [o["title"] for o in picks]


def test_substitute_before_other_structure():
    plan = {"A": ["Berlínská zeď", "Básně"], "B": ["Hlasy"], "AB": ["Film"], "C": ["Stávka"], "D": ["Charta"], "ODPO": ["Koncert"]}
    picks, notes = planner.best_program(OPTS, plan, PREF, True)
    assert titles(picks) == ["Básně", "Hlasy", "Stávka", "Charta", "Koncert"]
    assert any("obsazené" in n for n in notes)


def test_falls_back_to_double():
    plan = {"A": ["Berlínská zeď"], "B": ["Hlasy"], "AB": ["Film"], "C": ["Stávka"], "D": ["Charta"], "ODPO": ["Koncert"]}
    picks, _ = planner.best_program(OPTS, plan, PREF, True)
    assert titles(picks) == ["Film", "Stávka", "Charta", "Koncert"]


def test_fill_any_and_strict():
    plan = {"A": ["Berlínská zeď"], "B": ["Hlasy"], "C": ["Stávka"], "D": ["Charta"], "ODPO": ["Koncert"]}
    picks, _ = planner.best_program(OPTS, plan, PREF, True, fill_any=True)
    assert len(picks) == 5 and picks[0]["blok"] in ("A", "AB")
    picks, _ = planner.best_program(OPTS, plan, PREF, True, fill_any=False)
    assert picks is None


def test_no_duplicate_event():
    opts = [opt(1, "A", "Zeď"), opt(2, "B", "Zeď"), opt(3, "B", "Jiné"), opt(4, "C", "C"), opt(5, "D", "D")]
    plan = {"A": ["Zeď"], "B": ["Zeď", "Jiné"], "C": ["C"], "D": ["D"]}
    picks, _ = planner.best_program(opts, plan, PREF, False)
    assert titles(picks) == ["Zeď", "Jiné", "C", "D"]


def test_prefer_double():
    plan = {"A": ["Básně"], "B": ["Hlasy"], "AB": ["Film"], "C": ["Stávka"], "D": ["Charta"]}
    picks, _ = planner.best_program(OPTS, plan, {"p1": "double", "p2": "single"}, False)
    assert titles(picks) == ["Film", "Stávka", "Charta"]
