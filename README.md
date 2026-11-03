# SAMET Booker

Aplikace, která tě v čas otevření přihlásí na program **Sametového festivalu 2026** na [rezervace.gympb.cz](https://rezervace.gympb.cz/) (záložka **Bloková rezervace**).

Vybereš si akce předem, u každé hodiny i náhradníka, a appka přesně v čas otevření (3. 11. 2026 v 19:00) načte stránku, poskládá platný program z toho, co je volné, a odešle ho. Celé to trvá zhruba sekundu.

## Jak to funguje

- Appka otevře **vlastní okno Google Chrome** (s vlastním profilem). V něm se jednou přihlásíš **školním Google účtem**. Heslo appka nikdy nevidí ani neukládá.
- Vedle se otevře ovládací panel, kde vybíráš akce.
- Web chce celé dopoledne: 1.–4. hodinu buď po hodinách (A, B, C, D), nebo jako dvouhodinovky (AB, CD), plus jednu odpolední akci. Appka hlídá, aby výsledný program byl platný.
- Když je tvoje 1. volba plná, použije náhradníka. Když nevyjde ani ten, zkusí dvouhodinovku (nebo naopak) a nakonec, pokud chceš, cokoli volného.
- Když web při odeslání ohlásí, že se něco mezitím zaplnilo, appka načte aktuální obsazenost a zkusí to znovu (nejvýš 4×).

## Pravidla Samet 2026 (podle [gympb.cz/samet](https://gympb.cz/samet/#prihlasovani))

- Přihlašování: **od 3. 11. 19:00 do 6. 11. 16:00** na rezervace.gympb.cz.
- Bloky: A 8:00, B 9:00, C 10:00, D 11:00 (po 45 min), dvouhodinovky AB 8:00–9:30 a CD 10:00–11:30, odpoledne ODPO 12:00–14:00 (jen vyšší gymnázium, vybírá se jeden workshop).
- Dopoledne musí být pokryté: A+B+C+D, AB+C+D, A+B+CD nebo AB+CD. Stejnou akci nejde mít dvakrát.
- Některé akce jsou jen pro němčináře nebo vyšší gymnázium, film Dalajlama stojí 80 Kč (strhne se z Bakalářů). Appka to u akcí ukazuje.

Dokud web nezveřejní nabídku přímo v Blokové rezervaci, appka bere akce z Programu a bloky podle oficiálního programu školy (`samet_booker/program2026.py`). Jakmile nabídka na webu je, načte se odtamtud přesně.

## Instalace (Windows)

**Možnost A, bez instalace Pythonu:** stáhni `SAMET-Booker.exe` ze stránky [Releases](../../releases) a spusť ho. Windows může ukázat varování SmartScreen („Neznámý vydavatel“), klikni na *Další informace → Přesto spustit*.

**Možnost B, z kódu:**

1. Nainstaluj [Python 3.11+](https://www.python.org/downloads/) (při instalaci zaškrtni *Add python.exe to PATH*).
2. Stáhni repozitář (zelené tlačítko *Code → Download ZIP*) a rozbal ho.
3. Dvojklikem spusť `spustit.bat`. Poprvé si stáhne knihovnu Playwright, pak už startuje hned.

Potřebuješ nainstalovaný **Google Chrome** (nebo Microsoft Edge).

## Použití

1. Spusť appku. Otevře se okno Chromu s webem a malé okno s ovládacím panelem.
2. V okně s webem se přihlas školním Google účtem (stačí jednou, Chrome si to pamatuje).
3. V panelu klikni na **Načíst nabídku z webu** a vyber akce: u každé hodiny 1. volbu a náhradníka, u dvouhodinovek zálohu, a odpolední akci.
4. Klikni na **Zkontrolovat stránku**. V záznamu uvidíš, jestli jsi přihlášený a co appka na stránce vidí.
5. Klikni na **Spustit odpočet** a nech počítač zapnutý (nevypínat, neuspávat, Chrome nezavírat).

### Zkouška nanečisto

Dole v panelu je **demo stránka**, která vypadá a funguje jako Bloková rezervace, ale běží jen u tebe v počítači. Zapni *Používat zkušební demo stránku*, klikni na *Načíst nabídku z webu*, vyber akce a dej **Demo: otevřít za 1 minutu a spustit**. Akce „Berlínská zeď“ v 1. hodině se v demu schválně hned zaplní, takže uvidíš i náhradníka. Před ostrým během demo zase vypni.

Volba **Jen nanečisto** na ostrém webu akce vybere, ale neodešle.

## Ohleduplnost

Appka je navržená tak, aby se chovala jako rychlý člověk, ne jako útok:

- kolem času otevření stránku obnovuje: 2 s a 0,7 s před, přesně v čas otevření, prvních 5 s zhruba každých 0,75 s, pak každé 2 s a od 30. sekundy každých 5 s, nejdéle 3 minuty. Jakmile je otevřeno, přestane obnovovat a hned rezervuje,
- program odešle jedním kliknutím, opakuje jen když web ohlásí chybu,
- rezervuje jen pro účet, který je v Chromu přihlášený.

Škola nemusí mít automatické přihlašování ráda. Používáš ji na vlastní zodpovědnost.

## Kde jsou data

`%LOCALAPPDATA%\samet-booker\`: nastavení (`settings.json`), profil Chromu a složka `logs` se záznamem (`log.txt`) a snímky obrazovky z průběhu.

## Pro vývojáře

- `samet_booker/bot.py`: práce se stránkou (Playwright připojený k Chromu přes CDP)
- `samet_booker/planner.py`: výběr nejlepšího platného programu
- `samet_booker/demo.py`, `web/demo_*.html`: zkušební stránka
- `web/index.html`: ovládací panel
- Exe se staví GitHub Actions při vydání nové verze (Release) a přiloží se k ní. Ručně jde spustit v záložce Actions.
