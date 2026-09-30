"""Lernexperimente: was PYTHON tut, nicht was das Projekt tut.

WAS HIER HINEINGEHOERT — das Kriterium
    Diese Tests wuerden auch dann noch etwas belegen, wenn es die
    Kundenverwaltung gar nicht gaebe. Sie pruefen Sprachverhalten: wie
    @dataclass Methoden erzeugt, was frozen wirklich verspricht, wie Python
    auf einen Importzyklus reagiert, was mypy aus einem Generic ableitet.

    Sie stehen hier und nicht in den Themendateien, weil sie einen anderen
    Abnehmer haben. Ein Testlauf der Themendateien beantwortet "funktioniert
    das Projekt?". Dieser hier beantwortet "habe ich Python richtig
    verstanden?". Beides ist wertvoll, aber das Erste muss schnell sein und
    bei jeder Aenderung laufen.

WAS NICHT HIERHER GEHOERT
    Tests, die eine Projektentscheidung absichern — auch wenn sie nebenbei
    Sprachverhalten zeigen. "Adresse ist frozen" gehoert zu Adresse.
    "object.__setattr__ kommt an frozen vorbei" gehoert hierher.

SCHNELLER LAUF IM ALLTAG
    Die Experimente mit Subprozessen (Importzyklus, mypy) dauern laenger als
    die ganze uebrige Suite. Sie sind mit @pytest.mark.langsam markiert:

        pytest -m "not langsam"     # nur die schnellen
        pytest                      # alles
"""

import ast
import importlib.util
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError, dataclass, field
from pathlib import Path
from typing import Any

import pytest

from kundenverwaltung import (
    Adresse,
    InfoFaehig,
    Kunde,
    Kundenliste,
    Notiz,
)

MYPY_DA = importlib.util.find_spec("mypy") is not None


# ===========================================================================
# frozen ist eine Zusage, kein Tresor (Woche 10, Dienstag)
# ===========================================================================

def test_frozen_weist_die_normale_zuweisung_ab() -> None:
    adresse = Adresse("Hauptstrasse", "1", "10115", "Berlin")
    with pytest.raises(FrozenInstanceError):
        adresse.plz = "20095"  # type: ignore[misc]


def test_object_setattr_kommt_an_frozen_vorbei() -> None:
    """Die Grenze der Zusage. frozen schuetzt vor Versehen, nicht vor Absicht:
    @dataclass baut ein __setattr__, das wirft — object.__setattr__ geht
    daran vorbei, weil es die Klasse gar nicht erst fragt."""
    adresse = Adresse("Hauptstrasse", "1", "10115", "Berlin")
    object.__setattr__(adresse, "plz", "20095")
    assert adresse.plz == "20095"


def test_der_hash_wird_dabei_inkonsistent() -> None:
    """Und das ist der Grund, warum man es nicht tut: Das Objekt liegt danach
    im falschen Fach (Woche 6, das Fach-Gleichnis)."""
    adresse = Adresse("Hauptstrasse", "1", "10115", "Berlin")
    menge = {adresse}
    object.__setattr__(adresse, "plz", "20095")
    assert adresse not in menge, "es ist in seiner eigenen Menge nicht mehr auffindbar"


# ===========================================================================
# Was @dataclass erzeugt — und wo es nicht passt (Woche 10, Montag/Donnerstag)
# ===========================================================================

def test_dataclass_erzeugt_init_repr_und_eq() -> None:
    @dataclass
    class Punkt:
        x: int
        y: int = 0

    assert Punkt(1, 2) == Punkt(1, 2)
    # endswith statt ==: Das erzeugte __repr__ benutzt __qualname__, und bei
    # einer in einer Funktion definierten Klasse steht da
    # "test_...<locals>.Punkt". Im Modul-Massstab — also bei Adresse — ist es
    # der schlichte Klassenname.
    assert repr(Punkt(1)).endswith("Punkt(x=1, y=0)")
    assert repr(Adresse("A", "1", "12345", "O")).startswith("Adresse(")


def test_dataclass_verbietet_veraenderliche_defaults() -> None:
    """Die Mutable-Default-Falle aus Woche 1 — @dataclass laesst sie gar
    nicht erst zu, statt sie zur Laufzeit zuschlagen zu lassen."""
    with pytest.raises(ValueError, match="mutable default"):
        @dataclass
        class Kaputt:
            eintraege: list[str] = []


def test_default_factory_gibt_jeder_instanz_eine_eigene_liste() -> None:
    @dataclass
    class Protokoll:
        meldungen: list[str] = field(default_factory=list)

    a, b = Protokoll(), Protokoll()
    a.meldungen.append("nur bei a")
    assert b.meldungen == []


def test_erzeugtes_eq_vergleicht_alle_felder() -> None:
    """Bruchstelle 4 aus dem dataclass-Versuch mit Kunde: Das Projekt hat in
    Woche 6 entschieden, dass gleiche NUMMER gleicher Kunde heisst — auch bei
    anderem Umsatz. Das erzeugte __eq__ kann das nicht."""
    @dataclass
    class KundeAlsDataclass:
        name: str
        umsatz: float = 0.0

    assert KundeAlsDataclass("A", 1.0) != KundeAlsDataclass("A", 2.0)


def test_order_sortiert_nach_feldreihenfolge() -> None:
    """Bruchstelle 5: order=True sortiert nach dem ERSTEN Feld, nicht nach
    dem fachlich richtigen. Kunde sortiert nach Umsatz, dann Nummer."""
    @dataclass(order=True)
    class Eintrag:
        name: str
        umsatz: float = 0.0

    assert sorted([Eintrag("B", 1.0), Eintrag("A", 99.0)])[0].name == "A"


def test_frozen_sperrt_alles_oder_nichts() -> None:
    """Bruchstelle 6: Ein einzelnes Feld read-only zu machen geht nicht —
    frozen gilt fuer die ganze Klasse."""
    @dataclass(frozen=True)
    class NurName:
        name: str
        umsatz: float = 0.0

    with pytest.raises(FrozenInstanceError):
        NurName("A").umsatz = 100.0  # type: ignore[misc]


# ===========================================================================
# NamedTuple gegen dict (Woche 10, Donnerstag)
# ===========================================================================

def test_dict_legt_bei_einem_tippfehler_still_einen_schluessel_an() -> None:
    """Der Grund fuer Geladen als NamedTuple: Beim dict faellt derselbe
    Tippfehler weder zur Laufzeit noch bei mypy auf."""
    daten: dict[str, object] = {"kunden": [], "waisen": []}
    daten["wiasen"] = [1]
    assert "wiasen" in daten and daten["waisen"] == []


def test_entpacken_eines_dict_liefert_die_schluessel() -> None:
    a, b = {"kunden": [1], "waisen": [2]}
    assert (a, b) == ("kunden", "waisen"), "nicht die Werte"


# ===========================================================================
# LBYL gegen EAFP (Woche 7, Donnerstag)
# ===========================================================================

class OhneInfo:
    """Hat kein info() — der Fall, den LBYL abfangen soll."""


class InfoKracht:
    """Hat info(), aber es wirft AttributeError von INNEN."""

    def info(self) -> str:
        return self.gibts_nicht  # type: ignore[attr-defined,no-any-return]


def _lbyl(objekt: object) -> str:
    # Nebenbei sichtbar an den ignore-Codes: mypy versteht hasattr() als
    # Typverengung und weiss danach, dass info() existiert — attr-defined
    # braucht es hier NICHT. Beim try/except unten schon, denn ein
    # except-Zweig verengt nichts. Auch der Typechecker findet LBYL leichter
    # nachvollziehbar als EAFP.
    if hasattr(objekt, "info"):
        return objekt.info()  # type: ignore[no-any-return]
    return "kein info()"


def _eafp(objekt: object) -> str:
    try:
        return objekt.info()  # type: ignore[attr-defined, no-any-return]
    except AttributeError:
        return "kein info()"


def test_beide_erkennen_die_fehlende_methode() -> None:
    assert _lbyl(OhneInfo()) == _eafp(OhneInfo()) == "kein info()"


def test_eafp_verschluckt_einen_echten_bug() -> None:
    """Der Grund, warum das Projekt beides kombiniert: EAFP faengt mehr ab
    als gewollt. Ein AttributeError AUS der Methode wird faelschlich als
    "kein info()" gemeldet — der Bug bleibt unsichtbar."""
    assert _eafp(InfoKracht()) == "kein info()", "faelschlich als fehlend gemeldet"
    with pytest.raises(AttributeError):
        _lbyl(InfoKracht())


def test_das_projekt_meldet_beide_faelle_getrennt() -> None:
    """Kunde.info() unterscheidet: fehlende Methode und kaputte Methode
    bekommen verschiedene Marker."""
    kunde = Kunde("Test", "test@example.de")
    kunde.komponente_hinzufuegen(InfoKracht())
    assert "fehlgeschlagen" in kunde.info()


# ===========================================================================
# Protocol prueft die Struktur, nicht die Abstammung (Woche 5/7)
# ===========================================================================

def test_protocol_erfuellt_wer_die_methode_hat() -> None:
    assert isinstance(Notiz("x"), InfoFaehig)


def test_protocol_prueft_zur_laufzeit_nur_die_anwesenheit() -> None:
    """runtime_checkable sieht die Signatur NICHT — nur, dass der Name da
    ist. Ein info(), das die falschen Argumente nimmt, gilt trotzdem."""
    class FalscheSignatur:
        def info(self, unerwartet: int) -> str:
            return "x"

    assert isinstance(FalscheSignatur(), InfoFaehig)


# ===========================================================================
# Der Rueckgabewert von __exit__ (Woche 7, Kuer)
# ===========================================================================

@pytest.mark.parametrize("rueckgabe, fliegt_weiter", [(False, True), (None, True), (True, False)])
def test_truthy_rueckgabe_schluckt_die_exception(
    rueckgabe: object, fliegt_weiter: bool
) -> None:
    """Deshalb hat KundenDatei.__exit__ den Typ Literal[False] und nicht bool:
    Wer `-> bool` schreibt, kuendigt an, dass er moeglicherweise schluckt."""
    class Manager:
        def __enter__(self) -> "Manager":
            return self

        def __exit__(self, *args: object) -> object:
            return rueckgabe

    geflogen = False
    try:
        with Manager():
            raise ValueError("x")
    except ValueError:
        geflogen = True
    assert geflogen is fliegt_weiter


def test_try_finally_speichert_auch_im_fehlerfall() -> None:
    """Die Gegenprobe aus Woche 9, Kuer: Ein Kontextmanager mit try/finally
    sieht sauberer aus und BRICHT die transaktionale Entscheidung — finally
    laeuft immer, also landet die halbe Arbeit im Speicher."""
    from contextlib import contextmanager
    from collections.abc import Generator

    gespeichert: list[str] = []

    @contextmanager
    def mit_finally() -> Generator[list[str], None, None]:
        arbeit: list[str] = []
        try:
            yield arbeit
        finally:
            gespeichert.extend(arbeit)

    with pytest.raises(ValueError):
        with mit_finally() as arbeit:
            arbeit.append("halb fertig")
            raise ValueError("Abbruch")
    assert gespeichert == ["halb fertig"], "finally hat trotz Fehler gespeichert"


# ===========================================================================
# Type Hints aendern das Laufzeitverhalten nicht (Woche 11, Freitag)
# ===========================================================================

def test_die_laufzeit_prueft_keine_typen() -> None:
    def verdoppeln(x: int) -> int:
        return x * 2

    assert verdoppeln("ab") == "abab"  # type: ignore[arg-type, comparison-overlap]


def test_annotationen_ohne_future_werden_ausgewertet() -> None:
    """Ohne `from __future__ import annotations` wertet Python eine
    Annotation beim Definieren aus — ein unbekannter Name wirft sofort."""
    with pytest.raises(NameError):
        exec("def f(x: GibtsNicht) -> None: ...", {})


def test_mit_future_bleibt_die_annotation_text() -> None:
    umgebung: dict[str, Any] = {}
    exec("from __future__ import annotations\n"
         "def f(x: GibtsNicht) -> None: ...", umgebung)
    assert umgebung["f"].__annotations__["x"] == "GibtsNicht"


# ===========================================================================
# Langsam: Subprozesse (Woche 11)
# ===========================================================================

@pytest.mark.langsam
def test_ein_importzyklus_scheitert_mit_partially_initialized(tmp_path: Path) -> None:
    """Genau das waere entstanden, wenn json_atomar_schreiben in Woche 9 in
    persistenz.py geblieben waere — und genau das haette eine Weiterleitung
    in Kundenliste in Woche 12 wieder erzeugt.

    Eigener Prozess, damit kein Modul aus einem vorigen Versuch im Speicher
    haengt."""
    paket = tmp_path / "zyklus"
    paket.mkdir()
    (paket / "__init__.py").write_text("", encoding="utf-8")
    (paket / "kundenliste.py").write_text(
        "from .persistenz import speichern_hilfe\n\n"
        "class Kundenliste:\n"
        "    def speichern(self) -> None:\n"
        "        speichern_hilfe(self)\n", encoding="utf-8")
    (paket / "persistenz.py").write_text(
        "from .kundenliste import Kundenliste\n\n"
        "def speichern_hilfe(liste: Kundenliste) -> None:\n"
        "    print('gespeichert')\n", encoding="utf-8")

    lauf = subprocess.run(
        [sys.executable, "-c", "import zyklus.kundenliste as k; k.Kundenliste().speichern()"],
        cwd=tmp_path, capture_output=True, text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert lauf.returncode != 0
    assert "partially initialized module" in lauf.stderr
    assert "circular import" in lauf.stderr


@pytest.mark.langsam
@pytest.mark.skipif(not MYPY_DA, reason="mypy nicht installiert")
def test_generic_laesst_mypy_den_konkreten_typ_ableiten(tmp_path: Path) -> None:
    """Was `[T: Tier]` bringt, gemessen statt behauptet — die Begruendung
    fuer erste() in Kunde.aus_dict()."""
    (tmp_path / "demo.py").write_text(
        "class Tier: ...\n\n"
        "class Hund(Tier):\n"
        "    def bellen(self) -> str:\n"
        "        return 'wuff'\n\n"
        "def ohne(werte: list[Tier], typ: type[Tier]) -> Tier | None:\n"
        "    return next((w for w in werte if isinstance(w, typ)), None)\n\n"
        "def mit[T: Tier](werte: list[Tier], typ: type[T]) -> T | None:\n"
        "    return next((w for w in werte if isinstance(w, typ)), None)\n\n"
        "tiere: list[Tier] = [Tier(), Hund()]\n"
        "reveal_type(ohne(tiere, Hund))\n"
        "reveal_type(mit(tiere, Hund))\n"
        "a = ohne(tiere, Hund)\n"
        "if a is not None:\n"
        "    a.bellen()\n"
        "b = mit(tiere, Hund)\n"
        "if b is not None:\n"
        "    b.bellen()\n", encoding="utf-8")

    lauf = subprocess.run([sys.executable, "-m", "mypy", "--strict", "demo.py"],
                          cwd=tmp_path, capture_output=True, text=True)
    assert 'Revealed type is "demo.Tier | None"' in lauf.stdout
    assert 'Revealed type is "demo.Hund | None"' in lauf.stdout
    assert '"Tier" has no attribute "bellen"' in lauf.stdout
    assert lauf.stdout.count("error:") == 1, "nur die Variante ohne Generic darf scheitern"


# ===========================================================================
# Die drei Haertungsvarianten im Projekt selbst (Woche 7, Donnerstag)
# ===========================================================================
# info_lbyl() und info_eafp() sind Lerncode auf Kunde: Sie haben keinen
# Aufrufer und stehen nur da, damit man die drei Varianten nebeneinander
# sieht. Getestet werden sie hier und nicht in test_kunde.py, weil sie eine
# SPRACHFRAGE illustrieren und keine Projektfunktion sind.
#
# In REFACTORING.md, Teil 4 steht die offene Frage dazu: Lehrmaterial
# behalten oder Ballast entfernen? Solange sie da sind, werden sie geprueft.

def test_projekt_lbyl_faengt_nur_die_fehlende_methode() -> None:
    kunde = Kunde("Test", "test@example.de")
    kunde.komponente_hinzufuegen(OhneInfo())    # type: ignore[arg-type]
    assert "kein info()" in kunde.info_lbyl()

    kracht = Kunde("Test", "test2@example.de")
    kracht.komponente_hinzufuegen(InfoKracht())
    with pytest.raises(AttributeError):
        kracht.info_lbyl()


def test_projekt_eafp_meldet_einen_bug_faelschlich_als_fehlend() -> None:
    kunde = Kunde("Test", "test@example.de")
    kunde.komponente_hinzufuegen(InfoKracht())
    assert "kein info()" in kunde.info_eafp(), "der echte Bug ist unsichtbar"


def test_die_variante_die_bleibt_unterscheidet_beide_faelle() -> None:
    kunde = Kunde("Test", "test@example.de")
    kunde.komponente_hinzufuegen(OhneInfo())    # type: ignore[arg-type]
    kunde.komponente_hinzufuegen(InfoKracht())
    ausgabe = kunde.info()
    assert "kein info()" in ausgabe and "fehlgeschlagen" in ausgabe
