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
from .csv_format import KundenCsv
from .kunde import Kunde
from .kundenliste import Kundenliste, KundenlisteIterator
from .protokoll import Fehlerprotokoll

__all__ = [
    "Adresse",
    "CsvFormatError",
    "Fehlerprotokoll",
    "GeschaeftsDaten",
    "GrosskundenDaten",
    "InfoFaehig",
    "InfoLieferant",
    "Kunde",
    "KundenCsv",
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
