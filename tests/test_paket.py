"""Paketstruktur und Typen: __all__, Importgraph, Annotationen, Vorfuehrung."""

import ast
import io
import os
import subprocess
import sys
import tokenize
from pathlib import Path

import kundenverwaltung
import kundenverwaltung.kunde as kunde_modul
from kundenverwaltung import Kunde

PAKET = Path(kundenverwaltung.__file__).parent
MODULE = sorted(PAKET.glob("*.py"))


def _importgraph() -> dict[str, set[str]]:
    """Wer importiert wen — nur relative Importe auf Modulebene.

    Importe in Funktionen oder unter `if TYPE_CHECKING` erzeugen zur Ladezeit
    keinen Zyklus und bleiben deshalb aussen vor.
    """
    return {
        datei.stem: {
            knoten.module.split(".")[0]
            for knoten in ast.parse(datei.read_text(encoding="utf-8")).body
            if isinstance(knoten, ast.ImportFrom) and knoten.level == 1 and knoten.module
        }
        for datei in MODULE
    }


def _kreis(graph: dict[str, set[str]]) -> list[str] | None:
    """Tiefensuche: Trifft sie auf ein Modul, das gerade noch offen ist, gibt es einen Kreis."""
    zustand: dict[str, str] = {}

    def besuche(modul: str, pfad: list[str]) -> list[str] | None:
        zustand[modul] = "offen"
        for nachbar in sorted(graph.get(modul, set())):
            if zustand.get(nachbar) == "offen":
                return [*pfad, modul, nachbar]
            if nachbar not in zustand:
                gefunden = besuche(nachbar, [*pfad, modul])
                if gefunden:
                    return gefunden
        zustand[modul] = "fertig"
        return None

    for modul in sorted(graph):
        if modul not in zustand:
            gefunden = besuche(modul, [])
            if gefunden:
                return gefunden
    return None


# --- Schnittstelle ---------------------------------------------------------

def test_alles_aus_all_ist_importierbar() -> None:
    fehlend = [name for name in kundenverwaltung.__all__ if not hasattr(kundenverwaltung, name)]
    assert fehlend == []


def test_interne_hilfen_stehen_nicht_in_all() -> None:
    assert not any(name.startswith("_") for name in kundenverwaltung.__all__)


# --- Importgraph -----------------------------------------------------------

def test_kreispruefer_findet_einen_kuenstlichen_kreis() -> None:
    """Gegenprobe — sonst waere der naechste Test auch mit einem blinden Pruefer gruen."""
    assert _kreis({"a": {"b"}, "b": {"a"}}) == ["a", "b", "a"]


def test_paket_hat_keinen_importzyklus() -> None:
    assert _kreis(_importgraph()) is None


def test_im_paket_wird_relativ_importiert() -> None:
    """Innen relativ, damit sich das Paket umbenennen laesst; aussen absolut."""
    absolut = [
        f"{datei.name}:{knoten.lineno}"
        for datei in MODULE
        for knoten in ast.walk(ast.parse(datei.read_text(encoding="utf-8")))
        if isinstance(knoten, ast.ImportFrom)
        and knoten.level == 0
        and (knoten.module or "").startswith("kundenverwaltung")
    ]
    assert absolut == []


# --- Typen -----------------------------------------------------------------

def test_jede_funktion_ist_vollstaendig_annotiert() -> None:
    """Strenger als mypy --strict: Das laesst ein __init__ ohne `-> None`
    durch, sobald ein Parameter annotiert ist."""
    luecken: list[str] = []
    for datei in MODULE:
        for f in ast.walk(ast.parse(datei.read_text(encoding="utf-8"))):
            if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if f.returns is None:
                    luecken.append(f"{datei.name}:{f.lineno} {f.name} ohne Rueckgabetyp")
                for arg in [*f.args.posonlyargs, *f.args.args, *f.args.kwonlyargs]:
                    if arg.annotation is None and arg.arg not in ("self", "cls"):
                        luecken.append(f"{datei.name}:{f.lineno} {f.name}({arg.arg})")
    assert luecken == []


def test_keine_schlupfloecher_fuer_mypy() -> None:
    """Kein `type: ignore`-Kommentar, kein cast()-Aufruf. Geprueft am Code,
    nicht am Text — ein Docstring darf beides erwaehnen."""
    funde: list[str] = []
    for datei in MODULE:
        text = datei.read_text(encoding="utf-8")
        for knoten in ast.walk(ast.parse(text)):
            if isinstance(knoten, ast.Call) and getattr(knoten.func, "id", None) == "cast":
                funde.append(f"{datei.name}:{knoten.lineno} cast()")
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT and "type: ignore" in token.string:
                funde.append(f"{datei.name}:{token.start[0]} type: ignore")
    assert funde == []


def test_type_checking_import_existiert_zur_laufzeit_nicht() -> None:
    """InfoFaehig steht in kunde.py nur in Annotationen und wird deshalb nur
    fuer mypy importiert. Die Annotation bleibt Text."""
    assert not hasattr(kunde_modul, "InfoFaehig")
    assert Kunde.komponente_hinzufuegen.__annotations__["komponente"] == "InfoFaehig"


# --- Vorfuehrung -----------------------------------------------------------

def test_vorfuehrung_laeuft_mit_python_m() -> None:
    umgebung = {**os.environ, "PYTHONPATH": str(PAKET.parent)}
    lauf = subprocess.run(
        [sys.executable, "-m", "kundenverwaltung"],
        capture_output=True, text=True, env=umgebung, timeout=30,
    )
    assert lauf.returncode == 0, lauf.stderr
    assert "Grosskunde" in lauf.stdout and "gesperrt" in lauf.stdout
