"""Die Kunde-Klasse und ihr Zustand.

KundenZustand ist eine Enum statt eines bool: Ein Kunde kennt drei
Zustaende (aktiv, inaktiv, gesperrt), und ein Tippfehler an einer Enum
faellt sofort auf statt still falsch zu vergleichen."""

from __future__ import annotations

from enum import Enum
from functools import cached_property, total_ordering
from typing import TYPE_CHECKING, Any

from .exceptions import (
    DateiInhaltError,
    UngueltigeEmailError,
    UngueltigerBetragError,
    UngueltigerNameError,
)
from .komponenten import (
    Adresse,
    GeschaeftsDaten,
    GrosskundenDaten,
    InfoLieferant,
    PrivatDaten,
)
from .validierung import email_gueltig

# TYPE_CHECKING (Woche 11, Donnerstag): InfoFaehig steht in diesem Modul nur in
# Annotationen — als Parametertyp von komponente_hinzufuegen() und als Typ einer
# lokalen Liste. Zur Laufzeit wird der Name nie gebraucht. TYPE_CHECKING ist
# beim Programmlauf False und nur fuer mypy True; der Import passiert also nur
# beim Pruefen. Damit das geht, macht `from __future__ import annotations` oben
# alle Annotationen dieses Moduls zu Text, den Python nicht auswertet.
#
# Preis: typing.get_type_hints(Kunde.komponente_hinzufuegen) findet den Namen
# zur Laufzeit nicht mehr und wirft NameError. Im Projekt liest niemand diese
# Annotationen zur Laufzeit — anders als bei einer dataclass, die ihre Felder
# daraus bestimmt. Deshalb nur an dieser einen Stelle, an der ein Name wirklich
# ausschliesslich in Annotationen vorkommt.
if TYPE_CHECKING:
    from .komponenten import InfoFaehig


# ============================================================================
# Kundenzustand (Woche 10, Mittwoch)
# Aufgabe: die erlaubten Zustaende eines Kunden benennen — und nur diese
# ============================================================================
class KundenZustand(Enum):
    """In welchem Zustand ein Kunde ist. Ersetzt das fruehere aktiv-bool.

    WARUM NICHT bool
        Ein bool kennt zwei Werte. Ein Kunde kennt drei Zustaende: aktiv,
        inaktiv (hat gekuendigt, darf zurueckkommen) und gesperrt (darf nicht
        mehr bestellen). Mit bool muesste der dritte in ein zweites Feld — und
        schon gaebe es Kombinationen wie "aktiv UND gesperrt", die es fachlich
        nicht geben darf.

    WARUM NICHT str
        Ein String laesst jeden Tippfehler zu, ohne sich zu beschweren:

            kunde.zustand == "gesprerrt"   # immer False, kein Fehler

        Der Vergleich ist einfach falsch, und niemand merkt es. Bei einer Enum
        fliegt derselbe Tippfehler sofort:

            KundenZustand.GESPRERRT        # AttributeError, sofort sichtbar

        und mypy meldet ihn schon, bevor das Programm laeuft.

    DIE WERTE
        Jedes Mitglied hat einen String als Wert ("aktiv", ...). Den braucht
        man ueberall, wo der Zustand die Python-Welt verlaesst — zum Beispiel
        in einer JSON-Datei. Innerhalb des Programms vergleicht man die
        Mitglieder selbst, mit `is`.
    """

    AKTIV = "aktiv"
    INAKTIV = "inaktiv"
    GESPERRT = "gesperrt"


# BEWUSST KEINE DATACLASS (Woche 10, Donnerstag)
#
# Kunde wurde probeweise als dataclass nachgebaut (test_kunde.py, Woche 10
# Donnerstag). Sechs Stellen passen nicht, alle gemessen:
#
#   1. Das erzeugte __init__ prueft nichts. Leerer Name und kaputte Email
#      gehen durch. Kunde validiert im Konstruktor und in den Settern.
#   2. email ist Feld UND Property gleichen Namens. @dataclass macht dann das
#      Property-Objekt zum Default des Feldes; ein Aufruf ohne email scheitert
#      mit "argument of type 'property' is not iterable".
#   3. Der Nummernzaehler ist ein Klassenattribut. Mit Annotation wird er zum
#      Konstruktorparameter — ausser man schreibt ClassVar.
#   4. Das erzeugte __eq__ vergleicht alle Felder. Woche 6 hat entschieden:
#      gleiche Nummer heisst gleicher Kunde, auch bei anderem Umsatz.
#   5. order=True sortiert nach der Reihenfolge der Felder, also nach name.
#      Kunde sortiert nach Umsatz, dann Nummer.
#   6. name soll nur lesbar sein. Das geht nur mit frozen — und das sperrt
#      auch umsatz und zustand.
#
# Jede Stelle einzeln liesse sich reparieren (eq=False, ClassVar,
# field(init=False), __post_init__ ...). Zusammen bliebe vom Gewinn nichts
# uebrig: Man schriebe mehr Schalter, als vorher Code dastand.
#
# Die Faustregel: Eine dataclass passt, wenn eine Klasse im Kern Daten TRAEGT
# (Adresse, Notiz). Kunde BEWACHT seine Daten — mit Regeln, einem Zaehler und
# einer eigenen Vorstellung von Gleichheit. Dafuer ist eine normale Klasse das
# richtige Werkzeug.
@total_ordering
class Kunde:

    naechste_nummer = 1000
    GROSSKUNDE_GRENZE = 10000

    def __init__(self, name: str, email: str,*,
                nummer: int | None = None,
                 geschaefts_daten: "GeschaeftsDaten | None" = None,
                 private_daten: "PrivatDaten | None" = None,
                 großkunden_daten: "GrosskundenDaten | None" = None,
                 adresse: "Adresse | None" = None,
                 tags: list[str] | None = None) -> None:
        if not name or not name.strip():
            raise UngueltigerNameError(f"Name darf nicht leer sein, war: {name!r}")
        self.__name = name
        self.email = email
        self.geschaefts_daten = geschaefts_daten
        self.private_daten = private_daten
        self.großkunden_daten = großkunden_daten
        self.adresse = adresse
        self._umsatz = 0.0

        if nummer is None:
            self._nummer = Kunde.naechste_nummer
            Kunde.naechste_nummer += 1
        else:
            self._nummer = nummer

        self._zustand = KundenZustand.AKTIV
        self._tags = tags if tags is not None else []

        # Polymorphe Verarbeitung (Woche 5): alles mit info() landet hier,
        # unabhaengig davon, ob es eine eigene Basisklasse hat oder nicht.
        self._info_komponenten: list[InfoFaehig] = [
            komponente for komponente in (private_daten, geschaefts_daten, großkunden_daten)
            if komponente is not None
        ]



    # ------------------------------------------------------------------
    # Properties (Getter/Setter)
    # ------------------------------------------------------------------
    @property
    def email(self)-> str:
        return self._email

    @email.setter
    def email(self, wert: str) -> None:
        if not email_gueltig(wert):
            raise UngueltigeEmailError(f"Ungültige E-Mail: {wert}")
        self._email = wert

    @property
    def name(self) -> str:
        return self.__name

    @property
    def umsatz(self) -> float:
        return self._umsatz

    @umsatz.setter
    def umsatz(self, wert: float) -> None:
        if wert < 0:
            raise UngueltigerBetragError(f"Umsätze müssen nicht-negativ sein. Wert: {wert}")
        # float(): Die Annotation sagt float, aber Python wandelt nicht von
        # selbst. Ohne den Aufruf haelt umsatz mal ein int, mal einen float —
        # je nachdem, wie zugewiesen wurde. Das schlaegt bis in die
        # CSV-Ausgabe durch ("1500" gegen "1500.0").
        self._umsatz = float(wert)

    @property
    def zustand(self) -> KundenZustand:
        return self._zustand

    @zustand.setter
    def zustand(self, wert: KundenZustand) -> None:
        # Typpruefung wie frueher beim aktiv-Setter: Ein falscher Typ ist ein
        # Programmierfehler am Aufrufort, also TypeError. Genau hier faengt die
        # Enum den Fall ab, den ein String durchgelassen haette:
        # kunde.zustand = "gesperrt" ist kein Zustand, sondern nur ein Wort.
        if not isinstance(wert, KundenZustand):
            raise TypeError(
                f"zustand erwartet KundenZustand, bekam {type(wert).__name__}: {wert!r}"
            )
        self._zustand = wert

    @property
    def aktiv(self) -> bool:
        """Nur noch lesbar — abgeleitet aus dem Zustand (Woche 10).

        Frueher gab es einen Setter. Er ist weg, weil es sonst ZWEI Wege gaebe,
        denselben Zustand zu schreiben, und die koennten sich widersprechen:
        `kunde.aktiv = True` auf einem gesperrten Kunden haette ihn still
        entsperrt. Geschrieben wird nur noch ueber `zustand` oder die Methoden
        aktivieren(), deaktivieren() und sperren().
        """
        return self._zustand is KundenZustand.AKTIV

    @property
    def tags(self) -> list[str]:
        return self._tags

    @property
    def nummer(self) -> int:
        return self._nummer

    @cached_property
    def risiko_score(self) -> float:
        """Wird beim ersten Zugriff berechnet und danach zwischengespeichert.

        `cached_property` legt das Ergebnis in `self.__dict__` ab. Ab dem
        zweiten Zugriff greift die normale Attributsuche und findet den Wert
        dort, bevor sie ueberhaupt bei der Property landet — die Berechnung
        laeuft also nur einmal.

        Folge: Der Wert altert. Aendert sich der Umsatz nach dem ersten
        Zugriff, bleibt der Score stehen. Belegen laesst sich das Caching
        ueber __dict__ statt ueber eine Stoppuhr.
        """
        score = 0.0
        if not self.aktiv:
            score += 50.0
        if self.umsatz < 100:
            score += 30.0
        elif self.umsatz > self.grosskunde_grenze():
            score -= 20.0

        if "@" in self.email and ".de" in self.email:
            score -= 10.0

        return max(0, score)

    # ------------------------------------------------------------------
    # Großkunden-Logik (delegiert an Komponenten statt an Vererbung)
    # ------------------------------------------------------------------
    def grosskunde_grenze(self) -> int:
        if self.großkunden_daten:
            return self.großkunden_daten.GROSSKUNDE_GRENZE
        if self.geschaefts_daten:
            return self.geschaefts_daten.GROSSKUNDE_GRENZE
        return Kunde.GROSSKUNDE_GRENZE

    def is_grosskunde(self) -> bool:
        return self.umsatz >= self.grosskunde_grenze()

    def status(self) -> str:
        # Nicht aktiv heisst seit Woche 10: inaktiv ODER gesperrt. Der Wert der
        # Enum ist genau das Wort, das hier angezeigt werden soll.
        if not self.aktiv:
            return self._zustand.value
        if self.is_grosskunde():
            return "Kunde ist ein Grosskunde"
        return "Kunde ist ein normaler Kunde"

    # ------------------------------------------------------------------
    # Darstellung (Woche 6, Montag)
    # ------------------------------------------------------------------
    def __str__(self) -> str:
        """Fuer Menschen: knappe Einzeiler-Identitaet fuer Logs und Tabellen.

        Bewusst ohne info() — das ist mehrzeilig und wuerde Name und Email
        ein zweites Mal ausgeben. info() bleibt die ausfuehrliche Ansicht,
        __str__ die knappe.
        """
        return f"{self.nummer} {self.name} <{self.email}> — {self.status()}"

    def __repr__(self) -> str:
        """Fuer Entwickler: eval-faehige Form fuer den Konstruktor-Teil.

        Gewaehlt, weil man so die Klasse sieht und die Werte, die ueber den
        Konstruktor vergeben wurden. Die Komponenten gehoeren dazu, weil sie
        selbst Konstruktorparameter sind. Bewusst nicht enthalten sind
        nummer (automatisch vergeben) und umsatz (erst nachtraeglich
        gesetzt) — sie wuerden die eval-Faehigkeit brechen. Damit ist
        eval(repr(k)) rekonstruierbar, aber nicht identisch: neue
        Kundennummer, Umsatz 0. Begruendung in notizen.md, Woche 6 Montag.
        """
        # Nur gesetzte Werte aufnehmen, damit die Zeile bei einfachen Kunden
        # kurz bleibt.
        teile = [repr(self.name), repr(self.email)]
        for feldname, wert in (
            ("geschaefts_daten", self.geschaefts_daten),
            ("private_daten", self.private_daten),
            ("großkunden_daten", self.großkunden_daten),
            ("adresse", self.adresse),
        ):
            if wert is not None:
                teile.append(f"{feldname}={wert!r}")
        if self._tags:
            teile.append(f"tags={self._tags!r}")
        return f"Kunde({', '.join(teile)})"

    # ------------------------------------------------------------------
    # Gleichheit und Hashing (Woche 6, Dienstag)
    # ------------------------------------------------------------------
    def __eq__(self, other: object) -> bool:
        """Gleichheit ueber die Kundennummer.

        Zwei Objekte mit derselben Nummer sind derselbe Kunde, auch wenn sie
        im Speicher getrennt liegen — wie Gleichheit ueber einen
        Primaerschluessel in einer Datenbank.

        Der Parametertyp ist `object`, nicht `Kunde`, weil hier jeder Typ
        ankommen darf. Bei einem Fremdtyp wird `NotImplemented`
        zurueckgegeben (nicht: NotImplementedError geworfen). Python
        versucht daraufhin die gespiegelte Operation und faellt schliesslich
        auf den Identitaetsvergleich zurueck — Ergebnis False statt Absturz.
        """
        if not isinstance(other, Kunde):
            return NotImplemented
        return self.nummer == other.nummer


    def __hash__(self) -> int:
        """Hash konsistent zu __eq__ — beide stuetzen sich auf nummer.

        Regel: Was gleich ist, muss denselben Hash haben. Mengen und Dicts
        ordnen einen Wert anhand seines Hashs einem Fach zu und vergleichen
        per == nur innerhalb dieses Fachs. Bei abweichenden Hashes landen
        zwei gleiche Objekte in verschiedenen Faechern und werden nie
        miteinander verglichen — das Duplikat bliebe unbemerkt.

        Diese Methode ist zwingend, weil Python __hash__ automatisch auf None
        setzt, sobald eine Klasse __eq__ definiert. Ohne sie waere Kunde
        unhashbar.

        Gehasht wird ueber nummer, weil das read-only ist. Ueber umsatz zu
        hashen waere fatal: Nach einer Aenderung gehoerte das Objekt in ein
        anderes Fach, laege aber noch im alten — und waere in seiner eigenen
        Menge nicht mehr auffindbar.
        """
        return hash(self.nummer)

    # ------------------------------------------------------------------
    # Ordnung (Woche 6, Mittwoch)
    # ------------------------------------------------------------------
    def __lt__(self, other: object) -> bool:
        """Ordnung nach Umsatz, bei Gleichstand nach Kundennummer.

        Sortierkriterium ist der Umsatz — deshalb liefert sorted(kunden)
        ohne key-Argument die Umsatzreihenfolge.

        Die Kundennummer als zweites Kriterium ist kein Detail, sondern
        noetig, damit die Klasse widerspruchsfrei bleibt. @total_ordering
        baut die uebrigen Operatoren aus __lt__ UND __eq__ zusammen:

            a <= b   ->   (a < b) or (a == b)
            a >  b   ->   (not a < b) and (a != b)
            a >= b   ->   (not a < b)

        Der Dekorator setzt damit voraus, dass beide Methoden dieselbe
        Ordnung beschreiben. Mit "self.umsatz < other.umsatz" allein war das
        verletzt: Bei gleichem Umsatz sagte < "nicht kleiner", waehrend ==
        ueber die Nummer "nicht gleich" sagte — und aus diesen zwei Neins
        folgte gleichzeitig a > b UND b > a. Zwei Objekte, von denen jedes
        groesser als das andere war.

        Mit dem Tupel entscheidet bei Umsatzgleichstand die Nummer. Da die
        eindeutig ist, gilt zwischen zwei verschiedenen Kunden immer genau
        eines von <, > oder ==.

        Rest-Einschraenkung: Zwei Objekte mit gleicher Nummer, aber
        unterschiedlichem Umsatz waeren weiterhin widerspruechlich. Dieser
        Zustand ist im Modell ausgeschlossen — gleiche Nummer heisst
        derselbe Kunde.
        """
        if not isinstance(other, Kunde):
            return NotImplemented
        return (self.umsatz, self.nummer) < (other.umsatz, other.nummer)

    # ------------------------------------------------------------------
    # Öffentliche Methoden
    # ------------------------------------------------------------------
    def umsatz_hinzufügen(self, betrag:float) -> float:
        self.umsatz += betrag
        return self.umsatz

    def is_aktiv(self) -> bool:
        return self.aktiv

    def aktivieren(self) -> None:
        self.zustand = KundenZustand.AKTIV

    def deaktivieren(self) -> None:
        self.zustand = KundenZustand.INAKTIV

    def sperren(self) -> None:
        self.zustand = KundenZustand.GESPERRT

    # ------------------------------------------------------------------
    # Woche 5 Donnerstag: drei Haertungsvarianten nebeneinander.
    # info_lbyl() und info_eafp() sind Lern-/Vergleichscode, info() ist
    # die Variante, die bleibt.
    # ------------------------------------------------------------------

    # --- Variante 1: LBYL (Look Before You Leap) ---------------------
    # Fragt vorher, ob die Methode existiert. Faengt NUR den Fall
    # "Methode fehlt". Kracht info() intern, stuerzt es weiterhin ab.
    def info_lbyl(self) -> str:
        meldung = f"{self.name} ({self.email})"
        for komponente in self._info_komponenten:
            if hasattr(komponente, "info"):
                meldung += "\n" + komponente.info()
            else:
                meldung += f"\n[{type(komponente).__name__}: kein info()]"
        return meldung

    # --- Variante 2: EAFP (Easier to Ask Forgiveness than Permission) -
    # Ruft direkt auf und faengt den Fehler. Faengt mehr ab als noetig:
    # ein AttributeError AUS der Methode wird faelschlich als
    # "kein info()" gemeldet und versteckt so einen echten Bug.
    def info_eafp(self) -> str:
        meldung = f"{self.name} ({self.email})"
        for komponente in self._info_komponenten:
            try:
                meldung += "\n" + komponente.info()
            except AttributeError:
                meldung += f"\n[{type(komponente).__name__}: kein info()]"
        return meldung

    # --- Variante 3: Kombination (die bleibt) -------------------------
    # hasattr klaert "gibt es die Methode?", try/except klaert
    # "funktioniert der Aufruf?". Zwei verschiedene Marker, damit in der
    # Ausgabe sichtbar bleibt, welcher Fall vorlag.
    def info(self) -> str:
        meldung = f"{self.name} ({self.email})"
        for komponente in self._info_komponenten:
            name = type(komponente).__name__
            if not hasattr(komponente, "info"):
                meldung += f"\n[{name}: kein info()]"
                continue
            try:
                meldung += "\n" + komponente.info()
            except Exception as e:
                meldung += f"\n[{name}: info() fehlgeschlagen - {type(e).__name__}: {e}]"
        return meldung

    def komponente_hinzufuegen(self, komponente: InfoFaehig) -> None:
        """Duck Typing: jede Komponente mit info() ist willkommen, egal welcher Klasse."""
        self._info_komponenten.append(komponente)

    # ------------------------------------------------------------------
    # Serialisierung (Woche 9, Montag)
    # ------------------------------------------------------------------
    # Drei Entscheidungen vom 11.09.2026, die erklaeren, was NICHT drinsteht:
    #
    #   risiko_score fehlt, weil er errechnet ist (@cached_property). Ein
    #   gespeicherter Rechenwert waere ab dem Moment falsch, in dem sich die
    #   Formel aendert — und er wuerde die alte Formel stillschweigend in die
    #   Zukunft tragen. Berechenbares wird berechnet, nicht gespeichert.
    #
    #   Die drei EINZELNEN Komponentenattribute fehlen, weil sie doppelt
    #   waeren: Sie stehen alle in _info_komponenten, und DIE wird gespeichert
    #   — als getaggte Liste. Umgekehrt herum (drei feste Schluessel) waere es
    #   auch gegangen und waere besser typisiert gewesen, haette aber
    #   verlangt, dass Kunde.als_dict() bei jeder neuen Komponentenklasse
    #   angefasst wird. Das ist die Open-Closed-Verletzung, die wir am
    #   11.09. bewusst vermieden haben — siehe InfoLieferant.aus_dict().
    #
    #   Notizen fehlen bewusst. Sie liegen zwar auch in _info_komponenten,
    #   stehen aber nicht in der Registry (Duck-Typing-Entscheidung aus
    #   Woche 5) — und genau das ist seit dem 11.09. das Kriterium: Was
    #   registriert ist, gehoert zum Kunden; was nicht registriert ist, ist
    #   ein Anhang und bekommt einen eigenen Speicher (Dienstag).
    #
    # Pflichtfeld oder Default? Die Regel dieses dicts (Entscheidung 11.09.):
    #
    #   Identitaet  name, email, nummer   -> Pflicht, daten["..."], KeyError
    #   Zustand     umsatz, aktiv, tags   -> Default, daten.get("...", x)
    #
    #   Ein Kunde ohne Namen ist kein Kunde — da ist ein Default eine
    #   Erfindung. Ein Kunde ohne Umsatzangabe hat eben noch keinen Umsatz;
    #   0.0 ist dort keine Erfindung, sondern die richtige Antwort. Der
    #   Unterschied ist nicht Strenge, sondern ob es einen sinnvollen
    #   Ausgangswert GIBT.

    def als_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "email": self.email,
            # Eine Liste statt drei fester Schluessel: Kunde muss damit keine
            # einzige Komponentenklasse namentlich kennen. Jede kann sich
            # selbst beschreiben, weil als_dict() den Typmarker mitliefert.
            # Nicht registrierte Komponenten (Notiz) bleiben draussen.
            "komponenten": [
                komponente.als_dict()
                for komponente in self._info_komponenten
                if isinstance(komponente, InfoLieferant)
            ],
            "adresse": (
                self.adresse.als_dict()
                if self.adresse is not None else None
            ),
            "umsatz": self.umsatz,
            "nummer": self.nummer,
            "zustand": self.zustand.value,
            "tags": self.tags.copy(),
        }


    # Die Kundennummer und das Laden (Entscheidungen vom 11.09.2026)
    #
    #   Das Problem: __init__ vergibt sich die Nummer selbst und zaehlt den
    #   Klassenzaehler hoch. Ein aus_dict(), das nur cls(name, email) ruft,
    #   bekommt deshalb eine NEUE Nummer — und weil __eq__ an der Nummer
    #   haengt, waere der geladene Kunde ein ANDERER als der gespeicherte.
    #
    #   Gewaehlt: ein keyword-only Parameter nummer: int | None in __init__.
    #   Verworfen: nach dem Konstruieren self._nummer ueberschreiben — das
    #   greift an der read-only Property vorbei, dieselbe Gewalt, zu der die
    #   Tests in Zeile 556 und 817 schon gezwungen sind.
    #
    #   Rest-Loch, bewusst offen gelassen: Wurde eine Nummer schon VOR dem
    #   Laden vergeben, ist die Kollision bereits passiert und nicht mehr
    #   heilbar. Schliessen liesse es sich nur mit einem set vergebener
    #   Nummern auf Klassenebene. Nicht gemacht, weil in diesem Projekt
    #   nichts vor dem Laden erzeugt wird; test_kunde.py haelt das Verhalten
    #   als Test fest, damit es nicht in Vergessenheit geraet.
    #
    #   Die eigentliche Diagnose, fuer spaeter: naechste_nummer ist globaler
    #   veraenderlicher Zustand auf der Klasse. Er lebt im Prozess und merkt
    #   sich etwas, das den Prozess ueberdauern muss. In einem echten System
    #   liegt dieser Zaehler BEI DEN DATEN — eine Sequence in der Datenbank.
    #   Das ist Phase 2.
    #

    @classmethod
    def aus_dict(cls, daten: dict[str, Any]) -> "Kunde":
        """Baut einen Kunden aus einem dict — Gegenstueck zu als_dict().

        Zwei Dinge sind hier bewusst so und nicht anders:

        1. umsatz und zustand laufen ueber die PROPERTY, nicht ueber _umsatz
           und _zustand. Am privaten Feld vorbei zu schreiben waere kuerzer,
           wuerde aber jede Pruefung umgehen: ein negativer Umsatz aus einer
           kaputten Datei kaeme anstandslos durch, und eine JSON-5 bliebe int
           statt float — genau die Inkonsistenz, die in Woche 8 der
           Praxistest aufgedeckt hat. Merksatz: Eine Pruefung im Setter
           schuetzt nur die Wege, die durch den Setter gehen. Jede neue
           Ladefunktion ist ein neuer Weg.

           Folge, die man wissen muss: aus_dict() kann damit werfen —
           UngueltigerBetragError bei negativem Umsatz, DateiInhaltError bei
           einem Zustand, der sich nicht lesen laesst. Das ist gewollt.

        2. Der Zaehler wird bei JEDEM geladenen Kunden mitgezogen. Dadurch
           kann kein danach erzeugter Kunde eine geladene Nummer bekommen —
           unabhaengig davon, wann, wie oft und ueber welchen Weg geladen
           wird. Eine Regel, die man nicht brechen kann, statt einer, die man
           einhalten muss.

        3. Die Komponenten kommen als EINE getaggte Liste zurueck; welche
           Klasse jeder Eintrag ist, entscheidet InfoLieferant.aus_dict()
           anhand des Typmarkers. Kunde muss dafuer keine Komponentenklasse
           kennen.

           Danach allerdings schon: Die drei benannten Attribute werden aus
           der Liste herausgesucht, weil grosskunde_grenze() sie namentlich
           liest. Damit ist ehrlich gesagt: Das Speichern ist offen fuer neue
           Komponentenklassen, die KLASSE ist es nicht. Eine neue Komponente,
           die bei der Grosskundengrenze mitreden will, braucht weiterhin
           einen Eingriff hier. Diese Naht aufzuloesen ist Woche 12
           (Design-Review, SOLID).
        """
        # Die Pflichtfelder ZUERST und in einem eigenen, engen try-Block
        # (Dienstag). Ein `except KeyError` um den ganzen Konstruktoraufruf
        # herum haette auch KeyErrors gefangen, die tief aus einer Komponente
        # kommen — und die als "Pflichtfeld fehlt" gemeldet, obwohl das
        # Pflichtfeld da war. Dieselbe Ueberdehnung wie beim try-Block in
        # info_eafp() (Woche 7). Die Regel: Der try-Block umfasst genau die
        # Anweisung, deren Fehler das except beschreibt.
        try:
            name = daten["name"]
            email = daten["email"]
            nummer = daten["nummer"]
        except KeyError as e:
            raise DateiInhaltError(
                f"Pflichtfeld fehlt im Kunden-dict: {e.args[0]!r}. "
                f"Vorhanden sind: {sorted(daten)}"
            ) from e

        komponenten = [
            InfoLieferant.aus_dict(eintrag)
            for eintrag in daten.get("komponenten", [])
        ]

        def erste[T: InfoLieferant](typ: type[T]) -> T | None:
            """Die erste Komponente dieser Klasse aus der geladenen Liste.

            Generisch (Kuer Woche 11): [T: InfoLieferant] heisst "T ist
            irgendeine Unterklasse von InfoLieferant — welche, entscheidet der
            Aufruf". erste(GeschaeftsDaten) liefert fuer mypy deshalb
            GeschaeftsDaten | None, nicht bloss InfoLieferant | None. Nur so
            passt das Ergebnis direkt in den Parameter geschaefts_daten des
            Konstruktors. Ohne das Generic muesste man mit cast() nachhelfen.
            """
            return next((k for k in komponenten if isinstance(k, typ)), None)

        kunde = cls(
            name=name,
            email=email,
            nummer=nummer,
            geschaefts_daten=erste(GeschaeftsDaten),
            private_daten=erste(PrivatDaten),
            großkunden_daten=erste(GrosskundenDaten),
            adresse=(
                Adresse.aus_dict(daten["adresse"])
                if daten.get("adresse") is not None
                else None
            ),
            tags=daten.get("tags", []),
        )

        # Komponenten, die in keinen der drei benannten Slots passen — eine
        # kuenftige registrierte Klasse etwa. __init__ kennt sie nicht, also
        # kommen sie ueber denselben Weg herein wie zur Laufzeit. Der
        # Identitaetsvergleich (`is`) statt `==` ist noetig, weil __eq__ seit
        # heute Werte vergleicht: Zwei inhaltsgleiche PrivatDaten waeren
        # gleich, und die zweite wuerde faelschlich als "schon drin" gelten.
        einsortiert = (kunde.geschaefts_daten, kunde.private_daten,
                       kunde.großkunden_daten)
        for komponente in komponenten:
            if not any(komponente is slot for slot in einsortiert):
                kunde.komponente_hinzufuegen(komponente)

        # Werte nachtragen, die __init__ nicht entgegennimmt.
        #
        # Der Umsatz laeuft ueber den Setter; dessen UngueltigerBetragError ist
        # schon ein Fachfehler und bleibt, wie er ist.
        #
        # Der Zustand (Woche 10, Freitag): In der Datei steht der WERT der Enum,
        # zum Beispiel "gesperrt". JSON kennt keine Enums, deshalb schreibt
        # als_dict() zustand.value, und hier uebersetzt KundenZustand(wert)
        # zurueck. Ein unbekannter Wert wirft dort ValueError — aus einer Datei
        # ist das kaputte Eingabe, also DateiInhaltError, und die ValueError
        # bleibt als Ursache erhalten.
        #
        # Alte Dateien (Formatversion 1) kennen stattdessen "aktiv": true/false.
        # Die werden weiter gelesen: true -> AKTIV, false -> INAKTIV. Eine Sperre
        # konnte Version 1 gar nicht ausdruecken, es geht also nichts verloren.
        kunde.umsatz = daten.get("umsatz", 0.0)
        if "zustand" in daten:
            try:
                kunde.zustand = KundenZustand(daten["zustand"])
            except ValueError as e:
                raise DateiInhaltError(
                    f"Feld 'zustand' muss einer von "
                    f"{[z.value for z in KundenZustand]} sein, "
                    f"war: {daten['zustand']!r}"
                ) from e
        else:
            aktiv = daten.get("aktiv", True)
            if not isinstance(aktiv, bool):
                raise DateiInhaltError(
                    f"Feld 'aktiv' muss true oder false sein, war: {aktiv!r}"
                )
            kunde.zustand = KundenZustand.AKTIV if aktiv else KundenZustand.INAKTIV

        Kunde.naechste_nummer = max(Kunde.naechste_nummer, kunde.nummer + 1)

        return kunde

    # Wie die Komponenten gespeichert werden — Entscheidungsweg vom 11.09.2026
    #
    #   Erst gebaut: Typmarker plus Dispatcher. Dann verworfen, weil als_dict()
    #   die drei Komponenten unter ihren eigenen Schluesseln ablegte und der
    #   Marker damit keinen Leser hatte. Dann WIEDER eingefuehrt, und zwar aus
    #   einem anderen Grund als beim ersten Mal: nicht weil die Datenform ihn
    #   erzwingt, sondern weil feste Schluessel das Open-Closed-Principle
    #   verletzen. Bei jeder neuen Komponentenklasse haette Kunde.als_dict()
    #   und Kunde.aus_dict() angefasst werden muessen — eine Klasse, die mit
    #   der neuen Komponente nichts zu tun hat.
    #
    #   Preis, bewusst bezahlt: schwaechere Typisierung. InfoLieferant.aus_dict()
    #   verspricht InfoLieferant, nicht GeschaeftsDaten; wer an `firma` will,
    #   braucht isinstance. Die drei benannten Attribute werden deshalb in
    #   aus_dict() per isinstance aus der Liste herausgesucht.
    #
    #   Was damit NICHT erreicht ist: grosskunde_grenze() liest die drei
    #   Attribute weiterhin namentlich. Das Speichern ist offen, die Klasse
    #   nicht. Diese Naht liegt in __init__, nicht in der Serialisierung —
    #   und ist Thema von Woche 12. test_kunde.py haelt die Grenze als Test
    #   fest, damit sie nicht in Vergessenheit geraet.
    #
    # Notizen liegen NICHT hier drin, sondern in NotizSpeicher (Dienstag).
    # Kriterium: Was in der Registry steht, gehoert zum Kunden; was nicht
    # drinsteht, ist ein Anhang. Die Restluecke davon: komponente_hinzufuegen()
    # nimmt jedes Objekt mit info() an — weder registriert noch Notiz heisst
    # weiterhin "wird nicht gespeichert". Bewusst so gelassen, damit die
    # Luecke sichtbar bleibt statt halb zugedeckt zu werden.
