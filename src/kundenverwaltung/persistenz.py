"""Was ueber eine einzelne Kundenliste hinausgeht: Notizen und die
Klammer um beides.

NotizSpeicher haelt die Notizen in einer EIGENEN Datei — eine Notiz
sagt nichts darueber aus, wer ein Kunde ist, sie haengt an ihm. Das
Kriterium dafuer ist die Registry aus komponenten: Was dort eingetragen
ist, gehoert zum Kunden; was nicht (Notiz), ist ein Anhang.

KundenDatei klammert Laden und Speichern beider Dateien um einen
Arbeitsblock — transaktional: Fliegt im Block eine Exception, wird
nichts geschrieben.

kunden_datei ist dieselbe Klammer als Generator mit @contextmanager.
Beide Varianten benutzen dieselben Hilfsfunktionen und unterscheiden
sich nur in der Verpackung."""

import json
from collections.abc import Generator
from contextlib import contextmanager
from types import TracebackType
from typing import Any, Literal, NamedTuple

from .dateien import json_atomar_schreiben
from .exceptions import (
    DateiInhaltError,
    DateiNichtGefundenError,
    DateiNichtLesbarError,
    KundenverwaltungError,
)
from .komponenten import Notiz
from .kunde import Kunde
from .kundenliste import Kundenliste


# ============================================================================
# Notizspeicher (Woche 9, Dienstag)
# Aufgabe: Notizen aufbewahren, getrennt von den Kunden
# ============================================================================
class NotizSpeicher:
    """Notizen zu Kunden, in einer eigenen Datei.

    WARUM GETRENNT
        Eine Notiz sagt nichts darueber aus, WER ein Kunde ist — sie haengt
        an ihm. Technisch sichtbar wird das an der Registry: Die drei
        Fachkomponenten sind dort eingetragen, Notiz ist es bewusst nicht
        (Duck Typing, Woche 5). Dieses Kriterium entscheidet seit Woche 9,
        wo etwas gespeichert wird.

        In der Datenbanksprache von Phase 2: eine 1:n-Beziehung, zweite
        Tabelle, Fremdschluessel auf die Kundennummer.

    DER FREMDSCHLUESSEL
        Genau deshalb musste die Kundennummer den Round-Trip ueberleben
        (Montag). Ohne stabile Nummer koennte nichts auf einen Kunden zeigen.

    DIE FALLE MIT DEN SCHLUESSELN
        JSON kennt nur Strings als Objektschluessel. Schreibt man
        {1000: [...]} hinein, kommt {"1000": [...]} heraus — lautlos. Ein
        Nachschlagen mit der int-Nummer ginge danach ins Leere. Deshalb
        wandelt _laden() die Schluessel beim Lesen zurueck nach int, und
        als_dict() macht die Umwandlung beim Schreiben ausdruecklich statt
        sie json zu ueberlassen.

    WAS NOCH OFFEN IST
        Zwei Dateien koennen auseinanderlaufen. Wird ein Kunde geloescht,
        bleiben seine Notizen als Waisen liegen; auf_kunden_verteilen()
        meldet sie deshalb zurueck, statt sie stillschweigend zu schlucken.
        Und zwei Dateien bedeuten zwei Schreibvorgaenge: Bricht das Programm
        dazwischen ab, passen sie nicht mehr zusammen. Donnerstag macht EINE
        Datei atomar — atomar ueber zwei hinweg ist eine andere Nummer und
        bleibt hier bewusst ungeloest.
    """

    FORMAT_VERSION = 1

    def __init__(self, notizen: dict[int, list[Notiz]] | None = None) -> None:
        self._notizen: dict[int, list[Notiz]] = notizen if notizen is not None else {}

    def __len__(self) -> int:
        """Anzahl der Notizen insgesamt, nicht der Kunden mit Notizen."""
        return sum(len(liste) for liste in self._notizen.values())

    def __repr__(self) -> str:
        return f"NotizSpeicher({len(self)} Notizen zu {len(self._notizen)} Kunden)"

    def fuer(self, nummer: int) -> list[Notiz]:
        """Die Notizen eines Kunden — leere Liste, wenn er keine hat."""
        return list(self._notizen.get(nummer, []))

    @classmethod
    def von_kunden(cls, kunden: "Kundenliste") -> "NotizSpeicher":
        """Sammelt die Notizen aus einer Kundenliste ein.

        Erkennungsmerkmal ist isinstance(Notiz) und nicht "steht nicht in der
        Registry": Ein Objekt, das weder registriert noch eine Notiz ist,
        soll nicht stillschweigend in der Notizdatei landen. Es faellt
        weiterhin heraus — das ist die bekannte Restluecke von
        komponente_hinzufuegen(), und sie soll sichtbar bleiben statt hier
        halb zugedeckt zu werden.
        """
        gesammelt: dict[int, list[Notiz]] = {}
        for kunde in kunden:
            eigene = [k for k in kunde._info_komponenten if isinstance(k, Notiz)]
            if eigene:
                gesammelt[kunde.nummer] = eigene
        return cls(gesammelt)

    def auf_kunden_verteilen(self, kunden: "Kundenliste") -> list[int]:
        """Haengt die Notizen wieder an die passenden Kunden.

        Liefert die Kundennummern zurueck, zu denen es keinen Kunden (mehr)
        gibt — die Waisen aus dem Docstring der Klasse. Bewusst ein
        Rueckgabewert und kein Fehler: Ob Waisen ein Problem sind, weiss nur
        der Aufrufer. Ein Reparaturwerkzeug will sie sehen, ein normaler
        Programmstart darf sie ignorieren. Was diese Klasse nicht tun darf,
        ist so zu tun, als gaebe es sie nicht.
        """
        vorhanden = {kunde.nummer: kunde for kunde in kunden}
        waisen = []
        for nummer, notizen in self._notizen.items():
            kunde = vorhanden.get(nummer)
            if kunde is None:
                waisen.append(nummer)
                continue
            for notiz in notizen:
                kunde.komponente_hinzufuegen(notiz)
        return sorted(waisen)

    def waisen_uebernehmen(self, quelle: "NotizSpeicher", nummern: list[int]) -> None:
        """Holt die Notizen der Waisen aus einem anderen Speicher herueber.

        Review-Fix 15.09.2026: von_kunden() sammelt nur ein, was an Kunden
        haengt. Waisen haengen an niemandem und waeren beim Speichern
        verloren. Diese Methode gibt sie aus dem geladenen Speicher zurueck.

        Hat inzwischen ein Kunde diese Nummer (nur ueber nummer= moeglich,
        weil der Zaehler ueber Waisen-Nummern gezogen wird), werden die
        Notizen zusammengelegt. Es geht in keinem Fall etwas verloren.
        """
        for nummer in nummern:
            self._notizen[nummer] = self._notizen.get(nummer, []) + quelle.fuer(nummer)

    def als_dict(self) -> dict[str, Any]:
        """Wie bei Kundenliste: dict mit Versionsfeld, nicht nackte Daten.

        str(nummer) ist ausdruecklich hingeschrieben, obwohl json dieselbe
        Umwandlung von sich aus vornaehme. Der Grund ist Ehrlichkeit: Beim
        Laden MUSS zurueckgewandelt werden, und das sieht nur, wer weiss,
        dass die Umwandlung stattfindet. Eine lautlose Konvertierung, die man
        beim Lesen von Hand rueckgaengig macht, ist eine Falle.
        """
        return {
            "version": NotizSpeicher.FORMAT_VERSION,
            "notizen": {
                str(nummer): [notiz.als_dict() for notiz in notizen]
                for nummer, notizen in self._notizen.items()
            },
        }

    @classmethod
    def aus_dict(cls, daten: dict[str, Any]) -> "NotizSpeicher":
        if not isinstance(daten, dict):
            raise DateiInhaltError(
                f"Erwartet wird ein JSON-Objekt, gefunden wurde "
                f"{type(daten).__name__}"
            )

        version = daten.get("version")
        if version != cls.FORMAT_VERSION:
            raise DateiInhaltError(
                f"Unbekannte Formatversion {version!r} im Notizspeicher, "
                f"erwartet wird {cls.FORMAT_VERSION}"
            )

        gelesen: dict[int, list[Notiz]] = {}
        for schluessel, eintraege in daten.get("notizen", {}).items():
            try:
                nummer = int(schluessel)
            except ValueError as e:
                raise DateiInhaltError(
                    f"Kundennummer im Notizspeicher ist keine Zahl: {schluessel!r}"
                ) from e
            gelesen[nummer] = [Notiz.aus_dict(eintrag) for eintrag in eintraege]
        return cls(gelesen)

    def speichern(self, pfad: str) -> None:
        """Atomar wie Kundenliste.speichern() — dieselbe Hilfsfunktion.

        Wichtig fuer KundenDatei: Beide Dateien werden JE FUER SICH
        unteilbar ersetzt. Dass beide ZUSAMMEN passen, folgt daraus nicht —
        zwischen den zwei os.replace() liegt ein Moment, in dem die
        Notizdatei schon neu und die Kundendatei noch alt ist.
        """
        json_atomar_schreiben(pfad, self.als_dict())

    @classmethod
    def laden(cls, pfad: str) -> "NotizSpeicher":
        try:
            with open(pfad, encoding="utf-8") as datei:
                rohdaten = json.load(datei)
        except FileNotFoundError as e:
            raise DateiNichtGefundenError(
                f"Notizdatei existiert nicht: {pfad!r}"
            ) from e
        except OSError as e:
            raise DateiNichtLesbarError(f"Notizdatei nicht lesbar: {pfad!r}") from e
        except json.JSONDecodeError as e:
            raise DateiInhaltError(
                f"Notizdatei {pfad!r} enthaelt kein gueltiges JSON "
                f"(Zeile {e.lineno}, Spalte {e.colno}): {e.msg}"
            ) from e

        return cls.aus_dict(rohdaten)


# ============================================================================
# Laden und Speichern beider Dateien (Woche 9, Kuer und Review-Fix)
# Aufgabe: die eigentliche Arbeit fuer KundenDatei UND kunden_datei
# ============================================================================
class Geladen(NamedTuple):
    """Was _beide_laden() zurueckgibt: drei Werte mit Namen (Woche 10).

    Vorher ein nacktes Tupel, tuple[Kundenliste, NotizSpeicher, list[int]].
    Wer das Ergebnis benutzte, musste sich die REIHENFOLGE merken. Jetzt
    heissen die Teile kunden, speicher und waisen.

    Warum NamedTuple und nicht dict oder dataclass?

    - dict: Ein Tippfehler beim Setzen legt still einen neuen Schluessel an,
      beim Lesen gibt es erst zur Laufzeit einen KeyError, und mypy sieht
      beides nicht. Ein dict passt, wenn die Schluessel vorher nicht
      feststehen — hier stehen sie fest.
    - dataclass: ginge auch. NamedTuple bleibt aber ein Tupel: Der bestehende
      Code `kunden, speicher, waisen = _beide_laden(...)` laeuft unveraendert
      weiter. Und ein Ergebnis soll man nicht nachtraeglich aendern — ein
      NamedTuple ist von Haus aus unveraenderlich.
    """

    kunden: "Kundenliste"
    speicher: "NotizSpeicher"
    waisen: list[int]


def _notizpfad_ableiten(kunden_pfad: str, notiz_pfad: str | None) -> str:
    """kunden.json -> kunden.notizen.json, falls kein eigener Pfad angegeben ist.

    Die Notizdatei gehoert zur Kundendatei; sie getrennt angeben zu muessen
    waere eine Fehlerquelle ohne Gegenwert.
    """
    if notiz_pfad is not None:
        return notiz_pfad
    stamm = kunden_pfad[:-5] if kunden_pfad.endswith(".json") else kunden_pfad
    return f"{stamm}.notizen.json"


def _beide_laden(kunden_pfad: str, notiz_pfad: str) -> Geladen:
    """Laedt Kunden und Notizen, haengt die Notizen an und meldet Waisen.

    Herausgezogen aus KundenDatei.__enter__, als die Generator-Variante
    dazukam (Kuer Woche 9). Seitdem steht die Arbeit an EINER Stelle, und
    Klasse und Generator sind nur noch zwei Verpackungen darum.

    Fehlende Datei = erster Programmstart = leer anfangen. Alle anderen
    Dateifehler fliegen weiter: Eine kaputte Datei darf nicht still durch
    eine leere ersetzt werden, sonst ueberschreibt das naechste Speichern
    echte Daten.

    Eine Nummer, zu der noch Notizen existieren, ist nicht frei (Review-Fix
    15.09.2026). Bekaeme ein neuer Kunde die Nummer einer Waise, haengten ihre
    Notizen beim naechsten Laden an ihm — an der falschen Person. Deshalb wird
    der Zaehler auch ueber die Waisen-Nummern gezogen, genau wie
    Kunde.aus_dict() ihn ueber geladene Kundennummern zieht.
    """
    try:
        kunden = Kundenliste.laden(kunden_pfad)
    except DateiNichtGefundenError:
        kunden = Kundenliste()

    try:
        speicher = NotizSpeicher.laden(notiz_pfad)
    except DateiNichtGefundenError:
        speicher = NotizSpeicher()

    waisen = speicher.auf_kunden_verteilen(kunden)
    if waisen:
        Kunde.naechste_nummer = max(Kunde.naechste_nummer, max(waisen) + 1)
    return Geladen(kunden, speicher, waisen)


def _beide_speichern(
    kunden: "Kundenliste",
    geladen: "NotizSpeicher",
    waisen: list[int],
    kunden_pfad: str,
    notiz_pfad: str,
) -> None:
    """Schreibt Notizen und Kunden — ohne Waisen zu verlieren.

    REVIEW-FIX 15.09.2026
        Vorher wurde der Notizspeicher nur aus den Kunden neu eingesammelt.
        Waisen haengen an keinem Kunden, also fehlten sie in der neuen Datei:
        Ein with-Block, der gar nichts tat, loeschte sie. Jetzt werden sie aus
        dem geladenen Speicher wieder uebernommen. Gemeldet ist nicht
        aufbewahrt — erst beides zusammen ist richtig.

    REIHENFOLGE MIT ABSICHT: erst die Notizen, dann die Kunden
        Scheitert das Schreiben der Notizen, ist noch gar nichts geschrieben —
        beide Dateien stehen konsistent auf dem alten Stand. Scheitert es
        danach bei den Kunden, verweisen neue Notizen auf Kunden, die in der
        alten Kundendatei fehlen: Beim naechsten Laden tauchen sie als Waisen
        auf und bleiben dank des Fixes erhalten. Umgekehrt (Kunden zuerst)
        fehlten einfach Notizen, und das fiele niemandem auf.

        Ueber zwei Dateien hinweg ist das trotzdem nicht atomar. Donnerstag
        loest das fuer EINE Datei; fuer zwei braeuchte es ein Journal oder eine
        einzige Datei. Bewusst offen.
    """
    neu = NotizSpeicher.von_kunden(kunden)
    neu.waisen_uebernehmen(geladen, waisen)
    neu.speichern(notiz_pfad)
    kunden.speichern(kunden_pfad)


# ============================================================================
# Kontextmanager fuer die Dateischicht (Woche 9, Mittwoch)
# Aufgabe: Laden beim Betreten, Speichern beim Verlassen
# ============================================================================
class KundenDatei:
    """Klammert Laden und Speichern um einen Arbeitsblock.

        with KundenDatei("kunden.json") as kunden:
            kunden.hinzufuegen(Kunde("Neu", "neu@x.de"))
        # hier ist schon gespeichert

    DIE ENTSCHEIDUNG: TRANSAKTIONAL
        Fliegt im Block eine Exception, wird NICHT gespeichert. Die alte Datei
        bleibt unangetastet, die Arbeit des Blocks ist verloren.

        Der Gegenentwurf waere, immer zu speichern. Dann bliebe bei einem
        Import, der bei Eintrag 900 abbricht, die Arbeit an den ersten 899
        erhalten — aber in der Datei staende ein Zustand, den niemand
        bewusst herbeigefuehrt hat, und man saehe ihm das nicht an. Kracht
        der Block gerade WEIL die Daten inkonsistent wurden, waere die
        Inkonsistenz danach festgeschrieben.

        Gewaehlt wurde deshalb: Eine Datei enthaelt immer einen Zustand, der
        vollstaendig erreicht wurde. Dasselbe Prinzip, das Donnerstag eine
        Ebene tiefer noch einmal auftaucht — os.replace() sorgt dafuer, dass
        auch auf Byte-Ebene kein Zwischenzustand sichtbar wird. Und dasselbe,
        das in Phase 2 bei SQL "Transaktion" heisst: alles oder nichts.

        Angenehme Nebenwirkung: Weil nur im Gutfall gespeichert wird, kann
        ein Fehler beim Speichern nie einen Fehler aus dem Block ueberdecken.
        Die Falle, dass __exit__ die eigentliche Ursache verschluckt und nur
        noch als __context__ mitfuehrt, entsteht hier gar nicht erst.

    WAS __enter__ ANDERS MACHT ALS BEI Fehlerprotokoll (Woche 7)
        Dort war __enter__ ein blosses `return self` und konnte nicht
        scheitern. Hier laedt es — und Laden kann werfen. Zwei Folgen:

        1. Wirft __enter__, laeuft weder der Block noch __exit__. Was
           __enter__ vorher belegt hat, raeumt niemand mehr auf. Diese
           Fassung belegt bewusst nichts, was Aufraeumen braeuchte: Die
           Dateien werden von laden() geoeffnet UND geschlossen, bevor
           __enter__ zurueckkehrt. Es bleibt kein offenes Handle liegen.

        2. Zurueckgegeben wird die Kundenliste, nicht self. `as kunden` soll
           die Liste liefern, nicht den Verwalter drumherum.

    DIE FEHLENDE DATEI IST KEIN FEHLER
        Beim ersten Programmstart gibt es noch nichts. DateiNichtGefundenError
        wird deshalb gefangen und mit einer leeren Liste beantwortet — genau
        dafuer ist er am Dienstag eine eigene Klasse geworden. Alle anderen
        Dateifehler fliegen weiter: Eine unlesbare oder kaputte Datei
        stillschweigend durch eine leere zu ersetzen hiesse, vorhandene Daten
        beim naechsten Speichern zu ueberschreiben.
    """

    def __init__(self, kunden_pfad: str, notiz_pfad: str | None = None) -> None:
        self.kunden_pfad = kunden_pfad
        self.notiz_pfad = _notizpfad_ableiten(kunden_pfad, notiz_pfad)

        self._kunden: Kundenliste | None = None
        self._speicher: NotizSpeicher | None = None
        self.waisen: list[int] = []

    def __enter__(self) -> Kundenliste:
        # Ein Kontextmanager ist nicht automatisch wiederverwendbar. Ohne
        # diese Pruefung wuerde ein zweites `with` auf demselben Objekt die
        # bereits geladene Liste stillschweigend ersetzen — und die
        # Aenderungen des ersten Blocks waeren weg.
        if self._kunden is not None:
            raise KundenverwaltungError(
                "Diese KundenDatei ist bereits geoeffnet. Lege fuer einen "
                "zweiten with-Block ein neues Objekt an."
            )

        # Die eigentliche Arbeit steht seit der Kuer in _beide_laden(), damit
        # die Generator-Variante dieselbe benutzt. Hier bleibt nur, was die
        # KLASSE ausmacht: Ergebnisse in self ablegen, damit __exit__ sie
        # findet und der Aufrufer ueber .waisen an die Waisen kommt.
        kunden, self._speicher, self.waisen = _beide_laden(
            self.kunden_pfad, self.notiz_pfad
        )
        self._kunden = kunden
        return kunden

    def __exit__(
        self,
        exc_typ: type[BaseException] | None,
        exc_wert: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        # Literal[False] statt bool, und das ist keine Kosmetik: mypy --strict
        # hat den blossen `bool` bemaengelt. Die Begruendung des Typecheckers
        # ist genau die Regel aus Woche 7 — ein truthy Rueckgabewert SCHLUCKT
        # die Exception. Wer `-> bool` schreibt, kuendigt an, dass er
        # moeglicherweise schluckt. Literal[False] sagt: niemals.
        #
        # Der Unterschied zu Fehlerprotokoll (Woche 7) ist damit im TYP
        # ablesbar: Dort steht `-> bool`, weil das schlucken-Flag die Wahl
        # offenlaesst. Hier waere Schlucken Datenverlust mit Ansage.
        #
        # Der Zustand wird IMMER zurueckgesetzt, auch wenn nicht gespeichert
        # wird — sonst bliebe das Objekt nach einem Fehler fuer immer
        # "geoeffnet" und die Pruefung in __enter__ wuerde zur Sackgasse.
        kunden, self._kunden = self._kunden, None
        speicher, self._speicher = self._speicher, None

        if exc_wert is not None or kunden is None or speicher is None:
            return False

        _beide_speichern(
            kunden, speicher, self.waisen, self.kunden_pfad, self.notiz_pfad
        )
        return False


# ============================================================================
# Kuer Woche 9: dieselbe Klammer als Generator
# ============================================================================
@contextmanager
def kunden_datei(
    kunden_pfad: str, notiz_pfad: str | None = None
) -> Generator[Kundenliste, None, None]:
    """Dieselbe Klammer wie KundenDatei — als Funktion mit @contextmanager.

        with kunden_datei("kunden.json") as kunden:
            kunden.hinzufuegen(Kunde("Neu", "neu@x.de"))

    Was vor dem yield steht, ist __enter__. Was danach steht, ist __exit__.
    Die Variablen ueberleben die Pause am yield von selbst — deshalb braucht
    die Funktion kein self, in dem sie sich etwas merken muesste.

    TRANSAKTIONAL OHNE EIN EINZIGES if
        Fliegt im with-Block eine Exception, loest Python sie genau am yield
        aus. Die Zeile danach wird dann nie erreicht — also wird nicht
        gespeichert. KundenDatei braucht dafuer `if exc_wert is not None`;
        hier erledigt das der ganz normale Programmfluss.

    DIE BEIDEN VORHERSAGEN AUS DER KUER (aufgeloest am 15.09.2026)
        a) Ohne try — wird bei einem Fehler gespeichert?
           Vermutung: "Es sollte kein Fehler geschmissen werden, da es vorher
           kein enter ausgefuehrt worden ist."
           Tatsaechlich: Der Teil vor dem yield IST das enter und lief schon.
           Der Fehler fliegt am yield weiter zum Aufrufer, gespeichert wird
           NICHT. Genau richtig fuer die Entscheidung vom Mittwoch.

        b) Mit try/finally — wird gespeichert?
           Vermutung: "speichert nicht".
           Tatsaechlich: finally laeuft IMMER, also wird auch bei einem Fehler
           gespeichert, und die halbe Arbeit landet in der Datei. Die Variante
           sieht "sauberer" aus und bricht trotzdem die Entscheidung.

        Beides steht als Test in test_kunde.py (Kuer, Teil 2 und 3).

    WAS DIE FUNKTION NICHT KANN
        Keine .waisen — eine Funktion hat keine Attribute. Die Waisen gehen
        nicht verloren (siehe _beide_speichern), der Aufrufer erfaehrt nur
        nichts davon. Wer sie sehen will, nimmt KundenDatei.

        Nicht wiederverwendbar — ein zweites `with` auf demselben Objekt
        scheitert mit einem AttributeError aus der Standardbibliothek. Im
        Ergebnis richtig, aber mit einer Meldung, die niemandem hilft.
        KundenDatei meldet denselben Fall verstaendlich.

    Die Arbeit selbst steht in _beide_laden() und _beide_speichern(), die
    auch KundenDatei benutzt. Die beiden Varianten unterscheiden sich damit
    nur noch in der Verpackung.
    """
    notiz_datei = _notizpfad_ableiten(kunden_pfad, notiz_pfad)
    geladen = _beide_laden(kunden_pfad, notiz_datei)
    yield geladen.kunden
    _beide_speichern(
        geladen.kunden, geladen.speicher, geladen.waisen, kunden_pfad, notiz_datei
    )
