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

    DAS PROBLEM
        `open(pfad, "w")` leert die Datei SOFORT — bevor auch nur ein Byte des
        neuen Inhalts geschrieben ist. Bricht das Schreiben danach ab, ist der
        alte Stand weg und der neue unvollstaendig:

            vorher : {"version": 1, "kunden": ["ALTER STAND, wertvoll"]}
            Fehler : Object of type object is not JSON serializable
            nachher: '{"version": 1, "kunden": [{"a": 1}, {"b": 2}, {"c": '

        Es braucht dafuer keinen Stromausfall. Ein Serialisierungsfehler
        mitten im Datenbestand genuegt, weil json.dump fortlaufend schreibt.

    DIE LOESUNG
        Nicht in die Zieldatei schreiben, sondern daneben — und erst wenn
        alles vollstaendig auf der Platte steht, den Namen umhaengen:

            1. temporaere Datei im SELBEN Verzeichnis anlegen
            2. vollstaendig hineinschreiben
            3. os.replace(temp, pfad)

    WARUM DAS ATOMAR IST
        os.replace() haengt einen VERZEICHNISEINTRAG um. Das Dateisystem
        fuehrt diese Operation als Ganzes aus oder gar nicht — es gibt keinen
        Zeitpunkt, zu dem ein Leser eine halbe Umbenennung saehe. Wer die
        Datei oeffnet, bekommt entweder vollstaendig den alten oder
        vollstaendig den neuen Inhalt.

        Der Inhalt wird also nie geaendert. Geaendert wird, WELCHER Inhalt
        unter diesem Namen zu finden ist. Das ist der ganze Trick.

    DREI BEDINGUNGEN, DIE LEICHT UEBERSEHEN WERDEN
        1. Dasselbe Dateisystem. Die Garantie gilt nur innerhalb eines
           Dateisystems — daher `dir=ordner` und nicht /tmp. Ueber Grenzen
           hinweg muesste kopiert werden, und Kopieren ist wieder ein
           Vorgang mit Zwischenzustand.

        2. os.replace(), nicht os.rename(). Unter Windows scheitert rename(),
           wenn das Ziel existiert — und genau das ist hier der Normalfall.
           os.replace() ueberschreibt auf allen Plattformen.

        3. Atomar ist nicht dasselbe wie dauerhaft. Nach dem Schreiben liegen
           die Daten womoeglich noch im Zwischenspeicher des Betriebssystems.
           Ein Stromausfall koennte sie verlieren, obwohl das Programm
           laengst weiter ist. os.fsync() erzwingt das Schreiben auf die
           Platte, BEVOR umgehaengt wird. Ohne fsync waere die Umbenennung
           zwar unteilbar, koennte aber auf einen leeren Inhalt zeigen.

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

        # Zugriffsrechte der alten Datei uebernehmen. Ohne das behaelt die
        # neue Datei die 0600 der temporaeren — sie waere nach dem ersten
        # Speichern nur noch fuer den Eigentuemer lesbar. Eine Aenderung,
        # die niemand angeordnet hat und die erst auffaellt, wenn jemand
        # anderes die Datei braucht.
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
