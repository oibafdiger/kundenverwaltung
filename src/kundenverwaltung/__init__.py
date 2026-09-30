"""Kundenverwaltung — ein OOP-Lernprojekt in Python.

Die oeffentliche Schnittstelle des Pakets. Wer `from kundenverwaltung import
Kunde` schreibt, soll nicht wissen muessen, in welchem Modul die Klasse liegt.

__all__ (Woche 11) legt fest, was dazugehoert. Es steuert zwei Dinge:
`from kundenverwaltung import *` holt genau diese Namen, und Werkzeuge wie
mypy und Editoren lesen daraus, was oeffentlich ist. Hilfsfunktionen mit
Unterstrich (_beide_laden) und interne Typen (Geladen) stehen bewusst nicht
drin — wer sie braucht, importiert sie ausdruecklich aus ihrem Modul.
"""

from .csv_format import KundenCsv
from .dateien import json_atomar_schreiben
from .exceptions import (
    CsvFormatError,
    DateiInhaltError,
    DateiNichtGefundenError,
    DateiNichtLesbarError,
    KundeNichtGefundenError,
    KundenverwaltungError,
    UnbekannteKomponenteError,
    UngueltigeAdresseError,
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
from .kunde import Kunde, KundenZustand
from .kundenliste import Kundenliste, KundenlisteIterator
from .notizen import NotizSpeicher
from .persistenz import KundenDatei, kunden_datei
from .protokoll import Fehlerprotokoll
from .speicher import (
    DateiSpeicher,
    Geladen,
    InMemorySpeicher,
    JSONNotizSpeicher,
    JSONSpeicher,
    Speicher,
)
from .validierung import email_gueltig

__all__ = [
    "Adresse",
    "CsvFormatError",
    "DateiSpeicher",
    "DateiInhaltError",
    "DateiNichtGefundenError",
    "DateiNichtLesbarError",
    "Fehlerprotokoll",
    "Geladen",
    "GeschaeftsDaten",
    "GrosskundenDaten",
    "InMemorySpeicher",
    "InfoFaehig",
    "InfoLieferant",
    "JSONNotizSpeicher",
    "JSONSpeicher",
    "Kunde",
    "KundenCsv",
    "KundenDatei",
    "KundeNichtGefundenError",
    "Kundenliste",
    "KundenlisteIterator",
    "KundenverwaltungError",
    "KundenZustand",
    "Notiz",
    "NotizSpeicher",
    "Speicher",
    "PrivatDaten",
    "UnbekannteKomponenteError",
    "UngueltigeAdresseError",
    "UngueltigeEmailError",
    "UngueltigerBetragError",
    "UngueltigerNameError",
    "email_gueltig",
    "json_atomar_schreiben",
    "kunden_datei",
]
