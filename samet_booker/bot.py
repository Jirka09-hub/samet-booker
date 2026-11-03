"""Práce se stránkou: načtení programu, nalezení akcí a samotná rezervace.

Vše běží v jednom vlákně (Playwright sync API to vyžaduje).
"""
from __future__ import annotations

import email.utils
import re
import threading
import time
import urllib.request
from datetime import datetime
from typing import Callable

from playwright.sync_api import Page, sync_playwright

from . import config, planner, program2026

# ---------------------------------------------------------------------------
# JavaScript, který běží ve stránce
# ---------------------------------------------------------------------------

JS_CATALOG = r"""
() => {
  const re = /(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\s*v\s*(\d{1,2}):(\d{2})(?:\s*[·•\-]\s*(\d+)\s*min)?/;
  const nextTexts = (el, n) => {
    const out = [];
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    w.currentNode = el;
    // přeskočit text uvnitř el
    let node;
    while ((node = w.nextNode())) {
      if (el.contains(node)) continue;
      const t = node.textContent.replace(/\s+/g, ' ').trim();
      if (t) { out.push(t); if (out.length >= n) break; }
    }
    return out;
  };
  const seen = new Set();
  const out = [];
  for (const el of document.querySelectorAll('body *')) {
    const txt = (el.textContent || '').replace(/\s+/g, ' ').trim();
    if (txt.length > 60) continue;
    const m = txt.match(re);
    if (!m) continue;
    if ([...el.children].some(c => re.test(c.textContent || ''))) continue;
    const [title, maybeLoc] = nextTexts(el, 2);
    if (!title || re.test(title)) continue;
    const start = `${m[3]}-${m[2].padStart(2,'0')}-${m[1].padStart(2,'0')}T${m[4].padStart(2,'0')}:${m[5]}`;
    const key = title + '|' + start;
    if (seen.has(key)) continue;
    seen.add(key);
    let link = el.closest('a[href]');
    if (!link) {
      let p = el;
      for (let i = 0; i < 6 && p; i++, p = p.parentElement) {
        const a = p.querySelector && p.querySelector('a[href*="/akce/"]');
        if (a) { link = a; break; }
      }
    }
    out.push({
      title, start,
      duration: m[6] ? parseInt(m[6]) : null,
      location: (maybeLoc && !/^t[řr][íi]dy/i.test(maybeLoc) && maybeLoc.length < 30) ? maybeLoc : '',
      url: link ? link.href : '',
    });
  }
  return out;
}
"""

JS_STATE = r"""
() => {
  const q = s => document.querySelector(s);
  if (q('[data-testid=samet-signin]')) return {state: 'signin'};
  const content = q('[data-testid=samet-content]');
  if (!content || content.getAttribute('data-state') === 'loading') return {state: 'loading'};
  const duvod = content.getAttribute('data-duvod');
  if (duvod) return {state: duvod};
  const faze = content.getAttribute('data-faze');
  const picker = q('[data-testid=samet-picker]');
  if (!picker) return {state: faze === 'po' ? 'po' : 'nezverejneno', faze};
  const options = [...document.querySelectorAll('[data-testid=samet-option]')].map(o => {
    const blokEl = o.closest('[data-testid^="samet-block-"]');
    const blok = blokEl ? blokEl.getAttribute('data-testid').replace('samet-block-', '') : null;
    const titleEl = o.querySelector('[data-testid=samet-pick] .font-semibold') || o.querySelector('[data-testid=samet-pick] span span');
    const freeTxt = (o.querySelector('[data-testid=samet-free]')?.innerText || '').trim();
    let free = null;
    if (/obsazeno/i.test(freeTxt)) free = 0;
    else { const m = freeTxt.match(/(\d+)/); if (m) free = parseInt(m[1]); }
    return {id: o.getAttribute('data-termin'), blok, title: (titleEl?.innerText || '').trim(), free,
            selected: o.getAttribute('data-selected') === 'true', mine: o.getAttribute('data-selected') === 'true'};
  });
  const pickBtn = q('[data-testid=samet-pick]');
  const locked = /jen k nahl[ée]dnut/i.test(picker.innerText) || faze !== 'otevreno';
  const progress = q('[data-testid=samet-progress]')?.innerText || '';
  const saved = [...document.querySelectorAll('[data-testid=samet-saved-item]')].map(e => e.innerText.replace(/\s+/g, ' ').trim());
  return {state: faze === 'po' ? 'po' : (locked ? 'nahled' : 'otevreno'), faze, options,
          needOdpo: /Odpoledne:/.test(progress), progress, saved};
}
"""

JS_SELECTED = r"""
() => [...document.querySelectorAll('[data-testid=samet-option][data-selected=true]')].map(o => o.getAttribute('data-termin'))
"""

JS_RESULT = r"""
() => {
  const err = document.querySelector('[data-testid=samet-error]');
  const toasts = [...document.querySelectorAll('[data-sonner-toast]')];
  const last = toasts[toasts.length - 1];
  const type = last?.getAttribute('data-type');
  const text = (last?.innerText || '').replace(/\s+/g, ' ').trim();
  return {error: err ? err.innerText.trim() : null,
          toast: type === 'success' ? text : (!type && text ? text : null),
          toastErr: type === 'error' ? text : null};
}
"""

def _head_date(url: str) -> tuple[float, float]:
    t0 = time.time()
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "samet-booker"})
    with urllib.request.urlopen(req, timeout=5) as r:
        date = r.headers.get("Date")
    t1 = time.time()
    if not date:
        raise RuntimeError("Server neposlal čas")
    return (t0 + t1) / 2, email.utils.parsedate_to_datetime(date).timestamp()


def server_offset(url: str) -> float:
    """Vrátí (čas serveru − místní čas) v sekundách.

    Hlavička Date má přesnost jen na sekundy, proto se pár dotazy (cca 15 za 1,5 s)
    trefíme do okamžiku, kdy se na serveru přehoupne sekunda.
    """
    samples = []
    for _ in range(16):
        samples.append(_head_date(url))
        if len(samples) >= 2 and samples[-1][1] > samples[-2][1]:
            (ta, _), (tb, sb) = samples[-2], samples[-1]
            return sb - (ta + tb) / 2
        time.sleep(0.08)
    t, s = samples[-1]
    return s + 0.5 - t


def guess_blocks(raw: list[dict]) -> list[dict]:
    """Přiřadí akcím z Programu blok podle začátku a délky.

    Časy bloků podle gympb.cz/samet: A 8:00, B 9:00, C 10:00, D 11:00 (45 min),
    AB 8:00 a CD 10:00 (dvouhodinovky), ODPO od 12:00.
    """
    if not raw:
        return []
    days = {}
    for e in raw:
        days[e["start"][:10]] = days.get(e["start"][:10], 0) + 1
    day = config.SAMET_DATE if config.SAMET_DATE in days else max(days, key=days.get)
    out = []
    for e in raw:
        if not e["start"].startswith(day):
            continue
        dur = e.get("duration") or 45
        hour = int(e["start"][11:13])
        if hour >= 12:
            blok = "ODPO"
        elif dur > 60:
            blok = "AB" if hour < 10 else "CD"
        else:
            blok = {8: "A", 9: "B", 10: "C", 11: "D"}.get(hour, "A" if hour < 8 else "D")
        out.append({"title": e["title"], "blok": blok, "start": e["start"], "duration": dur,
                    "location": e.get("location", ""), "exact": False})
    return out


def merge_with_school(raw: list[dict]) -> list[dict]:
    """Spojí akce z Programu na rezervačním webu s oficiálním programem školy.

    Název bereme z rezervačního webu (tak ho bude hledat i rezervace), bloky
    z programu školy. Akce, které škola nemá, dostanou blok odhadem podle času.
    """
    school = program2026.EVENTS
    out: list[dict] = []
    used_school = set()
    for e in guess_blocks(raw):
        hit = None
        for idx, (title, bloks, room, cap, note) in enumerate(school):
            if planner.similarity(e["title"], title) >= 0.85:
                hit = idx
                break
        if hit is None:
            out.append(e)
            continue
        if hit in used_school:
            continue
        used_school.add(hit)
        title, bloks, room, cap, note = school[hit]
        for b in bloks:
            out.append({"title": e["title"], "blok": b, "location": e.get("location") or room,
                        "capacity": cap, "note": note, "exact": False, "source": "web+skola"})
    for idx, ev in enumerate(school):
        if idx not in used_school:
            title, bloks, room, cap, note = ev
            out.extend({"title": title, "blok": b, "location": room, "capacity": cap, "note": note,
                        "exact": False, "source": "skola"} for b in bloks)
    return out


class Cancelled(Exception):
    pass


class Bot:
    def __init__(self, log: Callable[[str, str], None], set_status: Callable[..., None]):
        self.log = log
        self.set_status = set_status
        self.pw = None
        self.browser = None
        self.context = None
        self.page: Page | None = None
        self.cancel = threading.Event()
        self.set_base(config.BASE_URL)

    def set_base(self, base_url: str):
        self.base_url = base_url.rstrip("/") + "/"
        self.block_url = self.base_url + "samet"

    # -- připojení ---------------------------------------------------------
    def connect(self):
        if self.browser and self.browser.is_connected():
            return
        self.pw = self.pw or sync_playwright().start()
        self.browser = self.pw.chromium.connect_over_cdp(f"http://127.0.0.1:{config.DEBUG_PORT}")
        self.context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
        self.page = None
        self.log("Připojeno k Chrome.", "ok")

    def site_page(self) -> Page:
        self.connect()
        if self.page and not self.page.is_closed():
            return self.page
        for p in self.context.pages:
            if p.url.startswith(self.base_url):
                self.page = p
                return p
        self.page = self.context.new_page()
        self.page.goto(self.base_url, wait_until="domcontentloaded")
        return self.page

    def open_site(self):
        p = self.site_page()
        p.bring_to_front()
        if not p.url.startswith(self.base_url):
            p.goto(self.base_url, wait_until="domcontentloaded")
        self.log("Web je otevřený v Chromu. Pokud tam nejsi přihlášený, přihlas se školním Google účtem.", "info")

    # -- program -------------------------------------------------------------
    def load_catalog(self) -> list[dict]:
        """Seznam akcí s bloky. Přednostně přímo ze stránky Bloková rezervace,
        jinak z Programu (bloky se pak odhadnou podle času)."""
        p = self.goto_block_page()
        p.bring_to_front()
        st = self.read_state(p)
        if st.get("options"):
            items = [{"title": o["title"], "blok": o["blok"], "free": o["free"], "exact": True} for o in st["options"]]
            self.log(f"Načteno {len(items)} termínů přímo z Blokové rezervace.", "ok")
            return items
        self.log(self.describe(st), "info")
        self.log("Bloky zatím nejsou zveřejněné. Beru akce z Programu a bloky podle oficiálního programu školy.", "info")
        p.goto(self.base_url, wait_until="domcontentloaded")
        p.wait_for_timeout(2500)
        # Program se zobrazuje po částech, rozbalíme ho celý tlačítkem „Zobrazit další akce“.
        more = p.get_by_role("button", name=re.compile(r"zobrazit dal[šs][íi]", re.I))
        clicks = 0
        while clicks < 60:
            try:
                if more.count() == 0 or not more.first.is_visible():
                    break
                more.first.scroll_into_view_if_needed(timeout=3000)
                more.first.click(timeout=3000)
            except Exception:
                break
            clicks += 1
            p.wait_for_timeout(700)
        if clicks:
            self.log(f"Rozbaleno celé Program ({clicks}× „Zobrazit další akce“).", "info")
        last = 0
        for _ in range(15):  # dorolovat, kdyby se program načítal postupně
            p.mouse.wheel(0, 4000)
            p.wait_for_timeout(400)
            h = p.evaluate("document.body.scrollHeight")
            if h == last:
                break
            last = h
        raw = p.evaluate(JS_CATALOG)
        p.evaluate("window.scrollTo(0,0)")
        items = guess_blocks(raw) if "/demo/" in self.base_url else merge_with_school(raw)
        n_web = len({i["title"] for i in items if i.get("source") != "skola"})
        self.log(f"Načteno {n_web} akcí z Programu, doplněno o bloky z programu školy ({len(items)} termínů).",
                 "ok" if items else "warn")
        return items

    # -- bloková rezervace (/samet) ------------------------------------------
    def goto_block_page(self) -> Page:
        p = self.site_page()
        p.goto(self.block_url, wait_until="domcontentloaded")
        return p

    def read_state(self, p: Page, timeout: float = 8.0) -> dict:
        """Počká, až se stránka načte, a vrátí její stav včetně všech nabízených akcí."""
        deadline = time.time() + timeout
        st = {}
        while time.time() < deadline:
            try:
                st = p.evaluate(JS_STATE)
            except Exception:
                st = {"state": "loading"}
            if st.get("state") not in ("loading", None):
                return st
            time.sleep(0.1)
        return st

    def describe(self, st: dict) -> str:
        s = st.get("state")
        return {
            "signin": "Nejsi přihlášený. Přihlas se v Chromu školním Google účtem.",
            "ucet": "Jsi přihlášený jiným než školním účtem. Odhlas se a přihlas školním.",
            "neaktivni": "Školní účet není aktivní (hlásí web).",
            "trida": "Pro tvou třídu se Samet přes tento web nevybírá (hlásí web).",
            "nezverejneno": "Přihlášen. Nabídka programu zatím není zveřejněná.",
            "nahled": "Přihlášen. Nabídka je vidět, ale výběr ještě není otevřený.",
            "po": "Přihlašování už skončilo.",
            "otevreno": "Přihlášen a výběr je OTEVŘENÝ.",
        }.get(s, f"Neznámý stav stránky ({s}).")

    def probe(self, plan: dict, prefer: dict) -> dict:
        """Zkouška: otevře stránku, zjistí stav a co by se vybralo. Nic nekliká."""
        p = self.goto_block_page()
        p.bring_to_front()
        st = self.read_state(p)
        self.log(self.describe(st), "ok" if st.get("state") in ("otevreno", "nahled", "nezverejneno") else "warn")
        opts = st.get("options") or []
        if opts:
            self.log(f"Na stránce je {len(opts)} termínů.", "info")
            picks, notes = planner.best_program(opts, plan, prefer, st.get("needOdpo", False))
            for n in notes:
                self.log(n, "warn")
            if picks:
                self.log("Teď by se vybralo: " + ", ".join(f"{o['blok']}: {o['title']}" for o in picks), "ok")
            else:
                self.log("Z tvých voleb teď nejde složit platný program.", "err")
        return st

    def apply_selection(self, p: Page, picks: list[dict]):
        want = {o["id"] for o in picks}
        # nejdřív zrušit, co je vybrané navíc (jinak by se akce překrývaly)
        for oid in p.evaluate(JS_SELECTED):
            if oid not in want:
                p.locator(f'[data-testid="samet-option"][data-termin="{oid}"] [data-testid="samet-pick"]').click(timeout=3000)
        for o in picks:
            opt = p.locator(f'[data-testid="samet-option"][data-termin="{o["id"]}"]')
            if opt.get_attribute("data-selected", timeout=3000) == "true":
                continue
            opt.locator('[data-testid="samet-pick"]').click(timeout=3000)
            self.log(f"Vybráno {planner.SLOT_NAMES.get(o['blok'], o['blok'])}: {o['title']}", "ok")

    def submit(self, p: Page) -> tuple[bool, str]:
        btn = p.locator('[data-testid="samet-submit"]')
        deadline = time.time() + 3
        while time.time() < deadline and not btn.is_enabled():
            time.sleep(0.05)
        if not btn.is_enabled():
            hint = p.evaluate("() => document.querySelector('[data-testid=samet-progress]')?.parentElement?.innerText || ''")
            return False, "Tlačítko Odeslat je neaktivní: " + " ".join(hint.split())
        btn.click(timeout=3000)
        self.log("Odesláno, čekám na odpověď webu.", "info")
        deadline = time.time() + 20
        while time.time() < deadline:
            r = p.evaluate(JS_RESULT)
            if r.get("error"):
                return False, r["error"]
            if r.get("toast") and re.search(r"ulo[žz]en|beze zm[ěe]ny", r["toast"], re.I):
                return True, r["toast"]
            if r.get("toastErr"):
                return False, r["toastErr"]
            time.sleep(0.1)
        return False, "Web neodpověděl do 20 s."

    def book(self, plan: dict, prefer: dict, dry_run: bool, fill_any: bool = True) -> bool:
        p = self.site_page()
        for attempt in range(1, 5):
            self._check_cancel()
            st = self.read_state(p)
            if st.get("state") != "otevreno":
                self.log(self.describe(st), "err")
                self.screenshot("stav")
                return False
            picks, notes = planner.best_program(st["options"], plan, prefer, st.get("needOdpo", False), fill_any)
            for n in notes:
                self.log(n, "warn")
            if not picks:
                self.log("Nejde složit platný program (vše plné nebo nic nevybráno).", "err")
                self.screenshot("nelze")
                return False
            self.apply_selection(p, picks)
            if dry_run:
                self.log("Režim nanečisto: vybráno, ale neodesílám.", "warn")
                self.screenshot("nanecisto")
                return True
            ok, msg = self.submit(p)
            if ok:
                self.log(f"HOTOVO: {msg}", "ok")
                time.sleep(1.0)
                self.screenshot("ulozeno")
                return True
            self.log(f"Uložení neprošlo: {msg}", "err")
            if attempt < 4:
                self.log("Načítám aktuální obsazenost a zkouším znovu s náhradníky.", "warn")
                time.sleep(0.8)
                p = self.goto_block_page()
        self.screenshot("neulozeno")
        return False

    def screenshot(self, name: str):
        try:
            path = config.logs_dir() / f"{datetime.now():%Y%m%d-%H%M%S}-{name}.png"
            self.site_page().screenshot(path=str(path), full_page=True)
            self.log(f"Snímek: {path}", "info")
        except Exception as e:
            self.log(f"Snímek se nepodařil: {e}", "warn")

    def _check_cancel(self):
        if self.cancel.is_set():
            raise Cancelled()

    def _sleep_until(self, t: float):
        while True:
            self._check_cancel()
            left = t - time.time()
            if left <= 0:
                return
            time.sleep(min(0.25, left))

    # -- čekání na otevření -------------------------------------------------
    def run_at(self, open_at: datetime, plan: dict, prefer: dict, dry_run: bool, fill_any: bool = True):
        self.cancel.clear()
        try:
            off = server_offset(self.block_url)
            self.log(f"Hodiny tvého PC se od serveru liší o {off:+.2f} s, počítám s tím.", "info")
        except Exception as e:
            off = 0.0
            self.log(f"Čas serveru nezjištěn ({e}), použiju čas PC.", "warn")
        target = open_at.timestamp() - off
        self.set_status(phase="armed", target=target + off)
        self.log(f"Čekám na {open_at:%d. %m. %Y %H:%M:%S}.", "info")

        # Kontrola přihlášení s předstihem (jen jedno načtení stránky).
        self._sleep_until(target - 90)
        try:
            p = self.goto_block_page()
            p.bring_to_front()
            st = self.read_state(p)
            self.log("Kontrola 90 s předem: " + self.describe(st), "ok" if st.get("state") not in ("signin", "ucet") else "err")
        except Exception as e:
            self.log(f"Kontrola předem selhala: {e}", "warn")

        # Načtení s předstihem, ať je vše v mezipaměti.
        self._sleep_until(target - 15)
        try:
            p = self.goto_block_page()
        except Exception as e:
            self.log(f"Předběžné načtení selhalo: {e}", "warn")
            p = self.site_page()

        # Web si stav sám obnovuje jen jednou za 90 s, proto v čas otevření stránku načteme znovu.
        self.set_status(phase="watching")
        # Obnovování kolem času otevření: 2× těsně před (kdyby škola otevřela o chvilku dřív),
        # v čas otevření, pak prvních 5 s zhruba každých 0,75 s, do 30 s každé 2 s a do 3 min každých 5 s.
        schedule = ([-2.0, -0.7, 0.05] + [0.05 + 0.75 * k for k in range(1, 7)]
                    + [4.5 + 2 * k for k in range(1, 13)] + [30 + 5 * k for k in range(1, 31)])
        for k, delay in enumerate(schedule):
            self._sleep_until(target + delay)
            try:
                p.reload(wait_until="domcontentloaded", timeout=15000)
            except Exception as e:
                self.log(f"Načtení stránky selhalo ({e.__class__.__name__}), zkusím znovu.", "warn")
                continue
            st = self.read_state(p)
            if st.get("state") == "otevreno" and st.get("options"):
                self.log(f"Otevřeno! (načtení č. {k + 1}, {time.time() - target:+.2f} s)", "ok")
                self.set_status(phase="booking")
                return self.book(plan, prefer, dry_run, fill_any)
            if st.get("state") in ("signin", "ucet", "po", "trida", "neaktivni"):
                self.log(self.describe(st), "err")
                self.screenshot("stav")
                return False
        self.log("Výběr se do 3 minut neotevřel, končím. Zkus to ručně.", "err")
        self.screenshot("neotevreno")
        return False
