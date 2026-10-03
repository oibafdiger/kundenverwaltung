"""Das Datenbankschema (SQL-Sprint, Block 1).

Diese Tests pruefen schema.sql DIREKT, ohne SQLiteSpeicher: Lehnt die
Datenbank selbst ab, was sie ablehnen soll? Damit ist belegt, dass die
Regeln im Schema stehen und nicht nur im Python-Code. Ein anderes Programm,
das in dieselbe Datei schreibt, kommt an ihnen nicht vorbei.

Jeder Test bekommt eine frische In-Memory-Datenbank (Fixture `db`). Kein Test
sieht die Zeilen eines anderen.
"""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

import kundenverwaltung

# Der Pfad wird aus dem Paket abgeleitet, nicht aus dem Testordner. So stimmt
# er im Vault und im Portfolio-Repo (gleicher Grund wie in test_paket.py).
SCHEMA = Path(kundenverwaltung.__file__).parent / "schema.sql"


@pytest.fixture
def db() -> Iterator[sqlite3.Connection]:
    """Leere Datenbank mit Schema und eingeschalteten Fremdschluesseln."""
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    con.execute("INSERT INTO kunden (nummer, name, email) VALUES (1000, 'Anna', 'a@x.de')")
    yield con
    con.close()


def test_schema_legt_alle_tabellen_an(db: sqlite3.Connection) -> None:
    tabellen = {zeile[0] for zeile in db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    )}
    assert tabellen == {
        "kunden", "kunden_tags", "notizen", "waisen_notizen",
        "privat_daten", "geschaefts_daten", "grosskunden_daten",
    }


# --- Fremdschluessel ---------------------------------------------------------

def test_notiz_ohne_kunden_wird_abgelehnt(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        db.execute("INSERT INTO notizen VALUES (99, 0, 'verwaist')")


def test_kunde_mit_notizen_laesst_sich_nicht_loeschen(db: sqlite3.Connection) -> None:
    db.execute("INSERT INTO notizen VALUES (1000, 0, 'hallo')")
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        db.execute("DELETE FROM kunden WHERE nummer = 1000")


def test_waise_braucht_keinen_kunden(db: sqlite3.Connection) -> None:
    """Weg (b): waisen_notizen hat bewusst keinen Fremdschluessel."""
    db.execute("INSERT INTO waisen_notizen VALUES (99, 0, 'Kunde 99 ist weg')")
    assert db.execute("SELECT COUNT(*) FROM waisen_notizen").fetchone() == (1,)


def test_ohne_pragma_prueft_sqlite_nichts() -> None:
    """Der Stolperstein aus Block 1, als Test festgehalten.

    Ohne PRAGMA foreign_keys = ON nimmt SQLite die verwaiste Notiz
    klaglos an. Deshalb muss SQLiteSpeicher das PRAGMA bei JEDER Verbindung
    setzen.
    """
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    con.execute("INSERT INTO notizen VALUES (99, 0, 'verwaist')")
    assert con.execute("SELECT COUNT(*) FROM notizen").fetchone() == (1,)
    con.close()


# --- STRICT: Typen werden geprueft wie in PostgreSQL --------------------------

def test_text_in_integer_spalte_wird_abgelehnt(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.Error, match="cannot store TEXT"):
        db.execute("INSERT INTO privat_daten VALUES (1000, 'neunzehnhundert')")


# --- CHECK: dieselben Regeln wie in den Klassen ------------------------------

@pytest.mark.parametrize("sql", [
    # zustand: nur die drei Werte von KundenZustand
    "INSERT INTO kunden (nummer, name, email, zustand) VALUES (1, 'B', 'b@x.de', 'gesprerrt')",
    # name: nicht leer, auch nicht nur Leerzeichen (wie Kunde.__init__)
    "INSERT INTO kunden (nummer, name, email) VALUES (1, '   ', 'b@x.de')",
    # umsatz: nicht negativ (wie der umsatz-Setter)
    "INSERT INTO kunden (nummer, name, email, umsatz) VALUES (1, 'B', 'b@x.de', -1)",
    # Adresse: alle vier oder keins
    "INSERT INTO kunden (nummer, name, email, strasse) VALUES (1, 'B', 'b@x.de', 'Weg')",
    # Adresse: kein Feld nur aus Leerzeichen (wie Adresse.__post_init__)
    "INSERT INTO kunden VALUES (1, 'B', 'b@x.de', 0, 'aktiv', 'Weg', '1', '12345', '  ')",
])
def test_check_lehnt_ungueltige_kunden_ab(db: sqlite3.Connection, sql: str) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        db.execute(sql)


def test_kunde_mit_vollstaendiger_adresse_ist_gueltig(db: sqlite3.Connection) -> None:
    db.execute(
        "INSERT INTO kunden VALUES (1, 'B', 'b@x.de', 5, 'gesperrt', "
        "'Weg', '1', '01067', 'Dresden')"
    )
    # Die fuehrende Null der PLZ bleibt erhalten, weil die Spalte TEXT ist.
    assert db.execute("SELECT plz FROM kunden WHERE nummer = 1").fetchone() == ("01067",)


# --- Primaerschluessel -------------------------------------------------------

def test_komponente_hoechstens_einmal_pro_kunde(db: sqlite3.Connection) -> None:
    db.execute("INSERT INTO privat_daten VALUES (1000, 1980)")
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        db.execute("INSERT INTO privat_daten VALUES (1000, 1990)")


def test_notizen_werden_ueber_den_primaerschluessel_gefunden(db: sqlite3.Connection) -> None:
    """Kein eigener Index auf notizen.kunde_nr noetig.

    Der Primaerschluessel (kunde_nr, position) hat einen Index, und kunde_nr
    ist dessen erste Spalte. Der Plan zeigt SEARCH statt SCAN.
    """
    plan = db.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM notizen WHERE kunde_nr = 1000"
    ).fetchall()
    beschreibung = plan[0][3]
    assert beschreibung.startswith("SEARCH notizen USING INDEX")
