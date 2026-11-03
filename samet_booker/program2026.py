"""Oficiální program Samet 2026 podle https://gympb.cz/samet/ (stav k 2. 11. 2026).

Slouží k přesnému přiřazení akcí do bloků, dokud web nezveřejní nabídku
přímo v Blokové rezervaci. Jakmile ji zveřejní, má přednost to, co je na webu.

Bloky: A 8:00, B 9:00, C 10:00, D 11:00 (po 45 min), AB 8:00–9:30, CD 10:00–11:30,
ODPO 12:00–14:00 (jen vyšší gymnázium). Přihlašování 3. 11. 19:00 až 6. 11. 16:00.
"""
from __future__ import annotations

# (název, bloky, místnost, kapacita, poznámka)
EVENTS: list[tuple[str, tuple[str, ...], str, int, str]] = [
    # jednohodinové
    ("Jaká byla fyzika a matematika v 80. letech?", ("A", "C"), "FYZu", 30, ""),
    ("V rytmu režimu, v rytmu svobody: Od Spartakiády k diskotéce 80. let", ("A", "B"), "tělocvična", 20, ""),
    ("Básnicky bydlí člověk...?", ("A",), "3.B", 16, ""),
    ("Moje osobní bezpečnost", ("A", "B", "C", "D"), "3.A", 20, ""),
    ("Co je pravda a co ne?", ("A",), "IVT 1", 16, ""),
    ("Vojenský výcvik", ("A", "B", "C", "D"), "hřiště", 16, "sportovní oblečení, venku"),
    ("Berlínská zeď", ("A", "B", "D"), "JAZ 1", 25, "jen němčináři"),
    ("Od izolace ke globální síti", ("A", "B"), "4.B", 30, ""),
    ("Ekonomická únikovka: od front k podnikání", ("A", "B"), "1.C", 15, ""),
    ("Právo volby (film)", ("A", "B"), "oktáva", 32, "jen vyšší gymnázium"),
    ("Slavné dny aneb Významné momenty 20. století (film)", ("A", "B", "C", "D"), "2.C", 32, ""),
    ("Havel 90: Moc bezmocných (film)", ("A", "B", "C", "D", "ODPO"), "3.D", 32, ""),
    ("Za den vydělali víc než jiní za měsíc", ("B", "D"), "septima", 25, ""),
    ("Mikroskopování se zrcátkovými mikroskopy", ("B", "D"), "BIOp", 15, ""),
    ("Výtvarná výchova za socialismu", ("B", "C"), "sexta", 30, ""),
    ("Komiksový román A aneb Jak vypadá nesvobodný svět?", ("C", "D"), "tercie", 20, ""),
    ("Months of the Velvet Revolution in the Guardian newspaper", ("C",), "6.S", 16, "jen vyšší gymnázium, anglicky"),
    # dvouhodinové
    ("Listopád Aleny Mornštajnové", ("AB",), "2.B", 32, ""),
    ("Svoboda v životě a díle Franze Kafky", ("AB",), "knihovna", 30, ""),
    ("Vliv televizního vysílání na smýšlení veřejnosti v době normalizace", ("AB", "CD"), "2.A", 32, ""),
    ("Bratříčku, nauč se písničku!", ("AB",), "VYVu", 25, "vezmi kytaru/ukulele"),
    ("Všichni moji blízcí (film)", ("AB",), "kvinta", 32, ""),
    ("Bratři Okamurovi (film)", ("AB",), "6.S", 32, ""),
    ("Pan Nikdo proti Putinovi (film)", ("AB", "ODPO"), "1.D", 32, ""),
    ("Kuciak: Vražda novináře (film)", ("AB",), "HUVu", 120, ""),
    ("Velký vlastenecký výlet (film)", ("AB",), "1.B", 32, ""),
    ("Demokracie na mapě: Jak volilo Česko?", ("CD",), "ICT 2", 20, ""),
    ("Zdeněk Svěrák 90 (film)", ("CD",), "1.C", 32, ""),
    ("Svět podle Daliborka (film)", ("CD",), "1.B", 32, "jen vyšší gymnázium"),
    ("Marie Bastlová: Ptám se já", ("CD",), "HUVu", 120, ""),
    ("Severní Korea aneb Nejuzavřenější stát světa", ("CD",), "oktáva", 30, ""),
    ("Hokej vs StB - konec mistrů světa", ("CD",), "3.B", 32, ""),
    ("Scrolujeme, tedy jsme? Jak sociální sítě mění naše vnímání reality i sebe sama", ("CD",), "2.B", 32, ""),
    ("Veřejné finance přepočítané na cheeseburgery", ("CD", "ODPO"), "kvinta", 30, ""),
    ("Ústavní soud", ("CD",), "3.C", 30, ""),
    ("Svoboda jen pro někoho?", ("CD", "ODPO"), "4.A", 30, ""),
    ("Tvoříme Evropu", ("CD", "ODPO"), "4.C", 30, ""),
    ("Co je totalita?", ("CD",), "2.D", 30, ""),
    # odpoledne
    ("Dalajlama - Oceán moudrosti (film)", ("ODPO",), "kino", 250, "strhne se 80 Kč z Bakalářů"),
    ("Reportéři ČT a Vinohradská 12 aneb Role veřejnoprávních médií ve společnosti", ("ODPO",), "HUVu", 120, ""),
    ("Věřím, že více světla potřeba nebude (film)", ("ODPO",), "VYVu", 70, ""),
]


def catalog() -> list[dict]:
    out = []
    for title, bloks, room, cap, note in EVENTS:
        for b in bloks:
            out.append({"title": title, "blok": b, "location": room, "capacity": cap, "note": note,
                        "exact": False, "source": "skola"})
    return out
