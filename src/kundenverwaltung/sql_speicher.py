"""Der Bestand in einer SQLite-Datenbank — die dritte Implementierung von Speicher.

SQL-Sprint, Block 2 (03.10.2026). Das Schema steht in schema.sql, die
Begruendung dafuer in REFACTORING.md, Teil 5.

WAS DIESE IMPLEMENTIERUNG KANN, WAS DateiSpeicher NICHT KANN
    Kunden UND Notizen werden in EINER Transaktion geschrieben. Bricht das
    Speichern mittendrin ab, rollt die Datenbank alles zurueck, und der alte
    Stand bleibt vollstaendig. DateiSpeicher kann nur jede Datei fuer sich
    unteilbar ersetzen; der Docstring von Speicher hat genau diese Luecke
    vorausgesagt.

WIE UEBERSETZT WIRD: UEBER DIE DICTS, NICHT UEBER DIE OBJEKTE
    Gelesen und geschrieben wird dasselbe dict, das auch in der JSON-Datei
    stuende (Kunde.als_dict() / Kunde.aus_dict()). Diese Klasse verteilt es
    nur auf Tabellen und sammelt es wieder ein. Zwei Gruende:

    1. Beim Laden laufen dieselben Pruefungen wie bei JSON: Ein negativer
       Umsatz oder ein unbekannter Zustand wird von aus_dict() abgewiesen,
       nicht von eigenem Code hier, der davon abweichen koennte.
    2. Kein Zugriff auf private Felder (_umsatz, _info_komponenten). Was
       als_dict() nicht liefert, kann auch nicht gespeichert werden, genau
       wie bei JSON und InMemorySpeicher.

ALLES SQLITE-SPEZIFISCHE BLEIBT IN DIESER DATEI
    sqlite3, die ?-Platzhalter, das PRAGMA, der Dateipfad und sqlite3.Error
    tauchen nirgends sonst im Paket auf. Nach aussen kommen nur die eigenen
    Exceptions. Fuer PostgreSQL entstuende daneben eine PostgresSpeicher, und
    der aufrufende Code bliebe unveraendert.

BEKANNTE GRENZEN (bewusst, siehe REFACTORING.md, Teil 5)
    - Eine Tabelle pro Komponentenklasse heisst: Eine NEUE Komponentenklasse
      braucht eine neue Tabelle und einen Eintrag in _KOMPONENTEN. Bis dahin
      wirft speichern() UnbekannteKomponenteError, bevor etwas geschrieben
      wird. Laut statt still: Bei JSON gaebe es diese Grenze nicht.
    - Pro Kunde hoechstens eine Komponente je Klasse (Primaerschluessel).
      Haengt jemand ueber komponente_hinzufuegen() eine zweite PrivatDaten an,
      lehnt die Datenbank das Speichern ab, und der alte Stand bleibt.
    - Die Kunden kommen nach Nummer sortiert zurueck, nicht in der
      Reihenfolge, in der sie gespeichert wurden. Die Kundenliste hat keine
      fachliche Reihenfolge; eine position-Spalte wie bei den Notizen waere
      Aufwand ohne Leser.
"""

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, NamedTuple

from .exceptions import DateiInhaltError, DateiNichtLesbarError, UnbekannteKomponenteError
from .komponenten import Notiz
from .kunde import Kunde
from .kundenliste import Kundenliste
from .notizen import NotizSpeicher
from .speicher import Geladen, Speicher, _notizen_zusammenstellen, _zusammenfuegen

# Das Schema liegt als Datei im Paket. Der Pfad wird aus diesem Modul
# abgeleitet, damit er im Vault und im Portfolio-Repo gleich stimmt.
SCHEMA = Path(__file__).parent / "schema.sql"


# ============================================================================
# Ergebnistypen der Abfragen (Block 3)
# ============================================================================
# Eine Zeile aus der Datenbank ist ein nacktes Tupel: (1000, "Anna", 2). Wer es
# benutzt, muesste sich merken, was an welcher Stelle steht. Ein NamedTuple
# gibt den Stellen Namen (zeile.anzahl statt zeile[2]) und bleibt trotzdem ein
# Tupel. Dieselbe Ueberlegung wie bei Geladen in speicher.py.

class KundeImOrt(NamedTuple):
    ort: str
    nummer: int
    name: str


class NotizAnzahl(NamedTuple):
    nummer: int
    name: str
    anzahl: int


class ZustandUmsatz(NamedTuple):
    zustand: str
    kunden: int
    umsatz: float


class WaisenAnzahl(NamedTuple):
    kunde_nr: int
    notizen: int


class _KomponentenTabelle(NamedTuple):
    """Wie eine Komponentenklasse auf ihre Tabelle abgebildet wird."""

    lesen: str
    schreiben: str
    felder: tuple[str, ...]


# Schluessel ist der registry_key der Klasse ("typ" im dict).
#
# Warum ausgeschriebenes SQL und kein f"INSERT INTO {tabelle} ...":
# Platzhalter (?) gibt es nur fuer WERTE, nicht fuer Tabellen- oder
# Spaltennamen. Wer Namen einsetzen will, muss den SQL-Text zusammenbauen.
# Das waere hier sogar sicher, weil die Namen aus dem Code stammen und nie
# aus einer Eingabe. Ausgeschrieben sieht man aber auf einen Blick, welches
# SQL wirklich laeuft, und kein Leser muss die Sicherheit erst pruefen.
_KOMPONENTEN: dict[str, _KomponentenTabelle] = {
    "privat": _KomponentenTabelle(
        lesen="SELECT kunde_nr, geburtsjahr FROM privat_daten",
        schreiben="INSERT INTO privat_daten (kunde_nr, geburtsjahr) VALUES (?, ?)",
        felder=("geburtsjahr",),
    ),
    "geschaeft": _KomponentenTabelle(
        lesen="SELECT kunde_nr, firma, ust_id FROM geschaefts_daten",
        schreiben="INSERT INTO geschaefts_daten (kunde_nr, firma, ust_id) VALUES (?, ?, ?)",
        felder=("firma", "ust_id"),
    ),
    "gross": _KomponentenTabelle(
        lesen="SELECT kunde_nr, betreuer FROM grosskunden_daten",
        schreiben="INSERT INTO grosskunden_daten (kunde_nr, betreuer) VALUES (?, ?)",
        felder=("betreuer",),
    ),
}

# REIHENFOLGE MIT ABSICHT: erst die Tabellen, die auf kunden verweisen, dann
# kunden selbst. Andersherum lehnte der Fremdschluessel das Loeschen ab,
# solange noch Notizen oder Komponenten auf einen Kunden zeigen.
_ALLES_LOESCHEN = (
    "DELETE FROM notizen",
    "DELETE FROM waisen_notizen",
    "DELETE FROM kunden_tags",
    "DELETE FROM privat_daten",
    "DELETE FROM geschaefts_daten",
    "DELETE FROM grosskunden_daten",
    "DELETE FROM kunden",
)


class SQLiteSpeicher(Speicher):
    """Der Bestand in einer SQLite-Datei.

        with KundenDatei(SQLiteSpeicher("kunden.db")) as kunden:
            ...

    Fehlt die Datei, ist das der erste Programmstart: laden() liefert einen
    leeren Bestand und legt dabei KEINE Datei an. Erst speichern() erzeugt
    sie samt Schema. Eine vorhandene Datei, die keine SQLite-Datenbank ist,
    wird dagegen nicht still ueberschrieben, sondern gemeldet.
    """

    def __init__(self, pfad: str) -> None:
        self.pfad = pfad

    def __repr__(self) -> str:
        return f"SQLiteSpeicher({self.pfad!r})"

    # ------------------------------------------------------------------
    # Die Verbindung
    # ------------------------------------------------------------------
    def _verbinden(self) -> sqlite3.Connection:
        """Die EINZIGE Stelle, an der eine Verbindung geoeffnet wird.

        Deshalb steht das PRAGMA genau hier, direkt nach connect() und vor
        jeder anderen Anweisung: Es gilt nur fuer diese eine Verbindung, und
        innerhalb einer offenen Transaktion waere es wirkungslos. Wer eine
        Verbindung braucht, kommt an dieser Methode nicht vorbei und damit
        auch nicht am PRAGMA.

        Hat die Datei noch kein Schema (neu angelegt), wird es eingespielt.
        Scheitert dabei etwas, wird die Verbindung geschlossen, bevor der
        Fehler weiterfliegt; sonst bliebe sie offen haengen.
        """
        con = sqlite3.connect(self.pfad)
        try:
            con.execute("PRAGMA foreign_keys = ON")
            if not _hat_schema(con):
                con.executescript(SCHEMA.read_text(encoding="utf-8"))
        except BaseException:
            con.close()
            raise
        return con

    # ------------------------------------------------------------------
    # Der Vertrag
    # ------------------------------------------------------------------
    def laden(self) -> Geladen:
        """Alle Tabellen lesen, daraus dieselben dicts bauen wie bei JSON.

        Der try-Block umfasst NUR den Datenbankzugriff. Die Objekte werden
        danach gebaut: Wirft Kunde.aus_dict() einen Fachfehler, ist das
        bereits der richtige Fehler und soll nicht als Datenbankfehler
        gemeldet werden. Dieselbe Regel wie in JSONSpeicher.laden().
        """
        if not Path(self.pfad).exists():
            # Ohne diese Pruefung legte sqlite3.connect() eine leere Datei an.
            # Lesen soll aber nichts veraendern, auch nicht durch Anlegen.
            return _zusammenfuegen(Kundenliste(), NotizSpeicher())

        try:
            with closing(self._verbinden()) as con:
                roh = _alles_lesen(con)
        except sqlite3.Error as e:
            raise _uebersetzen(e, self.pfad, "gelesen") from e

        kunden = Kundenliste([Kunde.aus_dict(daten) for daten in _kunden_dicts(roh)])
        notizen = NotizSpeicher(_notizen_einsammeln(roh))
        # Das Verteilen der Notizen und das Erkennen der Waisen ist fuer jeden
        # Speicher gleich und steht deshalb in speicher.py, nicht hier.
        return _zusammenfuegen(kunden, notizen)

    def speichern(
        self, kunden: Kundenliste, notizen: NotizSpeicher, waisen: list[int]
    ) -> None:
        """Den ganzen Bestand ersetzen, in einer Transaktion.

        ABLAUF
            1. Alles vorbereiten, was scheitern kann, OHNE die Datenbank
               anzufassen: dicts bauen, Komponenten pruefen.
            2. In einer Transaktion alles loeschen und neu schreiben.
               Gelingt alles, wird committet. Fliegt irgendwo eine Exception,
               rollt `with con:` ALLES zurueck.

        WARUM ALLES LOESCHEN UND NEU SCHREIBEN
            Der Vertrag uebergibt immer den GANZEN Bestand, nicht die
            Aenderungen. Herauszufinden, was sich geaendert hat, waere viel
            Code fuer wenig Gewinn. In der Transaktion ist das Loeschen
            ungefaehrlich: Bis zum Commit sieht niemand den Zwischenstand,
            und bei einem Fehler ist er weg. (Bei grossen Bestaenden waere es
            langsam; das ist ein Thema fuer den Performance-Abschnitt.)

        WAISEN
            Eine Regel, und sie macht wahr, was das Schema nicht erzwingen
            kann: Gibt es den Kunden, kommt die Notiz nach `notizen`, sonst
            nach `waisen_notizen`. Hat ein neuer Kunde inzwischen die Nummer
            einer Waise, hat waisen_uebernehmen() die Notizen schon an ihn
            gehaengt, und sie landen richtig in `notizen`.
        """
        # --- 1. Vorbereiten, ohne Datenbank --------------------------------
        neu = _notizen_zusammenstellen(kunden, notizen, waisen)
        kunden_daten: list[dict[str, Any]] = kunden.als_dict()["kunden"]
        notiz_daten: dict[str, list[dict[str, Any]]] = neu.als_dict()["notizen"]
        _komponenten_pruefen(kunden_daten)
        vorhandene_nummern = {daten["nummer"] for daten in kunden_daten}

        # --- 2. Schreiben, in einer Transaktion ----------------------------
        try:
            with closing(self._verbinden()) as con:
                # `with con:` ist die Transaktion: ohne Fehler COMMIT, mit
                # Fehler ROLLBACK. Es schliesst die Verbindung NICHT, das
                # erledigt das closing() aussen herum.
                #
                # Streng genommen ginge es hier auch ohne: sqlite3 oeffnet vor
                # dem ersten DELETE von selbst eine Transaktion, und close()
                # ohne commit() verwirft sie. Darauf soll sich niemand
                # verlassen muessen, der den Code spaeter umbaut. Hier steht
                # deshalb ausdruecklich, was zusammengehoert.
                with con:
                    for sql in _ALLES_LOESCHEN:
                        con.execute(sql)
                    _kunden_schreiben(con, kunden_daten)
                    _notizen_schreiben(con, notiz_daten, vorhandene_nummern)
        except sqlite3.Error as e:
            raise _uebersetzen(e, self.pfad, "geschrieben") from e

    # ------------------------------------------------------------------
    # Abfragen, die JSON nicht kann (Block 3)
    # ------------------------------------------------------------------
    # Nicht Teil des Vertrags: InMemorySpeicher und DateiSpeicher muessen das
    # nicht koennen. Hier liegen sie, weil sie SQL sind, und alles
    # SQLite-Spezifische gehoert in diese Klasse.
    #
    # Die Regel fuer alle: Die RECHENARBEIT steht im SQL. Gezaehlt, summiert,
    # gefiltert und sortiert wird in der Datenbank. Python bekommt nur das
    # fertige Ergebnis und gibt den Spalten Namen. Wer SELECT * holt und in
    # einer Schleife zaehlt, hat die Datenbank nur als Datei benutzt.

    def kunden_nach_ort(self) -> list[KundeImOrt]:
        """Alle Kunden nach Ort, Kunden ohne Adresse unter 'unbekannt'.

        COALESCE nimmt den ersten Wert, der nicht NULL ist. Ohne Adresse ist
        stadt NULL, dann gilt 'unbekannt'. Ein WHERE stadt = ... braeuchte es
        nicht, aber genau dort waere die Falle aus T1: Kunden ohne Adresse
        fielen still heraus.
        """
        zeilen = self._abfragen(
            "SELECT COALESCE(stadt, 'unbekannt') AS ort, nummer, name "
            "FROM kunden "
            "ORDER BY ort, name"
        )
        return [KundeImOrt(*zeile) for zeile in zeilen]

    def notizen_pro_kunde(self) -> list[NotizAnzahl]:
        """Jeder Kunde mit der Zahl seiner Notizen, auch Kunden mit 0.

        Zweimal entscheidet die Spalte (T2 S4 aus der Einstufung):
        - LEFT JOIN, sonst fehlen Kunden ohne Notiz ganz.
        - COUNT(n.position), nicht COUNT(*): Bei einem Kunden ohne Notiz
          liefert der LEFT JOIN EINE Zeile mit NULL in den Notizspalten.
          COUNT(*) zaehlte diese Zeile als 1, COUNT(n.position) zaehlt nur
          Werte, die nicht NULL sind, also 0.
        - GROUP BY ueber den KUNDEN, nicht ueber eine Notizspalte, sonst gaebe
          es eine Zeile pro Notiz.
        Waisen zaehlen nicht mit: Sie stehen in waisen_notizen, nicht in notizen.
        """
        zeilen = self._abfragen(
            "SELECT k.nummer, k.name, COUNT(n.position) AS anzahl "
            "FROM kunden k "
            "LEFT JOIN notizen n ON n.kunde_nr = k.nummer "
            "GROUP BY k.nummer, k.name "
            "ORDER BY k.nummer"
        )
        return [NotizAnzahl(*zeile) for zeile in zeilen]

    def kunden_mit_mehr_notizen_als(self, grenze: int) -> list[NotizAnzahl]:
        """Kunden mit mehr als `grenze` Notizen.

        HAVING statt WHERE: Gefiltert wird auf das Ergebnis von COUNT, und das
        gibt es erst nach GROUP BY (T3 S2). Die Grenze kommt als Platzhalter,
        auch wenn sie nur eine Zahl ist. Die Regel hat keine Ausnahmen.
        """
        zeilen = self._abfragen(
            "SELECT k.nummer, k.name, COUNT(n.position) AS anzahl "
            "FROM kunden k "
            "LEFT JOIN notizen n ON n.kunde_nr = k.nummer "
            "GROUP BY k.nummer, k.name "
            "HAVING COUNT(n.position) > ? "
            "ORDER BY anzahl DESC, k.nummer",
            (grenze,),
        )
        return [NotizAnzahl(*zeile) for zeile in zeilen]

    def umsatz_pro_zustand(self) -> list[ZustandUmsatz]:
        """Pro Zustand: wie viele Kunden, wie viel Umsatz.

        Zwei Aggregate in einer Abfrage. Ein Zustand, den gerade kein Kunde
        hat, erscheint NICHT: GROUP BY kann nur Gruppen bilden, die in den
        Daten vorkommen. Fuer "alle drei, auch mit 0" braeuchte es eine
        Tabelle der Zustaende und einen LEFT JOIN darauf.
        """
        zeilen = self._abfragen(
            "SELECT zustand, COUNT(*) AS kunden, SUM(umsatz) AS umsatz "
            "FROM kunden "
            "GROUP BY zustand "
            "ORDER BY zustand"
        )
        return [ZustandUmsatz(*zeile) for zeile in zeilen]

    def waisen_uebersicht(self) -> list[WaisenAnzahl]:
        """Welche geloeschten Kundennummern haben noch wie viele Notizen?

        Die Frage, fuer die es die eigene Waisen-Tabelle gibt: Sie laesst sich
        jetzt mit einem GROUP BY beantworten, statt beide JSON-Dateien zu
        laden und abzugleichen.
        """
        zeilen = self._abfragen(
            "SELECT kunde_nr, COUNT(*) AS notizen "
            "FROM waisen_notizen "
            "GROUP BY kunde_nr "
            "ORDER BY kunde_nr"
        )
        return [WaisenAnzahl(*zeile) for zeile in zeilen]

    def _abfragen(self, sql: str, werte: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        """Eine lesende Abfrage, mit denselben Regeln wie laden().

        Fehlt die Datei, gibt es nichts zu fragen: leere Liste, und es wird
        keine Datei angelegt. Fehler kommen als eigene Exceptions heraus.
        """
        if not Path(self.pfad).exists():
            return []
        try:
            with closing(self._verbinden()) as con:
                return con.execute(sql, werte).fetchall()
        except sqlite3.Error as e:
            raise _uebersetzen(e, self.pfad, "gelesen") from e


# ============================================================================
# Hilfsfunktionen. Modulebene statt Methoden, weil sie nichts vom Objekt
# brauchen: Sie bekommen eine Verbindung oder Daten und geben Daten zurueck.
# ============================================================================

def _hat_schema(con: sqlite3.Connection) -> bool:
    """Gibt es die Tabelle kunden schon? sqlite_master ist SQLites Inhaltsverzeichnis."""
    zeile = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'kunden'"
    ).fetchone()
    return zeile is not None


def _uebersetzen(
    fehler: sqlite3.Error, pfad: str, was: str
) -> DateiInhaltError | DateiNichtLesbarError:
    """sqlite3.Error -> eigene Exception. Nach aussen geht nie ein sqlite3.Error.

    REIHENFOLGE MIT ABSICHT: IntegrityError und OperationalError sind beide
    Unterklassen von DatabaseError. Stuende die allgemeine Pruefung zuerst,
    kaemen die beiden speziellen nie dran. Dieselbe Falle wie bei
    FileNotFoundError und OSError in JSONSpeicher.laden().

    Die Zuordnung folgt den Docstrings in exceptions.py:
        IntegrityError   eine Regel des Schemas verletzt (z.B. doppelte
                         Kundennummer)                  -> DateiInhaltError
        OperationalError Datei nicht zu oeffnen, gesperrt, Ordner fehlt
                                                        -> DateiNichtLesbarError
        sonst            die Datei ist keine (gueltige) SQLite-Datenbank
                                                        -> DateiInhaltError
    """
    if isinstance(fehler, sqlite3.IntegrityError):
        return DateiInhaltError(
            f"Datenbank {pfad!r}: Der Bestand verletzt eine Regel des Schemas "
            f"und wurde nicht {was}: {fehler}"
        )
    if isinstance(fehler, sqlite3.OperationalError):
        return DateiNichtLesbarError(
            f"Datenbank {pfad!r} konnte nicht {was} werden: {fehler}"
        )
    return DateiInhaltError(
        f"{pfad!r} ist keine gueltige Kunden-Datenbank: {fehler}"
    )


def _komponenten_pruefen(kunden_daten: list[dict[str, Any]]) -> None:
    """Jede Komponente braucht eine Tabelle. Geprueft wird VOR dem Schreiben."""
    for daten in kunden_daten:
        for komponente in daten["komponenten"]:
            if komponente["typ"] not in _KOMPONENTEN:
                raise UnbekannteKomponenteError(
                    f"SQLiteSpeicher hat keine Tabelle fuer die Komponente "
                    f"{komponente['typ']!r} (Kunde {daten['nummer']}). Eine neue "
                    f"Komponentenklasse braucht eine Tabelle in schema.sql und "
                    f"einen Eintrag in _KOMPONENTEN. Es wurde nichts gespeichert."
                )


# --- Lesen ------------------------------------------------------------------

# Was _alles_lesen() zurueckgibt: Tabellenname -> Zeilen als Tupel.
_Rohdaten = dict[str, list[tuple[Any, ...]]]


def _alles_lesen(con: sqlite3.Connection) -> _Rohdaten:
    """Alle Zeilen aller Tabellen holen. Nur Datenbank, keine Objekte.

    ORDER BY ist bei Tags und Notizen Pflicht: Eine Tabelle hat keine
    Reihenfolge, erst `position` stellt die der Python-Liste wieder her.
    """
    roh: _Rohdaten = {
        "kunden": con.execute(
            "SELECT nummer, name, email, umsatz, zustand, "
            "strasse, hausnummer, plz, stadt "
            "FROM kunden ORDER BY nummer"
        ).fetchall(),
        "tags": con.execute(
            "SELECT kunde_nr, tag FROM kunden_tags ORDER BY kunde_nr, position"
        ).fetchall(),
        "notizen": con.execute(
            "SELECT kunde_nr, text FROM notizen ORDER BY kunde_nr, position"
        ).fetchall(),
        "waisen": con.execute(
            "SELECT kunde_nr, text FROM waisen_notizen ORDER BY kunde_nr, position"
        ).fetchall(),
    }
    for typ, tabelle in _KOMPONENTEN.items():
        roh[typ] = con.execute(tabelle.lesen).fetchall()
    return roh


def _kunden_dicts(roh: _Rohdaten) -> list[dict[str, Any]]:
    """Aus den Zeilen wieder die dicts machen, die Kunde.aus_dict() versteht."""
    tags: dict[int, list[str]] = {}
    for kunde_nr, tag in roh["tags"]:
        tags.setdefault(kunde_nr, []).append(tag)

    komponenten: dict[int, list[dict[str, Any]]] = {}
    for typ, tabelle in _KOMPONENTEN.items():
        for kunde_nr, *werte in roh[typ]:
            # zip() paart Feldnamen und Werte: ("firma", "ust_id") mit
            # ("Beispiel GmbH", "DE1") -> {"firma": ..., "ust_id": ...}
            felder = dict(zip(tabelle.felder, werte))
            komponenten.setdefault(kunde_nr, []).append({"typ": typ, **felder})

    ergebnis = []
    for nummer, name, email, umsatz, zustand, strasse, hausnummer, plz, stadt in roh["kunden"]:
        # Das Schema garantiert "alle vier oder keins". Eine Spalte zu
        # pruefen genuegt deshalb.
        adresse = (
            None
            if strasse is None
            else {"strasse": strasse, "hausnummer": hausnummer, "plz": plz, "stadt": stadt}
        )
        ergebnis.append({
            "nummer": nummer,
            "name": name,
            "email": email,
            "umsatz": umsatz,
            "zustand": zustand,
            "adresse": adresse,
            "tags": tags.get(nummer, []),
            "komponenten": komponenten.get(nummer, []),
        })
    return ergebnis


def _notizen_einsammeln(roh: _Rohdaten) -> dict[int, list[Notiz]]:
    """Notizen UND Waisen in ein dict. Wer davon Waise ist, entscheidet spaeter
    _zusammenfuegen(), genau wie bei den anderen Speichern."""
    gesammelt: dict[int, list[Notiz]] = {}
    for kunde_nr, text in roh["notizen"] + roh["waisen"]:
        gesammelt.setdefault(kunde_nr, []).append(Notiz(text))
    return gesammelt


# --- Schreiben --------------------------------------------------------------

def _kunden_schreiben(con: sqlite3.Connection, kunden_daten: list[dict[str, Any]]) -> None:
    """Kunden, Tags und Komponenten. Werte NUR ueber Platzhalter."""
    for daten in kunden_daten:
        adresse = daten["adresse"] or {}
        con.execute(
            "INSERT INTO kunden (nummer, name, email, umsatz, zustand, "
            "strasse, hausnummer, plz, stadt) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                daten["nummer"], daten["name"], daten["email"],
                daten["umsatz"], daten["zustand"],
                # .get() liefert None, wenn es keine Adresse gibt. None wird
                # in SQL zu NULL, und der CHECK "alle vier oder keins" passt.
                adresse.get("strasse"), adresse.get("hausnummer"),
                adresse.get("plz"), adresse.get("stadt"),
            ),
        )

        # executemany: ein Statement, viele Wertetupel. enumerate() liefert
        # zu jedem Tag seinen Listenindex, und der wird zur position.
        con.executemany(
            "INSERT INTO kunden_tags (kunde_nr, position, tag) VALUES (?, ?, ?)",
            [(daten["nummer"], position, tag) for position, tag in enumerate(daten["tags"])],
        )

        for komponente in daten["komponenten"]:
            tabelle = _KOMPONENTEN[komponente["typ"]]
            werte = [komponente[feld] for feld in tabelle.felder]
            con.execute(tabelle.schreiben, (daten["nummer"], *werte))


# Zwei ausgeschriebene Statements statt eines f-Strings mit Tabellennamen,
# aus demselben Grund wie bei _KOMPONENTEN.
_NOTIZ_EINFUEGEN = "INSERT INTO notizen (kunde_nr, position, text) VALUES (?, ?, ?)"
_WAISE_EINFUEGEN = "INSERT INTO waisen_notizen (kunde_nr, position, text) VALUES (?, ?, ?)"


def _notizen_schreiben(
    con: sqlite3.Connection,
    notiz_daten: dict[str, list[dict[str, Any]]],
    vorhandene_nummern: set[int],
) -> None:
    """Die Waisen-Regel aus dem Docstring von speichern()."""
    for nummer_text, eintraege in notiz_daten.items():
        # NotizSpeicher.als_dict() schreibt die Nummer als Text (JSON kennt
        # nur Text-Schluessel). Fuer die Datenbank zurueck in eine Zahl.
        nummer = int(nummer_text)
        sql = _NOTIZ_EINFUEGEN if nummer in vorhandene_nummern else _WAISE_EINFUEGEN
        con.executemany(
            sql,
            [(nummer, position, eintrag["text"]) for position, eintrag in enumerate(eintraege)],
        )
