"""Die Klammer um einen Arbeitsblock: laden beim Betreten, speichern beim
Verlassen — transaktional.

Seit Woche 12 weiss dieses Modul nicht mehr, WOHIN gespeichert wird. Es
bekommt einen Speicher uebergeben und ruft dessen Vertrag auf. Wer JSON
will, gibt einen DateiSpeicher mit; wer testet, einen InMemorySpeicher.

KundenDatei ist die Klasse, kunden_datei dieselbe Klammer als Generator mit
@contextmanager. Beide benutzen denselben Speicher und unterscheiden sich
nur in der Verpackung.
"""

from collections.abc import Generator
from contextlib import contextmanager
from types import TracebackType
from typing import Literal

from .exceptions import KundenverwaltungError
from .kundenliste import Kundenliste
from .notizen import NotizSpeicher
from .speicher import Speicher


# ============================================================================
# Kontextmanager fuer die Dateischicht (Woche 9, Mittwoch)
# Aufgabe: Laden beim Betreten, Speichern beim Verlassen
# ============================================================================
class KundenDatei:
    """Klammert Laden und Speichern um einen Arbeitsblock.

        with KundenDatei(DateiSpeicher("kunden.json")) as kunden:
            kunden.hinzufuegen(Kunde("Neu", "neu@x.de"))
        # hier ist schon gespeichert

    DER SPEICHER KOMMT VON AUSSEN (Woche 12, Mittwoch)
        Vorher nahm diese Klasse einen Pfad entgegen und baute sich daraus
        selbst zwei JSON-Dateien. Damit war sie an JSON gebunden, obwohl JSON
        sie nichts angeht: Ihre Aufgabe ist die KLAMMER — laden, arbeiten
        lassen, speichern oder eben nicht.

        Jetzt bekommt sie ein fertiges Speicher-Objekt. Sie ruft nur noch
        laden() und speichern() auf und weiss nicht, was dahinter steckt:

            KundenDatei(DateiSpeicher("kunden.json"))   # zwei JSON-Dateien
            KundenDatei(InMemorySpeicher())             # nichts auf der Platte

        Was das bringt, sieht man am besten an dem, was NICHT mehr geht: Man
        kann diese Klasse nicht mehr testen, ohne sich zu entscheiden, WO
        gespeichert wird — und genau deshalb kann man sie ab jetzt testen,
        ohne eine Datei anzulegen.

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

    DER LEERE SPEICHER IST KEIN FEHLER
        Beim ersten Programmstart gibt es noch nichts. Dass daraus eine leere
        Kundenliste wird statt eines Fehlers, entscheidet seit Woche 12 die
        IMPLEMENTIERUNG, nicht mehr diese Klasse — DateiSpeicher faengt dafuer
        seinen DateiNichtGefundenError selbst ab. Richtig so: Was "noch nichts
        da" heisst, weiss nur, wer weiss, wo die Daten liegen. Bei einer
        Datenbank waere es eine leere Tabelle und gar keine Exception.

        Alle anderen Speicherfehler fliegen weiter bis hierher und aus dem
        with-Block heraus. Eine kaputte Quelle stillschweigend durch eine
        leere zu ersetzen hiesse, vorhandene Daten beim naechsten Speichern zu
        ueberschreiben.
    """

    def __init__(self, speicher: Speicher) -> None:
        self.speicher = speicher

        self._kunden: Kundenliste | None = None
        self._notizen: NotizSpeicher | None = None
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

        # Die eigentliche Arbeit macht der Speicher. Hier bleibt nur, was die
        # KLASSE ausmacht: Ergebnisse in self ablegen, damit __exit__ sie
        # findet und der Aufrufer ueber .waisen an die Waisen kommt.
        kunden, self._notizen, self.waisen = self.speicher.laden()
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
        notizen, self._notizen = self._notizen, None

        if exc_wert is not None or kunden is None or notizen is None:
            return False

        self.speicher.speichern(kunden, notizen, self.waisen)
        return False


# ============================================================================
# Kuer Woche 9: dieselbe Klammer als Generator
# ============================================================================
@contextmanager
def kunden_datei(speicher: Speicher) -> Generator[Kundenliste, None, None]:
    """Dieselbe Klammer wie KundenDatei — als Funktion mit @contextmanager.

        with kunden_datei(DateiSpeicher("kunden.json")) as kunden:
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
        nicht verloren (Speicher.speichern bekommt sie), der Aufrufer erfaehrt
        nur nichts davon. Wer sie sehen will, nimmt KundenDatei.

        Nicht wiederverwendbar — ein zweites `with` auf demselben Objekt
        scheitert mit einem AttributeError aus der Standardbibliothek. Im
        Ergebnis richtig, aber mit einer Meldung, die niemandem hilft.
        KundenDatei meldet denselben Fall verstaendlich.

    Die Arbeit selbst macht der uebergebene Speicher — derselbe, den auch
    KundenDatei bekaeme. Die beiden Varianten unterscheiden sich damit nur
    noch in der Verpackung.
    """
    geladen = speicher.laden()
    yield geladen.kunden
    speicher.speichern(geladen.kunden, geladen.speicher, geladen.waisen)
