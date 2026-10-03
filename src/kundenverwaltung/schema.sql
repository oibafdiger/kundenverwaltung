-- ============================================================================
-- schema.sql — die Kundenverwaltung als Tabellen (SQL-Sprint, Block 1)
-- ============================================================================
--
-- Begruendung aller Entscheidungen: REFACTORING.md, Abschnitt "Datenbankschema".
--
-- Grundregeln fuer diese Datei:
--
-- 1. Das Schema prueft DASSELBE wie die Klassen, nicht mehr. Wuerde es
--    strenger pruefen als Python, koennte ein Kunde, den Python erlaubt,
--    nicht gespeichert werden. Wuerde es lockerer pruefen, waere die
--    Datenbank fuer jedes andere Programm, das in sie schreibt, ungeschuetzt.
-- 2. Nur Standard-SQL, damit der Umstieg auf PostgreSQL klein bleibt.
--    Jede Stelle, die dort anders aussieht, hat einen Kommentar
--    "-- PostgreSQL: ...".
-- 3. Alle Tabellen sind STRICT: SQLite prueft dann die Spaltentypen so
--    streng wie PostgreSQL. Ohne STRICT nimmt SQLite in einer INTEGER-Spalte
--    auch einen Text an.
--
-- WICHTIG: Fremdschluessel prueft SQLite nur, wenn die VERBINDUNG
--     PRAGMA foreign_keys = ON;
-- gesetzt hat. Das gehoert nicht in diese Datei (sie wird einmal ausgefuehrt,
-- das PRAGMA gilt aber pro Verbindung), sondern in SQLiteSpeicher.
-- Im sqlite3-Terminal: die Zeile vor dem Testen selbst eintippen.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- kunden — ein Kunde pro Zeile, die Adresse steht mit drin
-- ----------------------------------------------------------------------------
CREATE TABLE kunden (
    -- Die Nummer kommt aus Python (Kunde.naechste_nummer), nicht aus der
    -- Datenbank. Deshalb kein AUTOINCREMENT.
    -- PostgreSQL: unveraendert. (In SQLite ist INTEGER PRIMARY KEY zugleich
    -- die interne Zeilennummer; das merkt man hier nicht, weil wir die
    -- Nummer immer selbst setzen.)
    nummer     INTEGER PRIMARY KEY,

    -- Wie Kunde.__init__: Name darf nicht leer sein, auch nicht nur aus
    -- Leerzeichen bestehen.
    name       TEXT    NOT NULL CHECK (trim(name) <> ''),

    -- Ob die E-Mail gueltig ist, prueft email_gueltig() in Python. Die Regel
    -- ein zweites Mal in SQL nachzubauen, hiesse zwei Regeln zu pflegen, die
    -- auseinanderlaufen koennen. Die Datenbank sichert nur: Es gibt eine.
    email      TEXT    NOT NULL,

    -- Wie der umsatz-Setter: nicht negativ.
    -- PostgreSQL: REAL ist dort nur 4 Byte genau. Fuer Geldbetraege
    -- NUMERIC(12, 2), mindestens DOUBLE PRECISION.
    umsatz     REAL    NOT NULL DEFAULT 0 CHECK (umsatz >= 0),

    -- Die drei Werte von KundenZustand. Ein Tippfehler wie 'gesprerrt' wird
    -- abgelehnt, genau wie das Enum in Python ihn ablehnt.
    zustand    TEXT    NOT NULL DEFAULT 'aktiv'
                       CHECK (zustand IN ('aktiv', 'inaktiv', 'gesperrt')),

    -- Adresse (1:1, Wertobjekt). Darf fehlen, dann sind alle vier NULL.
    -- Ob spaeter eine eigene Tabelle daraus wird, ist offen (siehe Begruendung).
    strasse    TEXT,
    hausnummer TEXT,
    plz        TEXT,      -- TEXT, nicht INTEGER: sonst wird aus 01067 die 1067
    stadt      TEXT,

    -- Alle vier oder keins. Eine halbe Adresse gibt es in Python nicht,
    -- Adresse.__post_init__ verlangt jedes Feld.
    CHECK (
        (strasse IS NULL AND hausnummer IS NULL AND plz IS NULL AND stadt IS NULL)
        OR
        (strasse IS NOT NULL AND hausnummer IS NOT NULL
         AND plz IS NOT NULL AND stadt IS NOT NULL)
    ),
    -- Und wie in __post_init__: kein Feld nur aus Leerzeichen.
    -- (Bei NULL ist der Vergleich unbekannt, und CHECK laesst "unbekannt"
    -- durch. Anders als WHERE, das nur "wahr" behaelt. Deshalb reicht das.)
    CHECK (trim(strasse) <> '' AND trim(hausnummer) <> ''
           AND trim(plz) <> '' AND trim(stadt) <> '')
) STRICT;   -- PostgreSQL: STRICT weglassen, PostgreSQL ist von sich aus streng.


-- ----------------------------------------------------------------------------
-- kunden_tags — die Liste kunde.tags, eine Zeile pro Tag
-- ----------------------------------------------------------------------------
-- Eine Spalte tags = 'vip,neu' in kunden waere eine Liste in einem Feld und
-- verletzt die 1. Normalform. Folge: "alle VIP-Kunden" ginge nur mit
-- Textsuche, und 'vip' in 'vipps' waere ein falscher Treffer.
--
-- position haelt die Reihenfolge fest. Eine Tabelle hat von sich aus keine
-- Reihenfolge; ohne die Spalte kaemen die Tags nach dem Laden in
-- irgendeiner zurueck.
--
-- Kein UNIQUE (kunde_nr, tag): Python erlaubt doppelte Tags, also hier auch.
CREATE TABLE kunden_tags (
    kunde_nr INTEGER NOT NULL REFERENCES kunden (nummer),
    position INTEGER NOT NULL CHECK (position >= 0),
    tag      TEXT    NOT NULL,
    PRIMARY KEY (kunde_nr, position)
) STRICT;   -- PostgreSQL: STRICT weglassen


-- ----------------------------------------------------------------------------
-- Komponenten — eine Tabelle pro Klasse
-- ----------------------------------------------------------------------------
-- kunde_nr ist hier PRIMARY KEY und Fremdschluessel zugleich. Das erzwingt
-- zwei Dinge auf einmal:
--   - Es gibt die Komponente nur zu einem existierenden Kunden (FOREIGN KEY).
--   - Es gibt sie hoechstens EINMAL pro Kunde (PRIMARY KEY), genau wie Kunde
--     nur ein Attribut private_daten hat und keine Liste davon.
-- Kein CHECK auf die Werte (etwa geburtsjahr > 1900), weil die Klassen
-- selbst keinen haben. Siehe Grundregel 1 oben.

CREATE TABLE privat_daten (
    kunde_nr    INTEGER PRIMARY KEY REFERENCES kunden (nummer),
    geburtsjahr INTEGER NOT NULL
) STRICT;   -- PostgreSQL: STRICT weglassen

CREATE TABLE geschaefts_daten (
    kunde_nr INTEGER PRIMARY KEY REFERENCES kunden (nummer),
    firma    TEXT    NOT NULL,
    ust_id   TEXT    NOT NULL
) STRICT;   -- PostgreSQL: STRICT weglassen

CREATE TABLE grosskunden_daten (
    kunde_nr INTEGER PRIMARY KEY REFERENCES kunden (nummer),
    betreuer TEXT    NOT NULL
) STRICT;   -- PostgreSQL: STRICT weglassen


-- ----------------------------------------------------------------------------
-- notizen — 1:n, ein Kunde hat beliebig viele Notizen
-- ----------------------------------------------------------------------------
-- Gleicher Aufbau wie kunden_tags: Reihenfolge ueber position.
--
-- Index auf kunde_nr: Ein Fremdschluessel legt KEINEN Index an. Hier ist
-- trotzdem keiner extra noetig. Der Primaerschluessel (kunde_nr, position)
-- hat einen eigenen Index, und kunde_nr ist dessen ERSTE Spalte. Damit
-- taugt er auch fuer WHERE kunde_nr = ? (wie das Telefonbuch, das nach
-- Nachname, dann Vorname sortiert ist, auch fuer "alle Mueller" taugt).
-- Nachpruefen mit:
--   EXPLAIN QUERY PLAN SELECT * FROM notizen WHERE kunde_nr = 1000;
CREATE TABLE notizen (
    kunde_nr INTEGER NOT NULL REFERENCES kunden (nummer),
    position INTEGER NOT NULL CHECK (position >= 0),
    text     TEXT    NOT NULL,
    PRIMARY KEY (kunde_nr, position)
) STRICT;   -- PostgreSQL: STRICT weglassen


-- ----------------------------------------------------------------------------
-- waisen_notizen — Notizen zu Kunden, die es nicht mehr gibt
-- ----------------------------------------------------------------------------
-- Entscheidung 02.10.2026 (Weg b): Fremdschluessel fuer notizen behalten,
-- Waisen getrennt ablegen. kunde_nr hat hier BEWUSST keinen Fremdschluessel,
-- denn genau das macht eine Waise aus: Ihr Kunde existiert nicht.
--
-- Was die Datenbank hier NICHT erzwingen kann: dass die Nummer wirklich
-- keinem Kunden gehoert. Ein CHECK darf keine andere Tabelle befragen.
-- Das stellt SQLiteSpeicher.speichern() sicher.
CREATE TABLE waisen_notizen (
    kunde_nr INTEGER NOT NULL,   -- die Nummer des geloeschten Kunden
    position INTEGER NOT NULL CHECK (position >= 0),
    text     TEXT    NOT NULL,
    PRIMARY KEY (kunde_nr, position)
) STRICT;   -- PostgreSQL: STRICT weglassen
