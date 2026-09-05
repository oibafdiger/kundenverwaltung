"""Gemeinsame Testbausteine.

Fixtures ersetzen die Objekte, die im urspruenglichen Testskript einfach
nacheinander im Modul angelegt wurden. Jeder Test bekommt frische Exemplare
und haengt damit nicht mehr an der Reihenfolge der Zeilen.
"""

from pathlib import Path

import pytest

from kundenverwaltung import (
    Adresse,
    GeschaeftsDaten,
    GrosskundenDaten,
    Kunde,
    Kundenliste,
    PrivatDaten,
)


@pytest.fixture
def kunde() -> Kunde:
    """Ein Kunde ohne Komponenten."""
    return Kunde("Anna Beispiel", "anna@example.de")


@pytest.fixture
def geschaeftskunde() -> Kunde:
    return Kunde(
        "BigCorp", "kontakt@bigcorp.de",
        geschaefts_daten=GeschaeftsDaten("BigCorp GmbH", "DE123456789"),
    )


@pytest.fixture
def grosskunde() -> Kunde:
    return Kunde(
        "MegaCorp", "kontakt@megacorp.de",
        geschaefts_daten=GeschaeftsDaten("MegaCorp AG", "DE555"),
        großkunden_daten=GrosskundenDaten("Frau Mueller"),
    )


@pytest.fixture
def vollstaendiger_kunde() -> Kunde:
    """Ein Kunde mit allen vier Komponenten — fuer repr- und info-Tests."""
    return Kunde(
        "Vollstaendig", "voll@example.de",
        geschaefts_daten=GeschaeftsDaten("VollCorp", "DE777"),
        private_daten=PrivatDaten(1975),
        großkunden_daten=GrosskundenDaten("Frau Schmidt"),
        adresse=Adresse("Ringstrasse", "7", "20095", "Hamburg"),
    )


@pytest.fixture
def kundenliste() -> Kundenliste:
    """Drei Kunden mit aufsteigendem Umsatz: 50, 10.000, 100.000."""
    klein = Kunde("Klein", "klein@example.de")
    mittel = Kunde("Mittel", "mittel@example.de")
    gross = Kunde("Gross", "gross@example.de")
    klein.umsatz = 50
    mittel.umsatz = 10_000
    gross.umsatz = 100_000
    return Kundenliste([klein, mittel, gross])


@pytest.fixture
def beispiel_csv() -> Path:
    """Die mitgelieferte Beispieldatei: drei gute und drei kaputte Zeilen."""
    return Path(__file__).parent.parent / "beispieldaten" / "kunden.csv"
