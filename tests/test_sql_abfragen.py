"""Abfragen, die JSON nicht kann (SQL-Sprint, Block 3).

Ein fester Bestand, an dem jede Falle aus der Einstufung sichtbar wuerde:

    nummer  name   ort        zustand   umsatz  Notizen
    1       Anna   Berlin     aktiv     100     3
    2       Bernd  Hamburg    aktiv     200     1
    3       Clara  (keiner)   gesperrt   50     0      <- T1: faellt bei WHERE still raus
    4       Dora   Berlin     inaktiv     0     0      <- T2: COUNT(*) gaebe 1 statt 0
    Waisen: Kunde 77 mit 2 Notizen, Kunde 88 mit 1

Die erwarteten Ergebnisse stehen ausgeschrieben im Test, nicht berechnet.
Ein Test, der sein Soll mit derselben Logik ausrechnet wie der Code, prueft
nur, ob die Logik mit sich selbst uebereinstimmt.
"""

from pathlib import Path

import pytest

from kundenverwaltung import (
    Adresse,
    Kunde,
    KundeImOrt,
    Kundenliste,
    Notiz,
    NotizAnzahl,
    NotizSpeicher,
    SQLiteSpeicher,
    WaisenAnzahl,
    ZustandUmsatz,
)


def _kunde(nummer: int, name: str, stadt: str | None, umsatz: float, notizen: int) -> Kunde:
    adresse = Adresse("Weg", "1", "10115", stadt) if stadt is not None else None
    kunde = Kunde(name, f"{name.lower()}@example.de", nummer=nummer, adresse=adresse)
    kunde.umsatz = umsatz
    for i in range(notizen):
        kunde.komponente_hinzufuegen(Notiz(f"{name} {i + 1}"))
    return kunde


@pytest.fixture
def speicher(tmp_path: Path) -> SQLiteSpeicher:
    clara = _kunde(3, "Clara", None, 50, 0)
    clara.sperren()
    dora = _kunde(4, "Dora", "Berlin", 0, 0)
    dora.deaktivieren()
    kunden = Kundenliste([
        _kunde(1, "Anna", "Berlin", 100, 3),
        _kunde(2, "Bernd", "Hamburg", 200, 1),
        clara,
        dora,
    ])
    waisen = NotizSpeicher({77: [Notiz("alt 1"), Notiz("alt 2")], 88: [Notiz("alt")]})

    speicher = SQLiteSpeicher(str(tmp_path / "kunden.db"))
    speicher.speichern(kunden, waisen, [77, 88])
    return speicher


def test_kunden_nach_ort_mit_unbekannt(speicher: SQLiteSpeicher) -> None:
    assert speicher.kunden_nach_ort() == [
        KundeImOrt("Berlin", 1, "Anna"),
        KundeImOrt("Berlin", 4, "Dora"),
        KundeImOrt("Hamburg", 2, "Bernd"),
        KundeImOrt("unbekannt", 3, "Clara"),
    ]


def test_notizen_pro_kunde_auch_mit_null(speicher: SQLiteSpeicher) -> None:
    """Clara und Dora MUESSEN mit 0 dabei sein. Und die Waisen (77, 88) duerfen
    nicht auftauchen, sie gehoeren zu keinem Kunden."""
    assert speicher.notizen_pro_kunde() == [
        NotizAnzahl(1, "Anna", 3),
        NotizAnzahl(2, "Bernd", 1),
        NotizAnzahl(3, "Clara", 0),
        NotizAnzahl(4, "Dora", 0),
    ]


@pytest.mark.parametrize("grenze, erwartet", [
    (0, [NotizAnzahl(1, "Anna", 3), NotizAnzahl(2, "Bernd", 1)]),
    (1, [NotizAnzahl(1, "Anna", 3)]),
    (3, []),          # "mehr als 3": Anna mit genau 3 gehoert NICHT dazu
])
def test_kunden_mit_mehr_notizen_als(
    speicher: SQLiteSpeicher, grenze: int, erwartet: list[NotizAnzahl]
) -> None:
    assert speicher.kunden_mit_mehr_notizen_als(grenze) == erwartet


def test_umsatz_pro_zustand(speicher: SQLiteSpeicher) -> None:
    assert speicher.umsatz_pro_zustand() == [
        ZustandUmsatz("aktiv", 2, 300.0),
        ZustandUmsatz("gesperrt", 1, 50.0),
        ZustandUmsatz("inaktiv", 1, 0.0),
    ]


def test_waisen_uebersicht(speicher: SQLiteSpeicher) -> None:
    assert speicher.waisen_uebersicht() == [WaisenAnzahl(77, 2), WaisenAnzahl(88, 1)]


def test_ergebnisse_haben_namen_statt_nur_stellen(speicher: SQLiteSpeicher) -> None:
    """Der Grund fuer die NamedTuples: zeile.anzahl liest sich, zeile[2] nicht."""
    anna = speicher.notizen_pro_kunde()[0]
    assert (anna.name, anna.anzahl) == ("Anna", 3)


def test_abfrage_ohne_datei_ist_leer_und_legt_nichts_an(tmp_path: Path) -> None:
    pfad = tmp_path / "gibt_es_nicht.db"
    speicher = SQLiteSpeicher(str(pfad))
    assert speicher.notizen_pro_kunde() == []
    assert not pfad.exists()
