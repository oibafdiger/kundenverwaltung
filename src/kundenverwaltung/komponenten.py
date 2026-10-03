"""Komponenten, die ein Kunde haben kann.

InfoLieferant ist der nominale Vertrag (ABC) mit Registry und Factory,
InfoFaehig das strukturelle Gegenstueck (Protocol) fuer die Grenze, an der
Kunde Fremdes annimmt. Notiz zeigt bewusst, dass beides nebeneinander geht."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, fields
from typing import Any, Protocol, runtime_checkable

from .exceptions import UnbekannteKomponenteError, UngueltigeAdresseError


# ============================================================================
# Abstrakte-Klasse
# ============================================================================
class InfoLieferant(ABC):
    """Nominaler Vertrag fuer Komponenten, die zu einem Kunden gehoeren.

    Die Registry macht die Menge dieser Komponenten OFFEN: Eine neue Klasse
    traegt sich beim Erben selbst ein und ist damit erzeugbar UND speicherbar,
    ohne dass Kunde davon erfaehrt. Das ist das Open-Closed-Principle —
    offen fuer Erweiterung, geschlossen fuer Aenderung.

    Seit Woche 9 entscheidet die Registry-Mitgliedschaft ausserdem, WO etwas
    gespeichert wird: Was hier eingetragen ist, gehoert zum Kunden und landet
    in seinem dict. Was nicht eingetragen ist — Notiz zum Beispiel, bewusst
    per Duck Typing draussen — ist ein Anhang und bekommt einen eigenen
    Speicher. Aus einem Factory-Detail ist damit ein Zugehoerigkeitskriterium
    geworden.
    """

    registry: dict[str, type["InfoLieferant"]] = {}

    # Der eigene Registry-Schluessel, gesetzt von __init_subclass__. Damit
    # muss als_dict() ihn nicht ein zweites Mal hinschreiben: er steht nur in
    # der Klassenzeile (key="privat"), sonst nirgends.
    registry_key: str = ""

    @abstractmethod
    def info(self) -> str:
        """Muss jede Subklasse implementieren"""

    @abstractmethod
    def label(self) -> str:
        """Muss jede Subklasse implementieren"""

    @abstractmethod
    def felder(self) -> dict[str, Any]:
        """Die eigenen Daten als dict — ohne Typmarker, den setzt als_dict().

        Warum abstrakt und nicht einfach in jeder Klasse ein volles
        als_dict()? Weil der Marker sonst in jeder Unterklasse von Hand
        gesetzt werden muesste und beim Anlegen der naechsten Klasse
        vergessen wird. So kann eine Unterklasse ihn gar nicht vergessen:
        Sie liefert nur ihre Felder, den Rahmen macht die Basisklasse.
        """

    def als_dict(self) -> dict[str, Any]:
        """Selbstbeschreibendes dict: Typmarker plus die eigenen Felder.

        Der Marker ist noetig, weil alle Komponenten gemischt in EINER Liste
        stehen. Nur er sagt beim Laden, welche Klasse zu bauen ist. Bei
        Adresse ist das anders — die steht unter ihrem eigenen Schluessel,
        dort waere ein Marker totes Gewicht.
        """
        return {"typ": self.registry_key, **self.felder()}

    @classmethod
    @abstractmethod
    def aus_felder(cls, daten: dict[str, Any]) -> "InfoLieferant":
        """Gegenstueck zu felder(): baut die Instanz aus ihren eigenen Daten."""

    def __init_subclass__(cls, key: str | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if key is not None:
            InfoLieferant.registry[key] = cls
            cls.registry_key = key

    @classmethod
    def erzeugt(cls, key: str, *args: Any, **kwargs: Any) -> "InfoLieferant":
        try:
            klasse = cls.registry[key]
        except KeyError:
            raise UnbekannteKomponenteError(
                f"Unbekannte Komponente: {key!r}. Bekannt: {sorted(cls.registry)}"
            ) from None
        return klasse(*args, **kwargs)

    @staticmethod
    def aus_dict(daten: dict[str, Any]) -> "InfoLieferant":
        """Der Dispatcher: aus einem getaggten dict wird wieder ein Objekt.

        Das Gegenstueck zu als_dict() und der Grund, warum die Menge der
        Komponenten offen sein kann. Kunde muss keine einzige Komponentenklasse
        kennen — er reicht jedes Listenelement hier durch.

        Delegiert an aus_felder() der gefundenen Klasse, NICHT an erzeugt():
        erzeugt() reicht die Werte an den Konstruktor durch und koppelt damit
        die Schluessel in der Datei an die Parameternamen. Ein umbenannter
        Konstruktorparameter wuerde das Laden alter Dateien lautlos brechen.
        aus_felder() haelt diese Uebersetzung dort, wo die Felder zu Hause
        sind.
        """
        typ = daten.get("typ")
        if not isinstance(typ, str):
            raise UnbekannteKomponenteError(
                f"Komponente ohne Typmarker: {daten!r}"
            )
        try:
            klasse = InfoLieferant.registry[typ]
        except KeyError:
            raise UnbekannteKomponenteError(
                f"Unbekannte Komponente: {typ!r}. "
                f"Bekannt: {sorted(InfoLieferant.registry)}"
            ) from None
        return klasse.aus_felder(daten)


# ============================================================================
# Protocol (strukturell) — beschreibt die Grenze, an der Kunde Fremdes annimmt
# ============================================================================
@runtime_checkable
class InfoFaehig(Protocol):
    """Strukturell statt nominal: Wer info() kann, erfuellt das Protocol —
    ohne von irgendetwas erben zu muessen. Deckt damit sowohl die
    InfoLieferant-Komponenten ab als auch Klassen wie Notiz, die bewusst
    ausserhalb des ABC-Vertrags stehen."""

    def info(self) -> str: ...


class PrivatDaten(InfoLieferant, key="privat"):

    def __init__(self, geburtsjahr: int) -> None:
        self.geburtsjahr = geburtsjahr

    def info(self) -> str:
        return f"Geburtsjahr: {self.geburtsjahr}"

    def label(self) -> str:
        return "Typ: Privatkunde"

    def __repr__(self) -> str:
        return f"PrivatDaten({self.geburtsjahr!r})"

    # --- Serialisierung (Woche 9, Montag) -----------------------------------
    def felder(self) -> dict[str, Any]:
        return {"geburtsjahr": self.geburtsjahr}

    @classmethod
    def aus_felder(cls, daten: dict[str, Any]) -> "PrivatDaten":
        return cls(daten["geburtsjahr"])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PrivatDaten):
            return NotImplemented
        return self.geburtsjahr == other.geburtsjahr

    def __hash__(self) -> int:
        return hash(self.geburtsjahr)


class GeschaeftsDaten(InfoLieferant, key="geschaeft"):
    GROSSKUNDE_GRENZE = 100000

    def __init__(self, firma: str, ust_id: str) -> None:
        self.firma = firma
        self.ust_id = ust_id

    def info(self) -> str:
        return f"Firma: {self.firma} <{self.ust_id}>"

    def label(self) -> str:
        return "Typ: Geschäftskunde"

    def __repr__(self) -> str:
        return f"GeschaeftsDaten({self.firma!r}, {self.ust_id!r})"

    # --- Serialisierung (Woche 9, Montag) -----------------------------------
    def felder(self) -> dict[str, Any]:
        return {"firma": self.firma, "ust_id": self.ust_id}

    @classmethod
    def aus_felder(cls, daten: dict[str, Any]) -> "GeschaeftsDaten":
        return cls(daten["firma"], daten["ust_id"])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GeschaeftsDaten):
            return NotImplemented
        return (self.firma, self.ust_id) == (other.firma, other.ust_id)

    def __hash__(self) -> int:
        return hash((self.firma, self.ust_id))


class GrosskundenDaten(InfoLieferant, key="gross"):
    GROSSKUNDE_GRENZE = 500000

    def __init__(self, betreuer: str) -> None:
        self.betreuer = betreuer

    def info(self) -> str:
        return f"Betreuer: {self.betreuer}"

    def label(self) -> str:
        return "Typ: Grosskunde"

    def __repr__(self) -> str:
        return f"GrosskundenDaten({self.betreuer!r})"

    # --- Serialisierung (Woche 9, Montag) -----------------------------------
    def felder(self) -> dict[str, Any]:
        return {"betreuer": self.betreuer}

    @classmethod
    def aus_felder(cls, daten: dict[str, Any]) -> "GrosskundenDaten":
        return cls(daten["betreuer"])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GrosskundenDaten):
            return NotImplemented
        return self.betreuer == other.betreuer

    def __hash__(self) -> int:
        return hash(self.betreuer)


@dataclass(frozen=True)
class Adresse:
    """Komposition: Kunde hat-eine Adresse.

    Seit Woche 10 eine dataclass. Vorher standen __init__, __repr__, __eq__
    und __hash__ von Hand hier — die Klasse sagt jetzt nur noch, WAS eine
    Adresse ist.

    WARUM frozen (Dienstag)
        Eine Adresse ist ein Wert, kein Gegenstand mit Lebenslauf. Wer
        umzieht, bekommt eine NEUE: dataclasses.replace(adresse, plz="10115").
        Deshalb koennen sich zwei Kunden gefahrlos dieselbe Adresse teilen —
        zieht einer um, bekommt nur er ein neues Objekt.

        Nebenwirkung, die hier gebraucht wird: Erst frozen macht die Klasse
        wieder hashbar, nachdem @dataclass mit eq=True __hash__ sonst auf
        None setzt.

    Grenze: frozen ist eine Zusage, kein Tresor. object.__setattr__ kommt
    trotzdem durch. Es schuetzt vor Versehen, nicht vor Absicht.
    """

    strasse: str
    hausnummer: str
    plz: str
    stadt: str

    def __post_init__(self) -> None:
        """Pruefung beim Bauen (Kuer Woche 10), direkt nach dem erzeugten __init__.

        Warum hier und nicht in Settern wie bei Kunde.email: Adresse ist
        frozen. Eine einmal gueltige Adresse bleibt gueltig, und auch
        replace() laeuft ueber __init__ wieder hier durch. Bei einer
        VERAENDERBAREN dataclass waere das eine Luecke — als Test
        festgehalten.

        fields(self) statt einer festen Liste der vier Namen: Kommt ein Feld
        dazu, wird es automatisch mitgeprueft.
        """
        for feld in fields(self):
            wert = getattr(self, feld.name)
            if not isinstance(wert, str) or not wert.strip():
                raise UngueltigeAdresseError(
                    f"Adresse: {feld.name} muss ein nicht-leerer Text sein, war: {wert!r}"
                )

    def __str__(self) -> str:
        return f"{self.strasse} {self.hausnummer}, {self.plz} {self.stadt}"

    # --- Serialisierung (Woche 9, Montag) -----------------------------------
    def als_dict(self) -> dict[str, Any]:
        """Nur die vier Felder, kein Typmarker.

        Eine Adresse steht in Kunde.als_dict() unter dem festen Schluessel
        "adresse", und dort wird sie auch wieder hervorgeholt. Der PLATZ sagt
        schon, was das Ding ist — ein zusaetzliches "typ": "adresse" haette
        keinen Leser.

        Regel dahinter (Woche 9): Ein Typmarker lohnt genau dann, wenn an
        derselben Stelle verschiedene Klassen stehen koennen — etwa in einer
        gemischten Liste. Steht jede Klasse unter ihrem eigenen Schluessel,
        ist er totes Gewicht.
        """
        return {
            "strasse": self.strasse,
            "hausnummer": self.hausnummer,
            "plz": self.plz,
            "stadt": self.stadt,
        }

    @classmethod
    def aus_dict(cls, daten: dict[str, Any]) -> "Adresse":
        return cls(
            daten["strasse"], daten["hausnummer"], daten["plz"], daten["stadt"]
        )


@dataclass(frozen=True)
class Notiz:
    """Duck Typing: keine gemeinsame Basisklasse mit PrivatDaten/GeschaeftsDaten/
    GrosskundenDaten, aber dieselbe info()-Schnittstelle — Kunde.info() behandelt
    sie trotzdem gleich, weil nur die Methode zaehlt, nicht der Typ.

    Seit Woche 10 eine eingefrorene dataclass, aus demselben Grund wie
    Adresse: Eine Notiz ist ein Wert. Wer etwas anderes notieren will, legt
    eine neue Notiz an. __init__, __repr__, __eq__ und __hash__ erzeugt der
    Dekorator — vorher standen vier Methoden von Hand hier.
    """

    text: str

    def info(self) -> str:
        return f"Notiz: {self.text}"

    # --- Serialisierung (Woche 9, Montag) -----------------------------------
    def als_dict(self) -> dict[str, Any]:
        """Nur der Text — der Verweis auf den Kunden kommt von aussen.

        Notizen werden NICHT im Kunden-dict gespeichert (Entscheidung
        11.09.2026): Eine Notiz sagt nichts darueber aus, wer der Kunde ist,
        sie haengt an ihm. Sie bekommt einen eigenen Speicher, und der muss
        die Kundennummer als Verweis mitfuehren — deshalb steht sie hier
        nicht drin. Gebaut wird das am Dienstag, wenn es Dateien gibt.

        Nebenbei sichtbar: der Preis des Duck Typings. Notiz steht bewusst
        ausserhalb von InfoLieferant und taucht in der registry nicht auf.
        Fuer info() war das folgenlos — nur die Methode zaehlte. Zum Bauen
        eines Objekts aus einem dict reicht "hat info()" aber nicht: Es muss
        jemand wissen, WELCHE Klasse zu erzeugen ist. Duck Typing kann mit
        fertigen Objekten umgehen, aber keine herstellen.
        """
        return {"text": self.text}

    @classmethod
    def aus_dict(cls, daten: dict[str, Any]) -> "Notiz":
        return cls(daten["text"])
