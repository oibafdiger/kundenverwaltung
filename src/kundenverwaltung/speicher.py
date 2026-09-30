"""Wie eine Kundenliste auf die Platte kommt — und wieder herunter.

Herausgeloest aus Kundenliste (Woche 12, Dienstag). Der Aenderungsgrund ist
ein anderer: Ob gespeichert wird und wohin, hat nichts damit zu tun, wie man
ueber Kunden iteriert oder einen Kunden findet. Dieselbe Trennung, die Woche 8
schon fuer CSV gemacht hat (siehe csv_format.py) — nur fuer JSON.

WICHTIG FUER DIE IMPORT-RICHTUNG (Woche 11, Dienstag)
    speicher importiert kundenliste. Umgekehrt NICHT — sonst gibt es einen
    Kreis. Deshalb muessen speichern() und laden() aus Kundenliste wirklich
    verschwinden und nicht als Weiterleitung stehenbleiben.

    dateien  <-  speicher  <-  persistenz
                    |
                    v
               kundenliste  <-  kunde
"""

import json
from abc import ABC, abstractmethod
from typing import Any, NamedTuple

from .dateien import json_atomar_schreiben
from .exceptions import (
    DateiInhaltError,
    DateiNichtGefundenError,
    DateiNichtLesbarError,
)
from .kunde import Kunde
from .kundenliste import Kundenliste
from .notizen import NotizSpeicher

# WAS HIER BEWUSST NICHT LIEGT (Entscheidung 29.09.2026)
#   als_dict(), aus_dict() und die Formatversion bleiben vorerst in
#   Kundenliste; diese Klasse RUFT sie nur auf. Dass der
#   {"version": ...}-Umschlag eigentlich Wissen ueber die DATEI ist und
#   damit hierher gehoerte, steht als P2b in REFACTORING.md. Verschoben
#   auf Mittwoch, weil die Frage mit dem abstrakten Vertrag daneben
#   leichter zu beantworten ist als mitten im Umzug.


class JSONSpeicher:
    def __init__(self, pfad: str) -> None:
        self.pfad = pfad

    def laden(self) -> Kundenliste:
        """Liest eine JSON-Datei und baut die Liste daraus.
        
        Die Reihenfolge der except-Zweige ist nicht beliebig:
        FileNotFoundError ist eine UNTERKLASSE von OSError. Stuende OSError
        zuerst, faenge es auch die fehlende Datei, und der eigene Zweig waere
        toter Code — Python probiert die Zweige von oben nach unten und nimmt
        den ersten, der passt. Spezielles vor Allgemeinem.
        
        json.JSONDecodeError steht ausserhalb dieser Familie (es erbt von
        ValueError), seine Position ist deshalb gleichgueltig.
        
        aus_dict() steht mit Absicht NACH dem try-Block statt darin. Die
        Fachfehler, die es wirft, sind bereits die richtigen; lieferen sie
        durch den except-Filter, wuerde ein Strukturfehler als
        "JSON kaputt" gemeldet. Dieselbe Ueberlegung wie beim else-Block in
        KundenCsv.aus_datei().
        """
        try:
            with open(self.pfad, encoding="utf-8") as datei:
                rohdaten = json.load(datei)
        except FileNotFoundError as e:
            raise DateiNichtGefundenError(f"Datei existiert nicht: {self.pfad!r}") from e
        except OSError as e:
            raise DateiNichtLesbarError(f"Datei nicht lesbar: {self.pfad!r}") from e
        except json.JSONDecodeError as e:
            raise DateiInhaltError(
                f"Datei {self.pfad!r} enthaelt kein gueltiges JSON "
                f"(Zeile {e.lineno}, Spalte {e.colno}): {e.msg}"
            ) from e
        
        return Kundenliste.aus_dict(rohdaten)


    def speichern(self, kunden: Kundenliste) -> None:
        """Schreibt die Liste als JSON-Datei — atomar (Donnerstag).
        
        Die Fassung von Dienstag oeffnete den Zielpfad direkt mit "w" und
        machte ihn damit sofort leer. Ein Abbruch mitten im Schreiben — und
        dafuer genuegt ein Serialisierungsfehler — kostete den alten Stand.
        Die ganze Buchfuehrung dafuer steckt jetzt in
        json_atomar_schreiben(); hier bleibt nur noch, WAS geschrieben wird.
        
        Nebenbei entfaellt eine Verdopplung: NotizSpeicher.speichern() hatte
        denselben Rumpf. Die Fehleruebersetzung liegt jetzt an einer Stelle
        statt an zweien.
        """
        json_atomar_schreiben(self.pfad, kunden.als_dict())



class JSONNotizSpeicher:
    """Ein NotizSpeicher <-> eine JSON-Datei. Das Gegenstueck zu JSONSpeicher.

    Herausgeloest aus NotizSpeicher (Woche 12, Mittwoch — P3 in
    REFACTORING.md). Derselbe Fund wie bei Kundenliste am Dienstag, nur an
    einer zweiten Stelle: Notizen zu halten und zu verteilen ist ein anderer
    Aenderungsgrund als zu wissen, wie sie auf die Platte kommen.

    Dass die Fehlermeldungen "Notizdatei" statt "Datei" sagen, ist der einzige
    Unterschied zu JSONSpeicher — er hilft beim Lesen eines Tracebacks, weil
    KundenDatei zwei Dateien anfasst.
    """

    def __init__(self, pfad: str) -> None:
        self.pfad = pfad

    def __repr__(self) -> str:
        return f"JSONNotizSpeicher({self.pfad!r})"

    def laden(self) -> NotizSpeicher:
        try:
            with open(self.pfad, encoding="utf-8") as datei:
                rohdaten = json.load(datei)
        except FileNotFoundError as e:
            raise DateiNichtGefundenError(
                f"Notizdatei existiert nicht: {self.pfad!r}"
            ) from e
        except OSError as e:
            raise DateiNichtLesbarError(
                f"Notizdatei nicht lesbar: {self.pfad!r}"
            ) from e
        except json.JSONDecodeError as e:
            raise DateiInhaltError(
                f"Notizdatei {self.pfad!r} enthaelt kein gueltiges JSON "
                f"(Zeile {e.lineno}, Spalte {e.colno}): {e.msg}"
            ) from e

        return NotizSpeicher.aus_dict(rohdaten)

    def speichern(self, notizen: NotizSpeicher) -> None:
        json_atomar_schreiben(self.pfad, notizen.als_dict())

# ============================================================================
# Der Speicher-Vertrag (Woche 12, Mittwoch)
# Aufgabe: die Abhaengigkeit umdrehen — der Aufrufer bringt den Speicher mit
# ============================================================================
class Geladen(NamedTuple):
    """Was Speicher.laden() zurueckgibt: drei Werte mit Namen (Woche 10).

    Vorher ein nacktes Tupel, tuple[Kundenliste, NotizSpeicher, list[int]].
    Wer das Ergebnis benutzte, musste sich die REIHENFOLGE merken. Jetzt
    heissen die Teile kunden, speicher und waisen.

    Warum NamedTuple und nicht dict oder dataclass?

    - dict: Ein Tippfehler beim Setzen legt still einen neuen Schluessel an,
      beim Lesen gibt es erst zur Laufzeit einen KeyError, und mypy sieht
      beides nicht. Ein dict passt, wenn die Schluessel vorher nicht
      feststehen — hier stehen sie fest.
    - dataclass: ginge auch. NamedTuple bleibt aber ein Tupel: Der bestehende
      Code `kunden, speicher, waisen = speicher.laden()` laeuft unveraendert
      weiter. Und ein Ergebnis soll man nicht nachtraeglich aendern — ein
      NamedTuple ist von Haus aus unveraenderlich.

    Seit Woche 12 in speicher.py statt persistenz.py: Es ist der Rueckgabetyp
    des Vertrags und gehoert deshalb zum Vertrag.
    """

    kunden: Kundenliste
    speicher: NotizSpeicher
    waisen: list[int]


class Speicher(ABC):
    """Woher die Daten kommen und wohin sie gehen — als Vertrag statt als Code.

    WORUM ES GEHT (Abhaengigkeitsumkehr)
        Vorher erzeugte KundenDatei ihren Speicher selbst: Sie bekam einen
        Pfad und wusste, dass daraus JSON-Dateien werden. Damit hing die obere
        Schicht an der unteren — wer den Speicher tauschen wollte, musste
        KundenDatei anfassen.

        Jetzt bekommt KundenDatei ein fertiges Speicher-Objekt und weiss
        nicht, was darin steckt. Beide haengen nur noch an DIESEM Vertrag.
        Das ist das D in SOLID: Dependency Inversion.

    WARUM DER VERTRAG BEIDES UMFASST — Kunden UND Notizen
        Weil beides zusammen eine Einheit ist, die vollstaendig oder gar nicht
        geschrieben werden soll. Waeren es zwei Vertraege, muesste jemand
        anderes ihre Reihenfolge koordinieren — und genau diese Koordination
        (erst Notizen, dann Kunden, Waisen nicht verlieren) ist der heikle
        Teil. Sie gehoert in die Implementierung, die weiss, ob sie das
        ueberhaupt atomar kann.

        Konkret: DateiSpeicher kann es NICHT (zwei Dateien, zwei
        os.replace()), InMemorySpeicher braucht es nicht, und ein
        SQLiteSpeicher koennte es mit einer Transaktion wirklich. Derselbe
        Vertrag, drei verschiedene Garantien — und der Aufrufer waehlt aus,
        welche er braucht.

    KEIN PFAD IM VERTRAG
        laden() nimmt nichts entgegen. Ein Pfad waere ein Parameter, den
        InMemorySpeicher nur ignorieren koennte — ein Vertrag, der fuer eine
        seiner Implementierungen nicht stimmt. Jede bringt im Konstruktor mit,
        was sie braucht.
    """

    @abstractmethod
    def laden(self) -> Geladen:
        """Den ganzen Bestand holen: Kunden, Notizen und die Waisen-Nummern.

        Ein leerer Speicher ist KEIN Fehler — beim ersten Start gibt es noch
        nichts, und das Ergebnis ist eine leere Kundenliste. Ein DEFEKTER
        Speicher ist sehr wohl einer und wirft: Eine kaputte Datei still durch
        eine leere zu ersetzen hiesse, sie beim naechsten Speichern zu
        ueberschreiben.
        """

    @abstractmethod
    def speichern(
        self, kunden: Kundenliste, notizen: NotizSpeicher, waisen: list[int]
    ) -> None:
        """Den Bestand ablegen.

        `notizen` ist der GELADENE Speicher, nicht der neue — aus ihm werden
        die Notizen der Waisen wieder uebernommen. Waisen sind Notizen ohne
        Kunden; sie haengen an niemandem und waeren sonst beim naechsten
        Speichern verloren (Review-Fix 15.09.2026).
        """


def _zusammenfuegen(kunden: Kundenliste, notizen: NotizSpeicher) -> Geladen:
    """Notizen an die Kunden haengen, Waisen melden, Nummernzaehler nachziehen.

    Der Teil, der fuer JEDEN Speicher gleich ist — er haengt nur an den
    Objekten, nicht am Medium. Deshalb hier als Funktion und nicht doppelt in
    DateiSpeicher und InMemorySpeicher.

    Eine Nummer, zu der noch Notizen existieren, ist nicht frei (Review-Fix
    15.09.2026). Bekaeme ein neuer Kunde die Nummer einer Waise, haengten ihre
    Notizen beim naechsten Laden an ihm — an der falschen Person.
    """
    waisen = notizen.auf_kunden_verteilen(kunden)
    if waisen:
        Kunde.naechste_nummer = max(Kunde.naechste_nummer, max(waisen) + 1)
    return Geladen(kunden, notizen, waisen)


def _notizen_zusammenstellen(
    kunden: Kundenliste, geladen: NotizSpeicher, waisen: list[int]
) -> NotizSpeicher:
    """Der Notizspeicher, der geschrieben werden soll — Waisen inbegriffen.

    von_kunden() sammelt nur ein, was an Kunden haengt. Die Waisen haengen an
    niemandem und muessen aus dem geladenen Speicher zurueckgeholt werden.
    Gemeldet ist nicht aufbewahrt — erst beides zusammen ist richtig.
    """
    neu = NotizSpeicher.von_kunden(kunden)
    neu.waisen_uebernehmen(geladen, waisen)
    return neu


class DateiSpeicher(Speicher):
    """Der Bestand in zwei JSON-Dateien — der Weg, den es seit Woche 9 gibt.

        with KundenDatei(DateiSpeicher("kunden.json")) as kunden:
            ...

    Die Notizdatei wird aus dem Kundenpfad abgeleitet (kunden.json ->
    kunden.notizen.json). Sie getrennt angeben zu muessen waere eine
    Fehlerquelle ohne Gegenwert; wer es braucht, kann sie trotzdem nennen.

    WAS DIESE IMPLEMENTIERUNG NICHT KANN
        Die beiden Dateien werden JE FUER SICH unteilbar ersetzt
        (json_atomar_schreiben, Woche 9 Donnerstag). Dass beide ZUSAMMEN
        passen, folgt daraus nicht: Zwischen den zwei os.replace() liegt ein
        Moment, in dem die Notizdatei schon neu und die Kundendatei noch alt
        ist. Deshalb die Reihenfolge unten — sie macht den Schaden klein, sie
        verhindert ihn nicht.

        Das ist keine Schwaeche des Vertrags, sondern eine dieser
        Implementierung. Ein SQLiteSpeicher haette an derselben Stelle eine
        Transaktion und damit die Garantie, die hier fehlt.
    """

    def __init__(self, kunden_pfad: str, notiz_pfad: str | None = None) -> None:
        self.kunden_pfad = kunden_pfad
        self.notiz_pfad = self._notizpfad_ableiten(kunden_pfad, notiz_pfad)

    @staticmethod
    def _notizpfad_ableiten(kunden_pfad: str, notiz_pfad: str | None) -> str:
        """kunden.json -> kunden.notizen.json, falls kein eigener Pfad kommt."""
        if notiz_pfad is not None:
            return notiz_pfad
        stamm = kunden_pfad[:-5] if kunden_pfad.endswith(".json") else kunden_pfad
        return f"{stamm}.notizen.json"

    def __repr__(self) -> str:
        return f"DateiSpeicher({self.kunden_pfad!r})"

    def laden(self) -> Geladen:
        """Fehlende Datei = erster Programmstart = leer anfangen.

        Alle anderen Dateifehler fliegen weiter. Eine kaputte Datei darf nicht
        still durch eine leere ersetzt werden, sonst ueberschreibt das
        naechste Speichern echte Daten.
        """
        try:
            kunden = JSONSpeicher(self.kunden_pfad).laden()
        except DateiNichtGefundenError:
            kunden = Kundenliste()

        try:
            notizen = JSONNotizSpeicher(self.notiz_pfad).laden()
        except DateiNichtGefundenError:
            notizen = NotizSpeicher()

        return _zusammenfuegen(kunden, notizen)

    def speichern(
        self, kunden: Kundenliste, notizen: NotizSpeicher, waisen: list[int]
    ) -> None:
        """REIHENFOLGE MIT ABSICHT: erst die Notizen, dann die Kunden.

        Scheitert das Schreiben der Notizen, ist noch gar nichts geschrieben —
        beide Dateien stehen konsistent auf dem alten Stand. Scheitert es
        danach bei den Kunden, verweisen neue Notizen auf Kunden, die in der
        alten Kundendatei fehlen: Beim naechsten Laden tauchen sie als Waisen
        auf und bleiben erhalten. Umgekehrt (Kunden zuerst) fehlten einfach
        Notizen, und das fiele niemandem auf.
        """
        neu = _notizen_zusammenstellen(kunden, notizen, waisen)
        JSONNotizSpeicher(self.notiz_pfad).speichern(neu)
        JSONSpeicher(self.kunden_pfad).speichern(kunden)


class InMemorySpeicher(Speicher):
    """Derselbe Bestand im Arbeitsspeicher — fuer Tests.

        with KundenDatei(InMemorySpeicher()) as kunden:
            ...

    WARUM DICTS UND NICHT OBJEKTE
        Naheliegend waere, die Kundenliste einfach als Attribut zu halten.
        Dann waere dieser Speicher aber SCHNELLER ALS ECHT: Der Aufrufer
        bekaeme dieselben Objekte zurueck, die er hineingegeben hat, und ein
        Test wuerde Fehler nicht mehr finden, die eine Datei sehr wohl
        aufdeckt — ein Feld, das gar nicht serialisiert wird, ein Zustand, der
        den Round-Trip nicht ueberlebt, ein negativer Umsatz, den erst
        aus_dict() zurueckweist.

        Deshalb legt diese Klasse das ab, was auch in der Datei staende: das
        dict. Beim Laden wird daraus neu gebaut, mit allen Pruefungen. Es
        entfaellt genau eine Sache — das Dateisystem.

        Die Regel dahinter: Ein Test-Double darf schneller sein als das Echte,
        aber nicht nachsichtiger.

    WAS DAMIT WEGFAELLT
        Keine tempfile-Ordner, kein Aufraeumen, keine Reihenfolgeprobleme
        zwischen zwei Dateien. Und jeder Test bekommt seinen eigenen Speicher
        — zwei Tests koennen sich nicht mehr ueber eine liegengebliebene Datei
        in die Quere kommen.
    """

    def __init__(self) -> None:
        # None heisst "noch nie geschrieben" — das Gegenstueck zur fehlenden
        # Datei. Ein leeres dict waere etwas anderes: eine leere, aber
        # vorhandene Datei.
        self._kunden_daten: dict[str, Any] | None = None
        self._notiz_daten: dict[str, Any] | None = None

    def __repr__(self) -> str:
        stand = "leer" if self._kunden_daten is None else "beschrieben"
        return f"InMemorySpeicher({stand})"

    def laden(self) -> Geladen:
        kunden = (
            Kundenliste()
            if self._kunden_daten is None
            else Kundenliste.aus_dict(self._kunden_daten)
        )
        notizen = (
            NotizSpeicher()
            if self._notiz_daten is None
            else NotizSpeicher.aus_dict(self._notiz_daten)
        )
        return _zusammenfuegen(kunden, notizen)

    def speichern(
        self, kunden: Kundenliste, notizen: NotizSpeicher, waisen: list[int]
    ) -> None:
        neu = _notizen_zusammenstellen(kunden, notizen, waisen)
        # Erst beide dicts bauen, dann beide zuweisen: Wirft als_dict() bei
        # einem der beiden, bleibt der alte Stand vollstaendig stehen. Das ist
        # dasselbe Versprechen, das json_atomar_schreiben() fuer eine Datei
        # gibt — hier sogar fuer beide zusammen, weil eine Zuweisung nicht
        # scheitern kann. InMemorySpeicher ist damit atomarer als
        # DateiSpeicher, und das ist kein Zufall: Fehlende Ein-/Ausgabe ist
        # die einfachste Art, konsistent zu bleiben.
        notiz_daten = neu.als_dict()
        kunden_daten = kunden.als_dict()
        self._notiz_daten = notiz_daten
        self._kunden_daten = kunden_daten
