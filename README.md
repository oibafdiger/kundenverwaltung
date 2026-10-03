# Kundenverwaltung

Eine objektorientierte Kundenverwaltung in Python, entstanden als
Lernprojekt, das über zwölf Wochen schrittweise gewachsen ist. Der Fokus liegt
nicht auf dem Funktionsumfang, sondern auf den Designentscheidungen: warum
Komposition statt Vererbung, wann ein ABC und wann ein Protocol, wie eine
Fehlerhierarchie aussieht, die einem Aufrufer tatsächlich hilft, und wie man
Daten speichert, ohne sie bei einem Abbruch zu verlieren.

Gespeichert wird wahlweise in JSON-Dateien oder in einer SQLite-Datenbank,
hinter demselben Vertrag. Der Code, der mit Kunden arbeitet, merkt den
Unterschied nicht.

Keine externen Abhängigkeiten, auch SQLite kommt aus der Standardbibliothek.
`mypy --strict` läuft ohne ein einziges `type: ignore` durch. 278 Tests, davon
276 in unter zwei Sekunden.

```python
from kundenverwaltung import (
    Adresse, DateiSpeicher, GeschaeftsDaten, Kunde, KundenDatei,
)

speicher = DateiSpeicher("kunden.json")

with KundenDatei(speicher) as kunden:            # lädt, oder beginnt leer
    anna = Kunde("Anna Beispiel", "anna@example.de",
                 geschaefts_daten=GeschaeftsDaten("Beispiel GmbH", "DE123456789"),
                 adresse=Adresse("Hauptstrasse", "1", "10115", "Berlin"))
    anna.umsatz = 150_000
    kunden.hinzufuegen(anna)
# Hier ist gespeichert: atomar, und nur weil der Block fehlerfrei durchlief.

with KundenDatei(speicher) as kunden:
    for kunde in sorted(kunden, reverse=True):    # nach Umsatz, ohne key-Argument
        print(kunde)    # 1000 Anna Beispiel <anna@example.de> — Kunde ist ein Grosskunde
```

## Loslegen

```bash
git clone https://github.com/oibafdiger/kundenverwaltung.git
cd kundenverwaltung
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

python -m kundenverwaltung   # kurzer Vorführdurchlauf
pytest                       # 278 Tests
pytest -m "not langsam"      # ohne die zwei Subprozess-Tests, ~1,6 s
mypy                         # streng, Einstellungen in pyproject.toml
```

Voraussetzung ist Python 3.12.

## Aufbau

```
src/kundenverwaltung/
  exceptions.py     Fehlerhierarchie: eine Basis, zehn Unterklassen
  validierung.py    email_gueltig
  protokoll.py      Fehlerprotokoll (Kontextmanager)
  dateien.py        json_atomar_schreiben
  komponenten.py    InfoLieferant (ABC), InfoFaehig (Protocol), Adresse, Notiz
  kunde.py          Kunde, KundenZustand
  notizen.py        NotizSpeicher
  csv_format.py     KundenCsv
  kundenliste.py    Container mit vollem Protokoll
  speicher.py       Speicher (ABC), DateiSpeicher, InMemorySpeicher
  sql_speicher.py   SQLiteSpeicher und seine Abfragen
  schema.sql        das Datenbankschema
  persistenz.py     KundenDatei, kunden_datei
  main.py           Vorführung
  __main__.py       Startpunkt für python -m kundenverwaltung
  __init__.py       öffentliche Schnittstelle (__all__)

tests/              zwölf Dateien, nach Thema getrennt
beispieldaten/      CSV mit absichtlich kaputten Zeilen
```

Die Module sind in Ebenen geordnet, und jedes importiert nur aus tieferen:

```
0  exceptions, protokoll, validierung
1  dateien, komponenten
2  kunde, notizen
3  csv_format, kundenliste
4  speicher
5  persistenz, sql_speicher
```

Ein Test baut diesen Graphen bei jedem Lauf aus den Importen neu auf und sucht
Kreise.

## Designentscheidungen

Der interessantere Teil dieses Projekts. Jede dieser Entscheidungen wurde
gegen eine Alternative abgewogen, und mehrere davon sind Korrekturen an einem
früheren Entwurf.

### Komposition statt Vererbung

Ursprünglich gab es `Privatkunde`, `Geschaeftskunde` und `Grosskunde` als
Unterklassen von `Kunde`. Heute hat ein `Kunde` **Komponenten**:

```python
Kunde("MegaCorp", "kontakt@megacorp.de",
      geschaefts_daten=GeschaeftsDaten("MegaCorp AG", "DE555"),
      großkunden_daten=GrosskundenDaten("Frau Mueller"))
```

Der Ausschlag gab ein konkreter Fehler, kein Prinzip: Die Vererbungsvariante
hatte einen **Fragile-Base-Class-Bug**. `status()` in der Basisklasse verglich
den Umsatz immer gegen die Basisgrenze von 10.000, auch bei Geschäftskunden,
für die 100.000 gilt. Ein Geschäftskunde mit 12.000 Umsatz galt damit
fälschlich als Großkunde. Der Bug war in der Unterklasse nicht sichtbar; er
entstand dadurch, dass die Basisklasse eine Annahme über alle ihre Erben traf.

Mit Komposition delegiert die Grenze an die Komponente, die sie kennt. Der
Preis ist mehr Code: Die Delegation muss man ausschreiben. Der Gewinn ist, dass
ein Kunde mehrere Rollen gleichzeitig haben kann. Ein Regressionstest hält den
ursprünglichen Bug fest.

### ABC **und** Protocol, für verschiedene Zwecke

`InfoLieferant` ist ein **ABC**, ein nominaler Vertrag für die eigenen
Komponenten. Wer davon erbt, verpflichtet sich auf `info()` und `label()`, und
Python setzt das beim Instanziieren durch. Der ABC trägt zusätzlich eine
Registry, die sich über `__init_subclass__` selbst füllt:

```python
class PrivatDaten(InfoLieferant, key="privat"):
    ...

InfoLieferant.erzeugt("privat", 1990)   # Factory über den Schlüssel
```

`InfoFaehig` ist ein **Protocol**, ein struktureller Vertrag für die Grenze,
an der `Kunde` Fremdes annimmt. Dort zählt nur, ob ein Objekt `info()` kann.
Die Klasse `Notiz` erbt von nichts und funktioniert trotzdem.

Die Faustregel: **ABC für Code, den man besitzt. Protocol für Code, den man
annimmt.**

### Eine Klasse, ein Grund zur Änderung

Die Leitfrage beim Aufteilen war nicht „wie lang ist die Klasse", sondern „wie
viele Gründe gibt es, sie zu ändern". `Kunde` hatte vier: Kundendaten,
Großkundenlogik, E-Mail-Prüfung und CSV-Format.

- **CSV** zog nach `KundenCsv`. Ein neues Trennzeichen hat nichts damit zu
  tun, was ein Kunde ist. Lesen und Schreiben stehen seitdem in derselben
  Klasse; vorher benutzten sie unbemerkt verschiedene Trennzeichen.
- **`email_gueltig`** wurde eine Modulfunktion. Als `@staticmethod` hat sie
  `self` nie angefasst, ein ablesbares Zeichen, dass sie in der falschen
  Klasse stand.
- Die **Großkundenlogik** blieb bewusst. Was nach dem Herauslösen übrig ist,
  *ist* die Aufgabe der Klasse; ohne sie bliebe ein Datenhalter ohne Verhalten.

Später traf dieselbe Frage die Container. `Kundenliste` und `NotizSpeicher`
hielten ihre Daten und wussten zugleich, wie diese auf die Platte kommen. Der
Test dafür war nicht die Länge der Klasse, sondern: wenn sich X ändert, welche
Datei fasse ich an?

```
Kunde bekommt ein Feld    →  kunde.py                       in Ordnung
JSON wird Datenbank       →  kundenliste.py + persistenz.py  Schaden
```

Die zweite Zeile war der Grund zu handeln. Ein Speicherwechsel hätte
Container-Klassen angefasst, die mit Speichern nichts zu tun haben. Der
Dateizugriff liegt seitdem in `speicher.py`; die Container halten nur noch.

### Eine flache Fehlerhierarchie

```
KundenverwaltungError
├── KundeNichtGefundenError
├── UnbekannteKomponenteError
├── UngueltigeEmailError
├── UngueltigerNameError
├── UngueltigerBetragError
├── UngueltigeAdresseError
├── CsvFormatError
├── DateiNichtGefundenError
├── DateiNichtLesbarError
└── DateiInhaltError
```

Die gemeinsame Basis lässt dem **Aufrufer** die Wahl der Granularität. Ebenso
wichtig ist, was sie **ausschließt**: `TypeError` aus echten
Programmierfehlern bleibt draußen und schlägt durch.

Die Aufteilung folgt der Frage, ob ein Aufrufer **anders reagiert**. Deshalb
sind die Dateifehler drei Klassen: Auf `DateiNichtGefundenError` reagiert man
mit einer leeren Liste. Beim ersten Programmstart ist das der Normalfall. Auf
eine unlesbare oder kaputte Datei reagiert man mit Abbruch, denn Weitermachen
hieße, beim nächsten Speichern echte Daten zu überschreiben.

Und derselbe Wert kann in verschiedene Klassen fallen, je nachdem, **woher** er
kommt: `kunde.zustand = "gesperrt"` im Programm ist ein Bug (`TypeError`),
derselbe Unsinn aus einer JSON-Datei ist kaputte Eingabe (`DateiInhaltError`).
Übersetzt wird dort, wo fremde Daten hereinkommen.

### Fehler weiterreichen, mit oder ohne Ursache

```python
# Der KeyError verrät nur die interne Mechanik → verschweigen
except KeyError:
    raise UnbekannteKomponenteError(...) from None

# Der OSError verrät, WAS los war (fehlt? gesperrt? Rechte?) → weiterreichen
except OSError as e:
    raise DateiNichtLesbarError(f"Datei nicht lesbar: {pfad!r}") from e
```

Die Leitfrage: Hilft die untere Exception jemandem, der die Meldung liest?

### Speichern: alles oder nichts

`KundenDatei` klammert Laden und Speichern um einen Arbeitsblock, auf zwei
Ebenen gegen halbe Zustände geschützt:

| Ebene | schützt vor | wie |
|---|---|---|
| Vorgang | einem halb durchgeführten Block | Fliegt im `with`-Block eine Exception, wird **gar nicht** gespeichert |
| Datei | einer halb geschriebenen Datei | Schreiben in eine temporäre Datei, `fsync`, dann `os.replace()` |

Der zweite Punkt braucht keinen Stromausfall, um wichtig zu sein: Ein einziges
nicht serialisierbares Objekt mitten im Datenbestand bricht `json.dump` ab,
mit `open(pfad, "w")` wäre der alte Stand dann schon gelöscht. `os.replace()`
ändert nie den Inhalt einer Datei, sondern welcher Inhalt unter dem Namen zu
finden ist, und das ist unteilbar. Die Zugriffsrechte der alten Datei werden
dabei übernommen.

Weitere Entscheidungen in der Speicherschicht:

- **Formatversion.** Jede Datei trägt `"version"`. Als in Version 2 aus
  `"aktiv": true` ein `"zustand": "gesperrt"` wurde, blieben alte Dateien
  lesbar und werden beim nächsten Speichern migriert.
- **Getaggte Komponenten.** Komponenten stehen als Liste mit Typmarker in der
  Datei. Feste Schlüssel wären besser typisiert, verlangten aber bei jeder neuen
  Komponentenklasse eine Änderung an `Kunde` (Open-Closed). Ein Test legt eine
  Komponentenklasse nachträglich an und speichert sie, ohne `Kunde` anzufassen.
- **Notizen in eigener Datei.** Eine Notiz sagt nichts darüber, wer ein Kunde
  ist. Sie hängt an ihm, mit der Kundennummer als Verweis. Notizen zu Kunden,
  die es nicht mehr gibt, werden gemeldet **und** aufbewahrt; eine frühere
  Fassung hatte sie still gelöscht, ein Regressionstest hält das fest.

Dieselbe Klammer gibt es als Generator mit `@contextmanager` (`kunden_datei`).
Beide Varianten benutzen denselben Speicher und unterscheiden sich nur in der
Verpackung.

### Der Speicher ist austauschbar

`KundenDatei` bekommt den Speicher übergeben, statt ihn sich zu bauen:

```python
KundenDatei(DateiSpeicher("kunden.json"))   # zwei JSON-Dateien
KundenDatei(InMemorySpeicher())             # nichts auf der Platte
KundenDatei(SQLiteSpeicher("kunden.db"))    # eine SQLite-Datenbank
```

Vorher nahm die Klasse einen Pfad entgegen und wusste damit, dass daraus JSON
wird. Wer den Speicher tauschen wollte, musste sie anfassen. Jetzt hängen beide
Seiten nur noch am `Speicher`-Vertrag. `persistenz.py` importiert keine einzige
konkrete Implementierung, und ein Test prüft das über den AST statt über eine
Textsuche: Die Docstrings *zeigen* `DateiSpeicher` als Beispiel, benutzen ihn
aber nicht.

Der Vertrag umfasst Kunden und Notizen zusammen. Bei zwei getrennten Verträgen
müsste jemand von außen ihre Reihenfolge koordinieren, und genau diese
Koordination ist der heikle Teil. So gehört sie zu der Implementierung, die
weiß, ob sie sie überhaupt einhalten kann: `DateiSpeicher` kann es nicht (zwei
Dateien, zwei `os.replace()`), `InMemorySpeicher` braucht es nicht, eine
Datenbank hätte an der Stelle eine Transaktion.

`laden()` nimmt keinen Pfad entgegen. Er wäre ein Parameter, den
`InMemorySpeicher` nur ignorieren könnte, also ein Vertrag, der für eine seiner
Implementierungen nicht stimmt. Jede bringt im Konstruktor mit, was sie
braucht.

`InMemorySpeicher` legt die dicts ab, nicht die Objekte. Hielte er die Objekte,
bekäme der Aufrufer dieselben zurück, die er hineingegeben hat, und Tests
fänden Fehler nicht mehr, die eine Datei sehr wohl aufdeckt: ein Feld, das gar
nicht serialisiert wird, oder ein Zustand, der den Round-Trip nicht überlebt.
Ein Test-Double darf schneller sein als das Echte, aber nicht nachsichtiger.

`SQLiteSpeicher` ist die Implementierung, die der Vertrag vorhergesagt hat.
Kunden und Notizen gehen in **einer** Transaktion in die Datenbank: Scheitert
das Speichern mittendrin, wird alles zurückgerollt, und der alte Stand bleibt
vollständig. Übersetzt wird über dieselben dicts wie bei JSON
(`Kunde.als_dict()` und `Kunde.aus_dict()`), damit beim Laden dieselben
Prüfungen greifen und kein zweiter Satz Regeln entsteht. Der Beleg, dass der
Vertrag trägt: Die Vertragstests aus der Zeit, als es nur zwei Speicher gab,
laufen unverändert auch gegen den dritten.

### Datenbankschema

Das Schema ([schema.sql](src/kundenverwaltung/schema.sql)) folgt einer
Grundregel: **Es prüft dasselbe wie die Klassen, nicht mehr und nicht weniger.**
Ein Name aus Leerzeichen, ein negativer Umsatz, ein unbekannter Zustand oder
eine halbe Adresse wird von der Datenbank genauso abgelehnt wie von Python.
Strenger wäre schlecht, weil sich dann ein gültiger Kunde nicht speichern
ließe. Lockerer wäre schlecht, weil die Datei dann für jedes andere Programm
ungeschützt wäre.

Die Entscheidungen, jeweils mit der verworfenen Alternative:

| Frage | Entscheidung | Verworfen |
|---|---|---|
| Drei Komponentenklassen | eine Tabelle pro Klasse; `kunde_nr` ist dort Primär- und Fremdschlüssel zugleich, das erzwingt „höchstens eine pro Kunde“ | eine Tabelle mit Typspalte (viele NULL-Spalten), eine JSON-Spalte (die Datenbank kann den Inhalt weder prüfen noch abfragen) |
| Tags sind eine Liste | eigene Tabelle, eine Zeile pro Tag (1. Normalform) | `'vip,neu'` in einer Spalte |
| Reihenfolge von Notizen und Tags | Spalte `position` im Primärschlüssel; eine Tabelle hat von sich aus keine Reihenfolge | keine Alternative nötig |
| Notizen zu gelöschten Kunden | eigene Tabelle `waisen_notizen` ohne Fremdschlüssel; alle anderen Notizen schützt der Fremdschlüssel | `ON DELETE CASCADE` (stiller Datenverlust), ein Platzhalter-Kunde (die ursprüngliche Nummer ginge verloren) |
| Adresse | vier Spalten in `kunden` mit `CHECK` „alle vier oder keins“ | eigene Tabelle, sinnvoll erst bei mehreren Adressen pro Kunde |

Der Preis der Komponenten-Entscheidung steht offen im Code: Eine neue
Komponentenklasse braucht eine neue Tabelle. Bis dahin lehnt `speichern()` sie
ab, **bevor** etwas geschrieben wird. Bei JSON gibt es diese Grenze nicht.

SQLite prüft Fremdschlüssel nur, wenn jede Verbindung `PRAGMA foreign_keys = ON`
setzt. Damit das nicht vergessen werden kann, öffnet genau eine Methode
Verbindungen, und das PRAGMA steht dort direkt nach `connect()`. Ein Test hält
fest, was ohne passiert: Die verwaiste Notiz wird klaglos angenommen.

Daneben kann `SQLiteSpeicher` Fragen beantworten, für die man bei JSON alles
laden und in Python zählen müsste: Kunden nach Ort, Notizen pro Kunde (auch
mit 0), Umsatz pro Zustand, verwaiste Notizen. Gerechnet wird im SQL. Der
Query-Plan der Notiz-Abfrage zeigt, dass der zusammengesetzte Primärschlüssel
als Index taugt:

```
SCAN k
SEARCH n USING COVERING INDEX sqlite_autoindex_notizen_1 (kunde_nr=?) LEFT-JOIN
```

*Covering* heißt: Der Index enthält schon alle Spalten, die die Abfrage
braucht, die Tabelle selbst wird gar nicht gelesen.

**Warum SQLite und nicht PostgreSQL:** Das Projekt soll auf jedem Rechner mit
Python laufen, ohne Server und ohne Zugangsdaten. Das Schema ist deshalb so
geschrieben, dass ein Umstieg klein bleibt: `STRICT`-Tabellen, damit SQLite die
Typen so streng prüft wie PostgreSQL, nur Standard-SQL, jede abweichende Stelle
mit `-- PostgreSQL:` markiert. Für PostgreSQL käme eine `PostgresSpeicher`
dazu, fast eine Kopie mit anderem Treiber, und `umsatz` würde `NUMERIC`.

### Das passende Werkzeug: dataclass, Enum und eine normale Klasse

- **`Adresse` und `Notiz` sind `@dataclass(frozen=True)`.** Sie *tragen* Daten.
  Eingefroren lassen sie sich gefahrlos teilen: Zieht einer von zwei Kunden mit
  gemeinsamer Adresse um, bekommt er per `replace()` ein neues Objekt.
  `__post_init__` prüft beim Bauen, und weil sich danach nichts mehr ändern
  kann, reicht das.
- **`Kunde` ist bewusst keine dataclass.** Er *bewacht* seine Daten:
  Validierung in Settern, ein Nummernzähler, Gleichheit über die Nummer statt
  über alle Felder. Probeweise als dataclass gebaut, brachen sechs Stellen,
  eine davon heimtückisch: Feld und Property gleichen Namens machen das
  Property-Objekt zum Default des Feldes.
- **`KundenZustand` ist eine Enum** statt eines `bool`. Ein Kunde kennt drei
  Zustände (aktiv, inaktiv, gesperrt), und ein Tippfehler an einer Enum wirft
  sofort, statt still falsch zu vergleichen. `aktiv` ist nur noch lesbar, mit
  Setter hätte `aktiv = True` einen gesperrten Kunden still entsperrt.

### Paket und Typen

- **Innen relativ, außen absolut.** Das Paket lässt sich umbenennen, ohne eine
  interne Zeile anzufassen.
- **`mypy --strict` ohne Schlupflöcher:** kein `type: ignore`, kein `cast()`.
  `Any` steht nur für JSON-Inhalt, bevor er geprüft ist. Ein eigener Test ist
  sogar strenger als mypy, der lässt ein `__init__` ohne `-> None` durch.
- **`TYPE_CHECKING` an genau einer Stelle,** wo ein Name nur in Annotationen
  vorkommt. Der Preis (`get_type_hints()` findet ihn zur Laufzeit nicht) ist
  getestet.
- **Type Hints schützen nicht zur Laufzeit.** Deshalb prüft das Laden trotzdem
  mit `isinstance`, obwohl die Annotation schon `dict` sagt.

### Container-Protokoll

`Kundenliste` unterstützt `len()`, Indexzugriff, `in`, `for` und Slicing. Ein
Ausschnitt ist wieder eine `Kundenliste`, per `@overload` typisiert. Der
Container erbt **nicht** von `list`, sonst wären `append`, `sort` und `clear`
alle mit dabei. `hinzufuegen()` ist der einzige Schreibzugriff.

## Tests

Zwölf Dateien nach Thema getrennt, `pytest.mark.parametrize` für die
Tabellenfälle, `tmp_path` für alles mit Dateien. Die Tests, die nur die Klammer
prüfen, laufen über `InMemorySpeicher` und fassen keine Datei an; wo die Datei
selbst das Thema ist (atomares Schreiben, Zugriffsrechte, kaputtes JSON),
bleiben Dateien.

`test_python.py` steht etwas abseits. Dort liegt, was Python prüft statt das
Projekt: was `@dataclass` erzeugt, dass `object.__setattr__` an `frozen`
vorbeikommt, wie Python auf einen Importzyklus reagiert, was mypy aus einem
Generic ableitet. Diese Tests würden auch dann noch etwas belegen, wenn es die
Kundenverwaltung nicht gäbe. Die zwei, die einen eigenen Python-Prozess
starten, sind als `langsam` markiert.

Ein paar Beispiele für die Art von Test, die hier steht:

- **Regressionstests** halten Fehler fest, die es wirklich gab: den
  Fragile-Base-Class-Bug, die still gelöschten Notizen.
- **Gegenproben** zeigen, dass ein Test überhaupt anschlagen kann: Der
  Kreisprüfer für Importe wird zuerst an einem künstlichen Kreis erprobt. Für
  die SQL-Schicht wurden typische Fehler absichtlich eingebaut (`COUNT(*)`
  statt einer Spalte, `JOIN` statt `LEFT JOIN`, keine Transaktion), und jeder
  davon lässt einen Test fehlschlagen.
- **Tests gegen die bequeme Abkürzung:** Ein Round-Trip-Test mit `==` wäre
  wertlos, weil `Kunde.__eq__` nur die Nummer vergleicht. Ein eigener Test
  belegt das mit drei verfälschten Feldern.
- **Ränder:** gültiges JSON mit unbrauchbarem Inhalt, eine Version als Liste,
  ein gesperrtes Verzeichnis, und jeweils die Prüfung, dass nichts
  zurückbleibt.
- **Struktur statt nur Verhalten:** Dass `Kundenliste` nicht mehr speichern
  kann, prüft nicht bloß `hasattr`. Eine private `_speichern()`-Hilfsmethode
  wäre so unsichtbar geblieben, also sucht der Test über den AST, ob im Modul
  überhaupt noch `json` oder `open` vorkommt.

## Was dieses Projekt nicht ist

Keine Nebenläufigkeit: Zwei Prozesse, die gleichzeitig speichern, überschreiben
sich, ohne Datenverlust, aber der letzte gewinnt. Keine Benutzeroberfläche.
Und `DateiSpeicher` schreibt zwei Dateien, die je für sich atomar sind, aber
nicht gemeinsam; die Reihenfolge ist so gewählt, dass ein Abbruch dazwischen
sichtbar statt still bleibt. Wer beides zusammen geschützt braucht, nimmt
`SQLiteSpeicher`. Keine Performance-Arbeit an großen Datenmengen: Gespeichert
wird immer der ganze Bestand, das ist bei einer Kundenverwaltung dieser Größe
richtig und bei Millionen Zeilen nicht mehr. Das ist das nächste Thema im
Lernweg, zusammen mit PostgreSQL.

## Lizenz

MIT, siehe [LICENSE](LICENSE).
