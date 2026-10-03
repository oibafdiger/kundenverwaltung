"""SQLiteSpeicher: was ueber die Vertragstests in test_speicher.py hinausgeht.

Die Vertragstests zeigen: Derselbe Ablauf liefert mit SQLite dasselbe wie
mit JSON und In-Memory. Hier steht, was nur diese Implementierung betrifft
oder bei ihr besonders leicht schiefgeht (SQL-Sprint, Block 2):

- Round-Trip mit Randdaten (A5): Was geht rein, was kommt raus, was fehlt?
- Waisen in ihrer eigenen Tabelle
- Platzhalter statt f-Strings
- die Transaktion: Abbruch mittendrin laesst den alten Stand stehen
- Fehleruebersetzung: nach aussen nie ein sqlite3.Error
"""

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from kundenverwaltung import (
    Adresse,
    DateiInhaltError,
    DateiNichtLesbarError,
    GeschaeftsDaten,
    GrosskundenDaten,
    InfoLieferant,
    Kunde,
    KundenDatei,
    Kundenliste,
    KundenZustand,
    Notiz,
    NotizSpeicher,
    PrivatDaten,
    SQLiteSpeicher,
    UnbekannteKomponenteError,
    UngueltigerBetragError,
)


@pytest.fixture
def pfad(tmp_path: Path) -> Path:
    return tmp_path / "kunden.db"


@pytest.fixture
def speicher(pfad: Path) -> SQLiteSpeicher:
    return SQLiteSpeicher(str(pfad))


def _zeilen(pfad: Path, sql: str) -> list[tuple[Any, ...]]:
    """Direkt in die Datenbank schauen, am Speicher vorbei.

    Damit pruefen die Tests nicht nur "kommt richtig zurueck", sondern auch
    "steht richtig drin". Beides zusammen zeigt, dass nicht zufaellig zwei
    Fehler einander aufheben.
    """
    with sqlite3.connect(pfad) as con:
        return con.execute(sql).fetchall()


def _neu_laden(speicher: SQLiteSpeicher) -> Kundenliste:
    return speicher.laden().kunden


# --- Leerer Anfang ----------------------------------------------------------

def test_fehlende_datei_ist_leerer_bestand_und_wird_nicht_angelegt(
    speicher: SQLiteSpeicher, pfad: Path
) -> None:
    geladen = speicher.laden()
    assert len(geladen.kunden) == 0 and geladen.waisen == []
    assert not pfad.exists(), "Lesen darf nichts anlegen"


def test_erstes_speichern_legt_datei_und_schema_an(
    speicher: SQLiteSpeicher, pfad: Path
) -> None:
    speicher.speichern(Kundenliste(), NotizSpeicher(), [])
    tabellen = {z[0] for z in _zeilen(pfad, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"kunden", "notizen", "waisen_notizen"} <= tabellen


def test_jede_verbindung_prueft_fremdschluessel(speicher: SQLiteSpeicher) -> None:
    """Das PRAGMA gilt pro Verbindung. _verbinden() ist die einzige Stelle,
    an der eine entsteht, also muss es dort gesetzt sein."""
    con = speicher._verbinden()
    try:
        assert con.execute("PRAGMA foreign_keys").fetchone() == (1,)
    finally:
        con.close()


# --- Round-Trip mit Randdaten (A5) ------------------------------------------

def _randfaelle() -> list[Kunde]:
    """Jeder Kunde deckt einen Fall ab, der beim Uebersetzen verloren gehen koennte."""
    voll = Kunde(
        "Voll", "voll@example.de",
        private_daten=PrivatDaten(1975),
        geschaefts_daten=GeschaeftsDaten("VollCorp", "DE777"),
        großkunden_daten=GrosskundenDaten("Frau Schmidt"),
        # fuehrende Null: als Zahl gespeichert waere aus 01067 die 1067
        adresse=Adresse("Ringstrasse", "7a", "01067", "Dresden"),
        # Reihenfolge und Duplikat muessen beide ueberleben
        tags=["vip", "neu", "stammkunde", "vip"],
    )
    voll.umsatz = 1234.56

    leer = Kunde("Ohne Alles", "leer@example.de")

    gesperrt = Kunde("Gesperrt", "gesperrt@example.de")
    gesperrt.sperren()

    inaktiv = Kunde("Inaktiv", "inaktiv@example.de")
    inaktiv.deaktivieren()

    return [voll, leer, gesperrt, inaktiv]


def test_round_trip_feld_fuer_feld(speicher: SQLiteSpeicher) -> None:
    """Verglichen wird ueber als_dict(), nicht mit ==.

    Kunde.__eq__ vergleicht seit Woche 6 nur die Nummer. Ein == waere also
    auch dann wahr, wenn beim Speichern Adresse, Tags und Zustand verloren
    gegangen waeren. als_dict() enthaelt JEDES gespeicherte Feld, der
    Vergleich der dicts ist deshalb ein Vergleich Feld fuer Feld.
    """
    original = _randfaelle()
    speicher.speichern(Kundenliste(original), NotizSpeicher(), [])

    zurueck = {k.nummer: k.als_dict() for k in _neu_laden(speicher)}
    for kunde in original:
        assert zurueck[kunde.nummer] == kunde.als_dict(), kunde.name


def test_zustand_kommt_als_enum_zurueck(speicher: SQLiteSpeicher) -> None:
    speicher.speichern(Kundenliste(_randfaelle()), NotizSpeicher(), [])
    zustaende = {k.name: k.zustand for k in _neu_laden(speicher)}
    assert zustaende["Gesperrt"] is KundenZustand.GESPERRT
    assert zustaende["Inaktiv"] is KundenZustand.INAKTIV


def test_notizen_behalten_ihre_reihenfolge(speicher: SQLiteSpeicher, pfad: Path) -> None:
    kunde = Kunde("Notizreich", "notiz@example.de")
    for text in ("erste", "zweite", "dritte"):
        kunde.komponente_hinzufuegen(Notiz(text))
    with KundenDatei(speicher) as kunden:
        kunden.hinzufuegen(kunde)

    geladen = speicher.laden()
    assert geladen.speicher.fuer(kunde.nummer) == [Notiz("erste"), Notiz("zweite"), Notiz("dritte")]
    assert _zeilen(pfad, "SELECT position, text FROM notizen ORDER BY position") == [
        (0, "erste"), (1, "zweite"), (2, "dritte"),
    ]


# --- Waisen -----------------------------------------------------------------

def test_waise_landet_in_eigener_tabelle_und_kommt_zurueck(
    speicher: SQLiteSpeicher, pfad: Path
) -> None:
    """Kunde 77 gibt es nicht mehr, seine Notiz bleibt trotzdem erhalten."""
    alte_notizen = NotizSpeicher({77: [Notiz("Kunde 77 ist weg")]})
    speicher.speichern(Kundenliste(), alte_notizen, [77])

    assert _zeilen(pfad, "SELECT kunde_nr, text FROM waisen_notizen") == [(77, "Kunde 77 ist weg")]
    assert _zeilen(pfad, "SELECT COUNT(*) FROM notizen") == [(0,)]

    geladen = speicher.laden()
    assert geladen.waisen == [77]
    assert geladen.speicher.fuer(77) == [Notiz("Kunde 77 ist weg")]


def test_waise_ueberlebt_mehrere_speichervorgaenge(speicher: SQLiteSpeicher) -> None:
    """Der Fall aus dem Review-Fix vom 15.09.2026, jetzt fuer SQLite: Gemeldet
    ist nicht aufbewahrt. Die Waise muss auch das ZWEITE Speichern ueberleben."""
    speicher.speichern(Kundenliste(), NotizSpeicher({77: [Notiz("bleibt")]}), [77])
    with KundenDatei(speicher) as kunden:
        kunden.hinzufuegen(Kunde("Neu", "neu@example.de"))
    assert speicher.laden().speicher.fuer(77) == [Notiz("bleibt")]


# --- Platzhalter statt f-Strings --------------------------------------------

@pytest.mark.parametrize("name", [
    "O'Brien",            # ein Apostroph beendet einen SQL-Text (T9 S3)
    "' OR '1'='1",        # der Klassiker der SQL-Injection (T9 S2)
    "Robert'); DROP TABLE kunden; --",
])
def test_name_mit_sql_zeichen_kommt_unveraendert_zurueck(
    speicher: SQLiteSpeicher, name: str
) -> None:
    """Mit f-Strings gaebe es hier Syntaxfehler oder Schlimmeres. Mit
    Platzhaltern ist der Name nur ein Wert und kommt genau so zurueck."""
    speicher.speichern(
        Kundenliste([Kunde(name, "x@example.de"), Kunde("Zweiter", "z@example.de")]),
        NotizSpeicher(), [],
    )
    namen = [k.name for k in _neu_laden(speicher)]
    assert namen == [name, "Zweiter"]


# --- Die Transaktion --------------------------------------------------------

def test_abbruch_mittendrin_laesst_alten_stand_stehen(speicher: SQLiteSpeicher) -> None:
    """Der Kern von Block 2.

    Zwei Kunden mit derselben Nummer: Das erste INSERT gelingt, das zweite
    verletzt den Primaerschluessel. Ohne Transaktion (jedes Statement sofort
    gespeichert) waere die Tabelle jetzt halb neu: der alte Kunde geloescht,
    ein neuer drin. Mit Transaktion wird ALLES zurueckgerollt, auch die
    DELETEs davor.

    Gegenprobe (03.10.2026): Mit isolation_level=None, also ohne
    Transaktion, schlaegt dieser Test fehl. Ohne `with con:` bleibt er
    dagegen gruen, weil close() die nie committete Transaktion verwirft
    (T7 S3). `with con:` macht das ausdruecklich, statt es dem Zufall der
    Aufraeumreihenfolge zu ueberlassen.
    """
    with KundenDatei(speicher) as kunden:
        kunden.hinzufuegen(Kunde("Alt", "alt@example.de", nummer=1))

    doppelt = Kundenliste([
        Kunde("Neu Eins", "eins@example.de", nummer=5),
        Kunde("Neu Zwei", "zwei@example.de", nummer=5),
    ])
    with pytest.raises(DateiInhaltError, match="Regel des Schemas"):
        speicher.speichern(doppelt, NotizSpeicher(), [])

    assert [k.name for k in _neu_laden(speicher)] == ["Alt"]


def test_unbekannte_komponente_wird_vor_dem_schreiben_abgelehnt(
    speicher: SQLiteSpeicher,
) -> None:
    """Der Preis von "eine Tabelle pro Klasse": Eine neue Komponentenklasse
    kennt SQLiteSpeicher nicht. Bei JSON uebersteht sie den Round-Trip (siehe
    test_persistenz.py), hier wird laut abgelehnt statt still verloren."""

    class VertragsDaten(InfoLieferant, key="vertrag_sql"):
        def __init__(self, monate: int) -> None:
            self.monate = monate

        def info(self) -> str:
            return f"Vertrag: {self.monate} Monate"

        def label(self) -> str:
            return "Typ: Vertrag"

        def felder(self) -> dict[str, Any]:
            return {"monate": self.monate}

        @classmethod
        def aus_felder(cls, daten: dict[str, Any]) -> "VertragsDaten":
            return cls(daten["monate"])

    try:
        with KundenDatei(speicher) as kunden:
            kunden.hinzufuegen(Kunde("Vorher", "vorher@example.de"))

        kunde = Kunde("Vertrag", "vertrag@example.de")
        kunde.komponente_hinzufuegen(VertragsDaten(24))
        with pytest.raises(UnbekannteKomponenteError, match="vertrag_sql"):
            speicher.speichern(Kundenliste([kunde]), NotizSpeicher(), [])

        assert [k.name for k in _neu_laden(speicher)] == ["Vorher"]
    finally:
        # Die Registry ist global, siehe test_persistenz.py.
        InfoLieferant.registry.pop("vertrag_sql", None)


# --- Fehleruebersetzung -----------------------------------------------------

def test_datei_ohne_datenbank_wird_gemeldet_nicht_ueberschrieben(
    speicher: SQLiteSpeicher, pfad: Path
) -> None:
    pfad.write_text("das ist keine Datenbank, sondern eine Einkaufsliste", encoding="utf-8")
    with pytest.raises(DateiInhaltError) as info:
        speicher.laden()
    assert isinstance(info.value.__cause__, sqlite3.DatabaseError)
    assert "Einkaufsliste" in pfad.read_text(encoding="utf-8")


def test_fehlender_ordner_wird_zu_eigenem_fehler(tmp_path: Path) -> None:
    speicher = SQLiteSpeicher(str(tmp_path / "gibt_es_nicht" / "kunden.db"))
    with pytest.raises(DateiNichtLesbarError) as info:
        speicher.speichern(Kundenliste(), NotizSpeicher(), [])
    assert isinstance(info.value.__cause__, sqlite3.OperationalError)


@pytest.fixture
def ungueltiger_bestand(pfad: Path, speicher: SQLiteSpeicher) -> Iterator[None]:
    """Ein Bestand, den Python nie schreiben wuerde: negativer Umsatz,
    an der Klasse vorbei direkt in die Datenbank geschrieben. Das CHECK im
    Schema wuerde das verhindern, deshalb wird es fuer diese eine Verbindung
    mit PRAGMA ignore_check_constraints ausgehebelt. So koennte ein anderes
    Programm oder ein Fehler von Hand die Datei veraendert haben."""
    speicher.speichern(Kundenliste([Kunde("Echt", "echt@example.de", nummer=1)]), NotizSpeicher(), [])
    with sqlite3.connect(pfad) as con:
        con.execute("PRAGMA ignore_check_constraints = ON")
        con.execute("UPDATE kunden SET umsatz = -5 WHERE nummer = 1")
    yield


def test_beim_laden_gelten_dieselben_pruefungen_wie_bei_json(
    speicher: SQLiteSpeicher, ungueltiger_bestand: None
) -> None:
    """Kunde.aus_dict() baut die Objekte, nicht eigener Code. Deshalb wird ein
    kaputter Wert aus der Datenbank genauso abgewiesen wie aus einer Datei,
    und zwar mit dem Fachfehler, nicht als Datenbankfehler."""
    with pytest.raises(UngueltigerBetragError):
        speicher.laden()
