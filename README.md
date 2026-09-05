# Kundenverwaltung

Eine objektorientierte Kundenverwaltung in Python — entstanden als
Lernprojekt, das über acht Wochen schrittweise gewachsen ist. Der Fokus liegt
nicht auf dem Funktionsumfang, sondern auf den Designentscheidungen: warum
Komposition statt Vererbung, wann ein ABC und wann ein Protocol, und wie eine
Fehlerhierarchie aussieht, die einem Aufrufer tatsächlich hilft.

Keine externen Abhängigkeiten. `mypy --strict` läuft sauber durch, 108 Tests
in unter einer Sekunde.

```python
from kundenverwaltung import Kunde, Kundenliste, GeschaeftsDaten

anna = Kunde("Anna Beispiel", "anna@example.de",
             geschaefts_daten=GeschaeftsDaten("Beispiel GmbH", "DE123456789"))
anna.umsatz = 150_000

print(anna)                    # 1000 Anna Beispiel <anna@example.de> — Kunde ist ein Grosskunde
print(anna.is_grosskunde())    # True

liste = Kundenliste([anna])
liste.hinzufuegen(Kunde("Bob", "bob@example.de"))

for kunde in sorted(liste):    # sortiert nach Umsatz, ohne key-Argument
    print(kunde.name)
```

## Loslegen

```bash
git clone https://github.com/oibafdiger/kundenverwaltung.git
cd kundenverwaltung
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest              # 108 Tests
mypy --strict src tests
```

## Aufbau

```
src/kundenverwaltung/
  exceptions.py     Fehlerhierarchie — eine Basis, sechs Unterklassen
  komponenten.py    InfoLieferant (ABC), InfoFaehig (Protocol), Datenklassen
  kunde.py          Kunde und ExportierbarMixin
  kundenliste.py    Container mit vollem Protokoll, eigener Iterator
  protokoll.py      Fehlerprotokoll (Contextmanager)

tests/              vier Dateien, nach Thema getrennt
beispieldaten/      CSV mit absichtlich kaputten Zeilen
```

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

Mit Komposition delegiert die Grenze an die Komponente, die sie kennt:

```python
def grosskunde_grenze(self) -> int:
    if self.großkunden_daten:
        return self.großkunden_daten.GROSSKUNDE_GRENZE   # 500.000
    if self.geschaefts_daten:
        return self.geschaefts_daten.GROSSKUNDE_GRENZE   # 100.000
    return Kunde.GROSSKUNDE_GRENZE                       #  10.000
```

Der Preis ist mehr Code — die Delegation muss man ausschreiben. Der Gewinn
ist, dass ein Kunde mehrere Rollen gleichzeitig haben kann, was mit
Einfachvererbung nicht ging.

Ein Regressionstest hält den ursprünglichen Bug fest, damit er nicht
zurückkommt.

### ABC **und** Protocol, für verschiedene Zwecke

Beides steht im Projekt, und zwar nicht aus Unentschlossenheit:

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
an der `Kunde` Fremdes annimmt. Dort zählt nur, ob ein Objekt `info()` kann;
woher es stammt, ist gleichgültig. Die Klasse `Notiz` erbt von nichts und
funktioniert trotzdem.

Die Faustregel dahinter: **ABC für Code, den man besitzt. Protocol für Code,
den man annimmt.**

### Eine flache Fehlerhierarchie

```
KundenverwaltungError
├── KundeNichtGefundenError
├── UnbekannteKomponenteError
├── UngueltigeEmailError
├── UngueltigerNameError
├── UngueltigerBetragError
└── CsvFormatError
```

Die gemeinsame Basis lässt dem **Aufrufer** die Wahl der Granularität — er
fängt `KundenverwaltungError` für alles oder eine Unterklasse für den
Einzelfall. Ebenso wichtig ist, was sie **ausschließt**: `TypeError` und
`AttributeError` aus echten Programmierfehlern bleiben draußen und schlagen
durch.

Bewusst **flach**: Eine Zwischenebene wie `CsvError` wurde verworfen, weil sie
undicht gewesen wäre. `aus_csv_zeile` baut einen Kunden und löst dabei die
Validierung im Setter aus — eine Zeile mit kaputter E-Mail wirft also
`UngueltigeEmailError`, keinen CSV-Fehler. Eine Gruppierung nach *Herkunft*
trägt nicht, solange die Fehler nach *Art* an verschiedenen Stellen entstehen.

Ebenso bewusst: Der `aktiv`-Setter wirft einen **`TypeError`** und gehört
nicht in diese Hierarchie. Er prüft mit `isinstance` den Typ, und ein falscher
Typ ist ein Bug am Aufrufort, kein Fachfehler.

### Fehler weiterreichen — mit oder ohne Ursache

```python
# Der KeyError verrät nur die interne Mechanik → verschweigen
except KeyError:
    raise UnbekannteKomponenteError(...) from None

# Der OSError verrät, WAS los war (fehlt? gesperrt? Rechte?) → weiterreichen
except OSError as e:
    raise CsvFormatError(f"Datei nicht lesbar: {pfad!r}") from e
```

Die Leitfrage: Hilft die untere Exception jemandem, der die Meldung liest?
`from None`, wenn sie nur verrät, *wie* intern nachgesehen wurde. `from e`,
wenn sie verrät, *was* wirklich los war.

### Validierung beim Bauen statt beim Prüfen

Früher gab es ein `ValidierbarMixin` mit `fehler_melden()`, das Verstöße in
einer Liste sammelte. Zwei seiner drei Prüfungen konnten nie zuschlagen — die
Setter waren schneller, ein Kunde mit ungültiger E-Mail entsteht gar nicht
erst.

Sammeln und Werfen sind kein Gegensatz, sondern zwei Zeitpunkte: Sammeln
*vor* dem Bauen, Werfen *beim* Bauen. Ein Sammler braucht ein Objekt, das in
ungültigem Zustand existieren kann — genau das verhindern die Setter. Das
Mixin ist deshalb entfallen.

### Container-Protokoll

`Kundenliste` unterstützt `len()`, Indexzugriff, `in`, `for` und Slicing:

```python
liste[0]        # Kunde
liste[1:3]      # Kundenliste — ein Ausschnitt bleibt derselbe Typ
kunde in liste  # vergleicht mit ==, findet also auch einen Kunden
                # mit gleicher Nummer als anderes Objekt
```

Das Slicing ist per `@overload` typisiert, sodass `liste[0].name` für den
Typechecker eindeutig ein `Kunde` ist.

Der Container erbt **nicht** von `list` — sonst wären `append`, `extend`,
`insert`, `sort` und `clear` alle mit dabei. `hinzufuegen()` ist der einzige
Schreibzugriff.

## Tests

Vier Dateien nach Thema getrennt, `pytest.mark.parametrize` für die
Tabellenfälle. Ein paar Beispiele für die Art von Test, die hier steht:

- **Regressionstests** halten Fehler fest, die es wirklich gab — etwa den
  Fragile-Base-Class-Bug.
- **Gegenfälle** schärfen die Aussage: Ein Test, der belegt, dass zwei Kunden
  mit derselben Nummer gleich sind, ist erst zusammen mit dem Test aussagekräftig,
  dass zwei mit verschiedener Nummer es nicht sind.
- **Gegenproben zur Härtung**: „zehn Mülleingaben werfen einen Fachfehler"
  würde auch bestehen, wenn die Klasse *alles* ablehnte — die Gutfall-Zeile
  daneben schließt das aus.

## Was dieses Projekt nicht ist

Keine Persistenz, keine Nebenläufigkeit, keine Benutzeroberfläche. Die
Kundennummern kommen aus einem Klassenzähler und sind nicht prozessübergreifend
eindeutig. Für eine echte Anwendung fehlt die Datenschicht — die kommt im
nächsten Abschnitt des Lernwegs.
