"""Datenmodell: dataclass, frozen, __post_init__, Enum — und bewusst keine dataclass."""

from dataclasses import FrozenInstanceError, is_dataclass, replace

import pytest

from kundenverwaltung import (
    Adresse,
    Fehlerprotokoll,
    Kunde,
    Kundenliste,
    KundenZustand,
    Notiz,
    UngueltigeAdresseError,
)


# --- dataclass und frozen --------------------------------------------------

def test_adresse_bekommt_init_repr_und_eq_vom_dekorator() -> None:
    adresse = Adresse("Weg", "1", "24103", "Kiel")
    assert repr(adresse) == "Adresse(strasse='Weg', hausnummer='1', plz='24103', stadt='Kiel')"
    assert adresse == Adresse("Weg", "1", "24103", "Kiel")
    assert adresse != Adresse("Weg", "2", "24103", "Kiel")


def test_eingefrorene_adresse_laesst_sich_nicht_aendern() -> None:
    adresse = Adresse("Weg", "1", "24103", "Kiel")
    with pytest.raises(FrozenInstanceError, match="plz"):
        adresse.plz = "10115"  # type: ignore[misc]


def test_umzug_heisst_neue_adresse() -> None:
    """Unveraenderliche Werte kann man teilen: Der Umzug des einen Kunden nimmt
    den anderen nicht mit."""
    gemeinsam = Adresse("Ringstrasse", "7", "20095", "Hamburg")
    a = Kunde("A", "a@example.de", adresse=gemeinsam)
    b = Kunde("B", "b@example.de", adresse=gemeinsam)
    a.adresse = replace(gemeinsam, hausnummer="9")
    assert b.adresse is not None and b.adresse.hausnummer == "7"


def test_frozen_macht_hashbar() -> None:
    """Ein Hash darf sich nicht aendern, solange das Objekt im set liegt —
    bei eingefrorenen Feldern ist das garantiert."""
    assert len({Adresse("Weg", "1", "24103", "Kiel"), Adresse("Weg", "1", "24103", "Kiel")}) == 1
    assert len({Notiz("x"), Notiz("x")}) == 1


def test_protokolle_teilen_keine_liste() -> None:
    """field(default_factory=list) statt = [] — die Mutable-Default-Falle."""
    erstes, zweites = Fehlerprotokoll("A"), Fehlerprotokoll("B")
    erstes.meldungen.append("nur bei A")
    assert zweites.meldungen == []


def test_kunde_ist_bewusst_keine_dataclass() -> None:
    """Adresse und Notiz tragen Daten. Kunde bewacht sie — Validierung,
    Nummernzaehler, Gleichheit ueber die Nummer. Dafuer passt eine normale
    Klasse; als dataclass nachgebaut brachen sechs Stellen."""
    assert is_dataclass(Adresse) and is_dataclass(Notiz)
    assert not is_dataclass(Kunde)


# --- __post_init__ ---------------------------------------------------------

@pytest.mark.parametrize(
    "felder",
    [
        ("", "1", "24103", "Kiel"),
        ("Weg", "   ", "24103", "Kiel"),
        ("Weg", "1", "24103", ""),
    ],
    ids=["strasse-leer", "hausnummer-leerzeichen", "stadt-leer"],
)
def test_leere_adressfelder_werden_abgewiesen(felder: tuple[str, str, str, str]) -> None:
    with pytest.raises(UngueltigeAdresseError):
        Adresse(*felder)


def test_pruefung_greift_auch_bei_replace() -> None:
    """replace() baut ueber __init__ neu — und laeuft damit durch __post_init__."""
    with pytest.raises(UngueltigeAdresseError, match="plz"):
        replace(Adresse("Weg", "1", "24103", "Kiel"), plz="")


def test_leere_strasse_aus_einer_datei_ist_ein_fachfehler() -> None:
    """Weil die Pruefung am Konstruktor sitzt, erwischt sie auch das Laden."""
    with pytest.raises(UngueltigeAdresseError):
        Kundenliste.aus_dict({"version": 2, "kunden": [{
            "name": "X", "email": "x@example.de", "nummer": 8201,
            "adresse": {"strasse": "", "hausnummer": "1", "plz": "24103", "stadt": "Kiel"},
        }]})


# --- Enum statt bool -------------------------------------------------------

def test_drei_zustaende_die_ein_bool_nicht_ausdruecken_kann() -> None:
    kunde = Kunde("Zustand", "zustand@example.de")
    kunde.umsatz = 500
    assert kunde.zustand is KundenZustand.AKTIV and kunde.aktiv

    kunde.deaktivieren()
    assert kunde.status() == "inaktiv" and not kunde.aktiv

    kunde.sperren()
    assert kunde.status() == "gesperrt" and not kunde.aktiv

    kunde.aktivieren()
    assert kunde.status() == "Kunde ist ein normaler Kunde"


def test_aktiv_ist_nur_noch_lesbar(kunde: Kunde) -> None:
    """Mit Setter gaebe es zwei Wege, denselben Zustand zu schreiben — und
    `aktiv = True` haette einen gesperrten Kunden still entsperrt."""
    kunde.sperren()
    with pytest.raises(AttributeError):
        kunde.aktiv = True  # type: ignore[misc]
    assert kunde.zustand is KundenZustand.GESPERRT


def test_nur_bekannte_zustandswerte() -> None:
    assert KundenZustand("gesperrt") is KundenZustand.GESPERRT
    with pytest.raises(ValueError):
        KundenZustand("geloescht")
