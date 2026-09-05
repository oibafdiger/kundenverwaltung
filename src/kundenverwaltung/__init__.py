"""Kundenverwaltung — ein OOP-Lernprojekt in Python.

Die oeffentliche Schnittstelle des Pakets. Wer `from kundenverwaltung import
Kunde` schreibt, soll nicht wissen muessen, in welchem Modul die Klasse liegt.
"""

from .exceptions import (
    CsvFormatError,
    KundeNichtGefundenError,
    KundenverwaltungError,
    UnbekannteKomponenteError,
    UngueltigeEmailError,
    UngueltigerBetragError,
    UngueltigerNameError,
)
from .komponenten import (
    Adresse,
    GeschaeftsDaten,
    GrosskundenDaten,
    InfoFaehig,
    InfoLieferant,
    Notiz,
    PrivatDaten,
)
from .kunde import ExportierbarMixin, Kunde
from .kundenliste import Kundenliste, KundenlisteIterator
from .protokoll import Fehlerprotokoll

__all__ = [
    "Adresse",
    "CsvFormatError",
    "ExportierbarMixin",
    "Fehlerprotokoll",
    "GeschaeftsDaten",
    "GrosskundenDaten",
    "InfoFaehig",
    "InfoLieferant",
    "Kunde",
    "KundeNichtGefundenError",
    "Kundenliste",
    "KundenlisteIterator",
    "KundenverwaltungError",
    "Notiz",
    "PrivatDaten",
    "UnbekannteKomponenteError",
    "UngueltigeEmailError",
    "UngueltigerBetragError",
    "UngueltigerNameError",
]
