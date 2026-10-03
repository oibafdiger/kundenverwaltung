"""Dateien so ersetzen, dass es keinen Zwischenzustand gibt.

Die unterste Schicht der Persistenz: kennt weder Kunden noch Notizen,
nur JSON und das Dateisystem. Steht deshalb in einem eigenen Modul —
sonst muesste kundenliste von persistenz importieren und persistenz
von kundenliste, und das waere ein Importzyklus."""

import json
import os
import tempfile
from typing import Any

from .exceptions import DateiNichtLesbarError


# ============================================================================
# Atomares Schreiben (Woche 9, Donnerstag)
# Aufgabe: eine Datei so ersetzen, dass es keinen Zwischenzustand gibt
# ============================================================================
def json_atomar_schreiben(pfad: str, daten: dict[str, Any]) -> None:
    """Schreibt JSON so, dass die Zieldatei nie halbfertig existiert.

    Das Muster: temporaere Datei im SELBEN Verzeichnis, vollstaendig
    schreiben, fsync, dann os.replace(). Umgehaengt wird der
    Verzeichniseintrag, nicht der Inhalt geaendert — deshalb sieht ein Leser
    nie einen Zwischenstand.

    Warum ueberhaupt: `open(pfad, "w")` leert die Datei sofort, bevor ein
    Byte des neuen Inhalts geschrieben ist. Es braucht keinen Stromausfall,
    damit das teuer wird — ein nicht serialisierbares Objekt mitten im
    Bestand genuegt, weil json.dump fortlaufend schreibt.

    WAS DIESE FASSUNG NICHT LEISTET
        Streng genommen muesste auch das VERZEICHNIS gefsynct werden, damit
        der neue Verzeichniseintrag selbst einen Stromausfall ueberlebt. Das
        ist plattformabhaengig und fuer ein Lernprojekt uebertrieben — hier
        bewusst weggelassen und benannt.

        Und die Atomaritaet gilt je Datei. KundenDatei schreibt zwei; dass
        beide zusammenpassen, garantiert auch os.replace() nicht.
    """
    ordner = os.path.dirname(os.path.abspath(pfad))
    temp_pfad: str | None = None
    try:
        # delete=False, weil die Datei den with-Block ueberleben muss — sie
        # wird ja gleich umgehaengt statt geloescht.
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=ordner,
            prefix=".tmp_", suffix=".json", delete=False,
        ) as temp_datei:
            temp_pfad = temp_datei.name
            json.dump(daten, temp_datei, ensure_ascii=False, indent=2)
            temp_datei.flush()      # Pythons Puffer ins Betriebssystem
            os.fsync(temp_datei.fileno())   # und von dort auf die Platte

        # Zugriffsrechte der alten Datei uebernehmen. Ohne das behielte die
        # neue die 0600 der temporaeren — eine Rechteaenderung, die niemand
        # angeordnet hat und die erst auffaellt, wenn ein anderer die Datei
        # braucht.
        if os.path.exists(pfad):
            os.chmod(temp_pfad, os.stat(pfad).st_mode & 0o777)

        os.replace(temp_pfad, pfad)
        temp_pfad = None            # ab hier gibt es nichts mehr aufzuraeumen
    except OSError as e:
        raise DateiNichtLesbarError(f"Datei nicht beschreibbar: {pfad!r}") from e
    finally:
        # Ist etwas schiefgegangen, liegt die temporaere Datei noch herum.
        # Dieselbe Buchfuehrung wie beim finally in KundenCsv.aus_datei —
        # nur nimmt sie einem `with` hier nicht ab, weil die Datei den Block
        # ja absichtlich ueberlebt.
        if temp_pfad is not None:
            try:
                os.remove(temp_pfad)
            except OSError:
                pass    # Aufraeumen darf den eigentlichen Fehler nicht ersetzen
