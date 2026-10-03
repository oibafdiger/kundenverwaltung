"""Der Speicher-Vertrag: austauschbare Ablage hinter einer ABC (Woche 12).

Ein Refactoring hat zwei Seiten, und ein Test, der nur eine davon prueft,
belegt nichts:

    Verhalten unveraendert   -> nichts kaputtgemacht
    Struktur geaendert       -> es wurde wirklich umgebaut

Nur das Erste waere auch ohne jeden Umbau wahr. Nur das Zweite sagt nichts
darueber, ob es noch geht.
"""

import ast
from pathlib import Path

import pytest

import kundenverwaltung
from kundenverwaltung import (
    DateiInhaltError,
    DateiSpeicher,
    Geladen,
    GeschaeftsDaten,
    InMemorySpeicher,
    JSONNotizSpeicher,
    JSONSpeicher,
    Kunde,
    KundenDatei,
    Kundenliste,
    Notiz,
    NotizSpeicher,
    SQLiteSpeicher,
    Speicher,
)

# Der Paketordner wird aus dem IMPORTIERTEN Modul abgeleitet, nicht aus dem
# Ort dieser Datei. Im Vault liegt das Paket neben tests/, im Portfolio-Repo
# unter src/ — so stimmt der Pfad in beiden, ohne Sonderfall.
PAKET = Path(kundenverwaltung.__file__).parent


@pytest.fixture
def speicher_varianten(tmp_path: Path) -> dict[str, Speicher]:
    """Alle Implementierungen, damit derselbe Test ueber jede laufen kann.

    Seit dem SQL-Sprint (03.10.2026) drei. Die Tests unten heissen noch
    "beide_..." aus Woche 12; sie laufen unveraendert auch gegen
    SQLiteSpeicher, und genau das ist der Beleg, dass der Vertrag traegt.
    """
    return {
        "DateiSpeicher": DateiSpeicher(str(tmp_path / "kunden.json")),
        "InMemorySpeicher": InMemorySpeicher(),
        "SQLiteSpeicher": SQLiteSpeicher(str(tmp_path / "kunden.db")),
    }


# --- Der Vertrag -----------------------------------------------------------

def test_speicher_ist_abstrakt() -> None:
    """Eine ABC mit @abstractmethod ist keine Empfehlung, sondern eine Sperre."""
    with pytest.raises(TypeError, match="abstract"):
        Speicher()  # type: ignore[abstract]


def test_der_vertrag_verlangt_laden_und_speichern() -> None:
    assert {"laden", "speichern"} <= set(Speicher.__abstractmethods__)


def test_beide_implementierungen_erfuellen_den_vertrag(
    speicher_varianten: dict[str, Speicher]
) -> None:
    for name, speicher in speicher_varianten.items():
        assert isinstance(speicher, Speicher), name


def test_laden_liefert_ein_geladen(speicher_varianten: dict[str, Speicher]) -> None:
    for name, speicher in speicher_varianten.items():
        ergebnis = speicher.laden()
        assert isinstance(ergebnis, Geladen), name
        assert ergebnis.kunden == Kundenliste() or len(ergebnis.kunden) == 0


# --- Austauschbarkeit: derselbe Ablauf ueber beide -------------------------

def _durchlauf(speicher: Speicher) -> tuple[int, list[str], str, list[int]]:
    """Anlegen, speichern, neu laden — und melden, was zurueckkam."""
    with KundenDatei(speicher) as kunden:
        anna = Kunde("Anna", "anna@example.de",
                     geschaefts_daten=GeschaeftsDaten("Beispiel GmbH", "DE1"))
        anna.umsatz = 150_000
        anna.komponente_hinzufuegen(Notiz("Rueckruf"))
        kunden.hinzufuegen(anna)
        kunden.hinzufuegen(Kunde("Bob", "bob@example.de"))

    verwalter = KundenDatei(speicher)
    with verwalter as kunden:
        return len(kunden), [k.name for k in kunden], kunden[0].info(), verwalter.waisen


def test_beide_implementierungen_liefern_dasselbe(
    speicher_varianten: dict[str, Speicher]
) -> None:
    """Das eigentliche Akzeptanzkriterium: nicht "beide haben die Methoden",
    sondern derselbe Code laeuft ueber beide und kommt zum gleichen Ergebnis.
    Waere der Vertrag zu duenn, ginge das nicht."""
    ergebnisse = {name: _durchlauf(s) for name, s in speicher_varianten.items()}
    erstes = next(iter(ergebnisse.values()))
    for name, wert in ergebnisse.items():
        assert wert == erstes, name
    anzahl, namen, info, waisen = erstes
    assert anzahl == 2 and namen == ["Anna", "Bob"] and waisen == []
    assert "Rueckruf" in info


# --- InMemorySpeicher ist nicht nachsichtiger ------------------------------

def test_in_memory_baut_beim_laden_neu() -> None:
    """Ein Test-Double darf schneller sein als das Echte, aber nicht
    grosszuegiger. Deshalb legt InMemorySpeicher dicts ab und baut beim Laden
    neu — haette er die Objekte gehalten, waere er schneller ALS ECHT und
    wuerde Fehler durchlassen, die eine Datei aufdeckt."""
    ram = InMemorySpeicher()
    with KundenDatei(ram) as kunden:
        original = Kunde("Doppel", "doppel@example.de")
        kunden.hinzufuegen(original)

    with KundenDatei(ram) as kunden:
        assert kunden[0] is not original, "es muss neu gebaut werden"
        assert kunden[0] == original, "gleich soll es trotzdem sein (Nummer)"


def test_in_memory_durchlaeuft_dieselben_pruefungen() -> None:
    ram = InMemorySpeicher()
    ram.speichern(Kundenliste([Kunde("Egal", "egal@example.de")]), NotizSpeicher(), [])
    ram._kunden_daten["version"] = 99  # type: ignore[index]

    with pytest.raises(DateiInhaltError):
        ram.laden()


def test_in_memory_legt_keine_datei_an(tmp_path: Path) -> None:
    vorher = set(tmp_path.iterdir())
    ram = InMemorySpeicher()
    with KundenDatei(ram) as kunden:
        kunden.hinzufuegen(Kunde("Ohne Datei", "ohne@example.de"))
        kunden[0].komponente_hinzufuegen(Notiz("auch die Notiz bleibt im RAM"))
    with KundenDatei(ram) as kunden:
        assert "auch die Notiz" in kunden[0].info()
    assert set(tmp_path.iterdir()) == vorher


# --- DateiSpeicher: was nur diese Implementierung betrifft -----------------

def test_notizpfad_wird_abgeleitet(tmp_path: Path) -> None:
    pfad = tmp_path / "kunden.json"
    assert DateiSpeicher(str(pfad)).notiz_pfad == str(tmp_path / "kunden.notizen.json")


def test_eigener_notizpfad_gewinnt(tmp_path: Path) -> None:
    eigen = str(tmp_path / "woanders.json")
    assert DateiSpeicher(str(tmp_path / "k.json"), eigen).notiz_pfad == eigen


def test_datei_speicher_legt_beide_dateien_an(tmp_path: Path) -> None:
    pfad = tmp_path / "kunden.json"
    with KundenDatei(DateiSpeicher(str(pfad))) as kunden:
        kunden.hinzufuegen(Kunde("Auf Platte", "platte@example.de"))
        kunden[0].komponente_hinzufuegen(Notiz("liegt daneben"))
    assert pfad.exists() and (tmp_path / "kunden.notizen.json").exists()


def test_die_grenze_ist_dokumentiert() -> None:
    """Atomar gilt JE DATEI. Dass beide zusammen passen, folgt daraus nicht.
    Seit Woche 12 steht die Grenze bei DateiSpeicher statt bei NotizSpeicher —
    sie ist eine Eigenschaft DIESER Implementierung, nicht des Vertrags."""
    assert DateiSpeicher.__doc__ and "ZUSAMMEN" in DateiSpeicher.__doc__


# --- Die Abhaengigkeit ist umgedreht ---------------------------------------

def test_persistenz_kennt_nur_den_vertrag() -> None:
    """Der strukturelle Beleg fuer die Abhaengigkeitsumkehr.

    Gesucht wird ueber den AST, nicht im Text: Die Docstrings von KundenDatei
    ZEIGEN DateiSpeicher als Beispiel, benutzen ihn aber nicht. Eine
    Textsuche haette die Prosa fuer eine Abhaengigkeit gehalten."""
    quelle = (PAKET / "persistenz.py").read_text(encoding="utf-8")
    baum = ast.parse(quelle)

    aus_speicher = {
        n.name for k in baum.body
        if isinstance(k, ast.ImportFrom) and k.module == "speicher" for n in k.names
    }
    assert aus_speicher == {"Speicher"}

    benutzt = {k.id for k in ast.walk(baum) if isinstance(k, ast.Name)}
    for konkret in ("DateiSpeicher", "InMemorySpeicher", "JSONSpeicher", "JSONNotizSpeicher"):
        assert konkret not in benutzt


# --- Die aufgeteilten Container --------------------------------------------

@pytest.mark.parametrize(
    "container, dateiklasse",
    [(Kundenliste, JSONSpeicher), (NotizSpeicher, JSONNotizSpeicher)],
)
def test_container_koennen_nicht_mehr_speichern(
    container: type, dateiklasse: type
) -> None:
    """P2 und P3 aus REFACTORING.md. Der Test haelt ausserdem fest, dass die
    Methoden nicht als bequeme Weiterleitung zurueckkommen — das waere der
    Importzyklus."""
    for methode in ("speichern", "laden"):
        assert not hasattr(container, methode), f"{container.__name__}.{methode}"
        assert hasattr(dateiklasse, methode), f"{dateiklasse.__name__}.{methode}"


@pytest.mark.parametrize(
    "modul, verbotene_namen",
    [
        ("kundenliste.py", ("json", "open", "json_atomar_schreiben")),
        ("notizen.py", ("json", "open", "json_atomar_schreiben")),
    ],
)
def test_dateiwissen_ist_aus_den_containern_verschwunden(
    modul: str, verbotene_namen: tuple[str, ...]
) -> None:
    """hasattr allein griffe zu kurz: Eine private _speichern()-Hilfsmethode
    waere unsichtbar geblieben. Geprueft wird deshalb, dass die Namen im Modul
    gar nicht mehr vorkommen."""
    baum = ast.parse((PAKET / modul).read_text(encoding="utf-8"))
    benutzt = {k.id for k in ast.walk(baum) if isinstance(k, ast.Name)}
    for name in verbotene_namen:
        assert name not in benutzt, f"{modul} benutzt noch {name}"


def test_importrichtung_ist_einseitig() -> None:
    def importe(modul: str) -> set[str]:
        return {
            k.module.split(".")[0]
            for k in ast.parse((PAKET / modul).read_text(encoding="utf-8")).body
            if isinstance(k, ast.ImportFrom) and k.level == 1 and k.module
        }

    assert "kundenliste" in importe("speicher.py")
    assert "notizen" in importe("speicher.py")
    assert "speicher" not in importe("kundenliste.py")
    assert "speicher" not in importe("notizen.py")
