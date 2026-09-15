# Kundenverwaltung

Eine objektorientierte Kundenverwaltung in Python — entstanden als
Lernprojekt, das über elf Wochen schrittweise gewachsen ist. Der Fokus liegt
nicht auf dem Funktionsumfang, sondern auf den Designentscheidungen: warum
Komposition statt Vererbung, wann ein ABC und wann ein Protocol, wie eine
Fehlerhierarchie aussieht, die einem Aufrufer tatsächlich hilft — und wie man
Daten speichert, ohne sie bei einem Abbruch zu verlieren.

Keine externen Abhängigkeiten. `mypy --strict` läuft ohne ein einziges
`type: ignore` durch, 178 Tests in unter einer Sekunde.

```python
from kundenverwaltung import Adresse, GeschaeftsDaten, Kunde, KundenDatei

with KundenDatei("kunden.json") as kunden:       # lädt — oder beginnt leer
    anna = Kunde("Anna Beispiel", "anna@example.de",
                 geschaefts_daten=GeschaeftsDaten("Beispiel GmbH", "DE123456789"),
                 adresse=Adresse("Hauptstrasse", "1", "10115", "Berlin"))
    anna.umsatz = 150_000
    kunden.hinzufuegen(anna)
# Hier ist gespeichert: atomar, und nur weil der Block fehlerfrei durchlief.

with KundenDatei("kunden.json") as kunden:
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
pytest                       # 178 Tests
mypy                         # streng, Einstellungen in pyproject.toml
```

Voraussetzung ist Python 3.12.

## Aufbau

```
src/kundenverwaltung/
  exceptions.py     Fehlerhierarchie — eine Basis, zehn Unterklassen
  validierung.py    email_gueltig
  protokoll.py      Fehlerprotokoll (Kontextmanager)
  dateien.py        json_atomar_schreiben
  komponenten.py    InfoLieferant (ABC), InfoFaehig (Protocol), Adresse, Notiz
  kunde.py          Kunde, KundenZustand
  csv_format.py     KundenCsv
  kundenliste.py    Container mit vollem Protokoll, JSON-Speichern und -Laden
  persistenz.py     NotizSpeicher, KundenDatei, kunden_datei
  main.py           Vorführung
  __main__.py       Startpunkt für python -m kundenverwaltung
  __init__.py       öffentliche Schnittstelle (__all__)

tests/              sieben Dateien, nach Thema getrennt
beispieldaten/      CSV mit absichtlich kaputten Zeilen
```

Die Module sind in Ebenen geordnet, und jedes importiert nur aus tieferen:

```
0  exceptions, protokoll, validierung
1  dateien, komponenten
2  kunde
3  csv_format, kundenliste
4  persistenz
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
den Umsatz immer gegen die Basisgrenze von 10.000 — auch bei Geschäftskunden,
für die 100.000 gilt. Ein Geschäftskunde mit 12.000 Umsatz galt damit
fälschlich als Großkunde. Der Bug war in der Unterklasse nicht sichtbar; er
entstand dadurch, dass die Basisklasse eine Annahme über alle ihre Erben traf.

Mit Komposition delegiert die Grenze an die Komponente, die sie kennt. Der
Preis ist mehr Code — die Delegation muss man ausschreiben. Der Gewinn ist, dass
ein Kunde mehrere Rollen gleichzeitig haben kann. Ein Regressionstest hält den
ursprünglichen Bug fest.

### ABC **und** Protocol, für verschiedene Zwecke

`InfoLieferant` ist ein **ABC** — ein nominaler Vertrag für die eigenen
Komponenten. Wer davon erbt, verpflichtet sich auf `info()` und `label()`, und
Python setzt das beim Instanziieren durch. Der ABC trägt zusätzlich eine
Registry, die sich über `__init_subclass__` selbst füllt:

```python
class PrivatDaten(InfoLieferant, key="privat"):
    ...

InfoLieferant.erzeugt("privat", 1990)   # Factory über den Schlüssel
```

`InfoFaehig` ist ein **Protocol** — ein struktureller Vertrag für die Grenze,
an der `Kunde` Fremdes annimmt. Dort zählt nur, ob ein Objekt `info()` kann.
Die Klasse `Notiz` erbt von nichts und funktioniert trotzdem.

Die Faustregel: **ABC für Code, den man besitzt. Protocol für Code, den man
annimmt.**

### Eine Klasse, ein Grund zur Änderung

Die Leitfrage beim Aufteilen war nicht „wie lang ist die Klasse", sondern „wie
viele Gründe gibt es, sie zu ändern". `Kunde` hatte vier: Kundendaten,
Großkundenlogik, E-Mail-Prüfung und CSV-Format.

- **CSV** zog nach `KundenCsv` — ein neues Trennzeichen hat nichts damit zu
  tun, was ein Kunde ist. Lesen und Schreiben stehen seitdem in derselben
  Klasse; vorher benutzten sie unbemerkt verschiedene Trennzeichen.
- **`email_gueltig`** wurde eine Modulfunktion. Als `@staticmethod` hat sie
  `self` nie angefasst — ein ablesbares Zeichen, dass sie in der falschen
  Klasse stand.
- Die **Großkundenlogik** blieb bewusst. Was nach dem Herauslösen übrig ist,
  *ist* die Aufgabe der Klasse; ohne sie bliebe ein Datenhalter ohne Verhalten.

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
mit einer leeren Liste — beim ersten Programmstart ist das der Normalfall. Auf
eine unlesbare oder kaputte Datei reagiert man mit Abbruch, denn Weitermachen
hieße, beim nächsten Speichern echte Daten zu überschreiben.

Und derselbe Wert kann in verschiedene Klassen fallen, je nachdem, **woher** er
kommt: `kunde.zustand = "gesperrt"` im Programm ist ein Bug (`TypeError`),
derselbe Unsinn aus einer JSON-Datei ist kaputte Eingabe (`DateiInhaltError`).
Übersetzt wird dort, wo fremde Daten hereinkommen.

### Fehler weiterreichen — mit oder ohne Ursache

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

`KundenDatei` klammert Laden und Speichern um einen Arbeitsblock — auf zwei
Ebenen gegen halbe Zustände geschützt:

| Ebene | schützt vor | wie |
|---|---|---|
| Vorgang | einem halb durchgeführten Block | Fliegt im `with`-Block eine Exception, wird **gar nicht** gespeichert |
| Datei | einer halb geschriebenen Datei | Schreiben in eine temporäre Datei, `fsync`, dann `os.replace()` |

Der zweite Punkt braucht keinen Stromausfall, um wichtig zu sein: Ein einziges
nicht serialisierbares Objekt mitten im Datenbestand bricht `json.dump` ab —
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
  ist — sie hängt an ihm, mit der Kundennummer als Verweis. Notizen zu Kunden,
  die es nicht mehr gibt, werden gemeldet **und** aufbewahrt; eine frühere
  Fassung hatte sie still gelöscht, ein Regressionstest hält das fest.

Dieselbe Klammer gibt es als Generator mit `@contextmanager` (`kunden_datei`).
Beide Varianten teilen dieselben Hilfsfunktionen und unterscheiden sich nur in
der Verpackung.

### Das passende Werkzeug: dataclass, Enum — und eine normale Klasse

- **`Adresse` und `Notiz` sind `@dataclass(frozen=True)`.** Sie *tragen* Daten.
  Eingefroren lassen sie sich gefahrlos teilen: Zieht einer von zwei Kunden mit
  gemeinsamer Adresse um, bekommt er per `replace()` ein neues Objekt.
  `__post_init__` prüft beim Bauen — und weil sich danach nichts mehr ändern
  kann, reicht das.
- **`Kunde` ist bewusst keine dataclass.** Er *bewacht* seine Daten:
  Validierung in Settern, ein Nummernzähler, Gleichheit über die Nummer statt
  über alle Felder. Probeweise als dataclass gebaut, brachen sechs Stellen —
  eine davon heimtückisch: Feld und Property gleichen Namens machen das
  Property-Objekt zum Default des Feldes.
- **`KundenZustand` ist eine Enum** statt eines `bool`. Ein Kunde kennt drei
  Zustände (aktiv, inaktiv, gesperrt), und ein Tippfehler an einer Enum wirft
  sofort, statt still falsch zu vergleichen. `aktiv` ist nur noch lesbar — mit
  Setter hätte `aktiv = True` einen gesperrten Kunden still entsperrt.

### Paket und Typen

- **Innen relativ, außen absolut.** Das Paket lässt sich umbenennen, ohne eine
  interne Zeile anzufassen.
- **`mypy --strict` ohne Schlupflöcher:** kein `type: ignore`, kein `cast()`.
  `Any` steht nur für JSON-Inhalt, bevor er geprüft ist. Ein eigener Test ist
  sogar strenger als mypy — der lässt ein `__init__` ohne `-> None` durch.
- **`TYPE_CHECKING` an genau einer Stelle,** wo ein Name nur in Annotationen
  vorkommt. Der Preis — `get_type_hints()` findet ihn zur Laufzeit nicht — ist
  getestet.
- **Type Hints schützen nicht zur Laufzeit.** Deshalb prüft das Laden trotzdem
  mit `isinstance`, obwohl die Annotation schon `dict` sagt.

### Container-Protokoll

`Kundenliste` unterstützt `len()`, Indexzugriff, `in`, `for` und Slicing. Ein
Ausschnitt ist wieder eine `Kundenliste`, per `@overload` typisiert. Der
Container erbt **nicht** von `list` — sonst wären `append`, `sort` und `clear`
alle mit dabei. `hinzufuegen()` ist der einzige Schreibzugriff.

## Tests

Sieben Dateien nach Thema getrennt, `pytest.mark.parametrize` für die
Tabellenfälle, `tmp_path` für alles mit Dateien. Ein paar Beispiele für die Art
von Test, die hier steht:

- **Regressionstests** halten Fehler fest, die es wirklich gab — den
  Fragile-Base-Class-Bug, die still gelöschten Notizen.
- **Gegenproben** zeigen, dass ein Test überhaupt anschlagen kann: Der
  Kreisprüfer für Importe wird zuerst an einem künstlichen Kreis erprobt.
- **Tests gegen die bequeme Abkürzung:** Ein Round-Trip-Test mit `==` wäre
  wertlos, weil `Kunde.__eq__` nur die Nummer vergleicht — ein eigener Test
  belegt das mit drei verfälschten Feldern.
- **Ränder:** gültiges JSON mit unbrauchbarem Inhalt, eine Version als Liste,
  ein gesperrtes Verzeichnis — und jeweils die Prüfung, dass nichts
  zurückbleibt.

## Was dieses Projekt nicht ist

Keine Nebenläufigkeit: Zwei Prozesse, die gleichzeitig speichern, überschreiben
sich — ohne Datenverlust, aber der letzte gewinnt. Keine Benutzeroberfläche.
Und zwei Dateien (Kunden und Notizen) sind je für sich atomar, aber nicht
gemeinsam; die Reihenfolge beim Schreiben ist so gewählt, dass ein Abbruch
dazwischen sichtbar statt still bleibt. Für mehr fehlt eine Datenbank — die
kommt im nächsten Abschnitt des Lernwegs.

## Lizenz

MIT — siehe [LICENSE](LICENSE).
