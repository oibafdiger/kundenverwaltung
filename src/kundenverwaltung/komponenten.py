"""Komponenten, die ein Kunde haben kann.

InfoLieferant ist der nominale Vertrag (ABC) mit Registry und Factory,
InfoFaehig das strukturelle Gegenstueck (Protocol) fuer die Grenze, an der
Kunde Fremdes annimmt. Notiz zeigt bewusst, dass beides nebeneinander geht."""

from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable

from .exceptions import UnbekannteKomponenteError


class InfoLieferant(ABC):
    registry: dict[str, type["InfoLieferant"]] = {}

    @abstractmethod
    def info(self) -> str:
        """Muss jede Subklasse implementieren"""

    @abstractmethod
    def label(self) -> str:
        """Muss jede Subklasse implementieren"""

    def __init_subclass__(cls, key: str | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if key is not None:
            InfoLieferant.registry[key] = cls

    @classmethod
    def erzeugt(cls, key: str, *args: Any, **kwargs: Any) -> "InfoLieferant":
        try:                                  
            klasse = cls.registry[key]
        except KeyError:
            raise UnbekannteKomponenteError(
                f"Unbekannte Komponente: {key!r}. Bekannt: {sorted(cls.registry)}"
            ) from None
        return klasse(*args, **kwargs)

@runtime_checkable
class InfoFaehig(Protocol):
    """Strukturell statt nominal: Wer info() kann, erfuellt das Protocol —
    ohne von irgendetwas erben zu muessen. Deckt damit sowohl die
    InfoLieferant-Komponenten ab als auch Klassen wie Notiz, die bewusst
    ausserhalb des ABC-Vertrags stehen."""

    def info(self) -> str: ...

class PrivatDaten(InfoLieferant, key="privat"):

    def __init__(self, geburtsjahr: int):
        self.geburtsjahr = geburtsjahr

    def info(self) -> str:
        return f"Geburtsjahr: {self.geburtsjahr}"

    def label(self) -> str:
        return "Typ: Privatkunde"

    def __repr__(self) -> str:
        return f"PrivatDaten({self.geburtsjahr!r})"


class GeschaeftsDaten(InfoLieferant, key="geschaeft"):
    GROSSKUNDE_GRENZE = 100000

    def __init__(self, firma: str, ust_id: str):
        self.firma = firma
        self.ust_id = ust_id

    def info(self) -> str:
        return f"Firma: {self.firma} <{self.ust_id}>"

    def label(self) -> str:
        return "Typ: Geschäftskunde"

    def __repr__(self) -> str:
        return f"GeschaeftsDaten({self.firma!r}, {self.ust_id!r})"


class GrosskundenDaten(InfoLieferant, key="gross"):
    GROSSKUNDE_GRENZE = 500000

    def __init__(self, betreuer: str):
        self.betreuer = betreuer

    def info(self) -> str:
        return f"Betreuer: {self.betreuer}"

    def label(self) -> str:
        return "Typ: Grosskunde"

    def __repr__(self) -> str:
        return f"GrosskundenDaten({self.betreuer!r})"


class Adresse:
    """Komposition: Kunde hat-eine Adresse"""

    def __init__(self, strasse: str, hausnummer : str, plz: str, stadt: str):
        self.strasse = strasse
        self.hausnummer = hausnummer
        self.plz = plz
        self.stadt = stadt

    def __str__(self) -> str:
        return f"{self.strasse} {self.hausnummer}, {self.plz} {self.stadt}"

    def __repr__(self) -> str:
        return f"Adresse({self.strasse!r}, {self.hausnummer!r}, {self.plz!r}, {self.stadt!r})"


class Notiz:
    """Duck Typing: keine gemeinsame Basisklasse mit PrivatDaten/GeschaeftsDaten/
    GrosskundenDaten, aber dieselbe info()-Schnittstelle — Kunde.info() behandelt
    sie trotzdem gleich, weil nur die Methode zaehlt, nicht der Typ."""

    def __init__(self, text: str):
        self.text = text

    def info(self) -> str:
        return f"Notiz: {self.text}"

    def __repr__(self) -> str:
        return f"Notiz({self.text!r})"
