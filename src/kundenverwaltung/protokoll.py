"""Contextmanager zum Protokollieren von Fehlern."""

from dataclasses import dataclass, field
from types import TracebackType


# ============================================================================
# Kuer Woche 7: eigener Contextmanager
# ============================================================================
@dataclass(eq=False)
class Fehlerprotokoll:
    """Contextmanager: haelt fest, was im with-Block schiefging.

    Hier gibt es nichts vorzubereiten, also ist __enter__ nur `return self`,
    damit `as p` etwas bekommt. Die ganze Arbeit liegt in __exit__ — es
    erfaehrt als einziges, ob etwas schiefging.

    Das Flag `schlucken` steuert den Rueckgabewert von __exit__ und damit,
    ob die Exception weiterfliegt. Es gibt das Flag nur, damit sich beide
    Faelle im Test vergleichen lassen; ein echter Contextmanager haette die
    Wahl selten. Der Standardfall ist `False` — einen Fehler verschwinden zu
    lassen soll eine bewusste Handlung sein.
    """

    # Seit Woche 10 eine dataclass. Die drei Felder ersetzen das bisherige
    # __init__. Die drei Schalter sind jeweils eine Entscheidung:
    #
    #   default_factory  sonst teilten sich alle Protokolle EINE Liste — die
    #                    Meldungen von Import A stuenden auch in Import B.
    #   init=False       meldungen ist ein Ergebnis, kein Parameter. Niemand
    #                    soll Fehlerprotokoll("x", False, ["erfunden"]) bauen.
    #   eq=False         Zwei Protokolle mit gleicher Beschreibung sind nicht
    #                    "gleich" — es sind zwei verschiedene Vorgaenge.
    beschreibung: str
    schlucken: bool = False
    meldungen: list[str] = field(default_factory=list, init=False)

    def __enter__(self) -> "Fehlerprotokoll":
        return self

    def __exit__(
        self,
        exc_typ: type[BaseException] | None,
        exc_wert: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        # Der Typ kommt aus dem Wert statt aus exc_typ: fuer den Typechecker
        # sind die beiden Argumente unabhaengig, `exc_wert is not None` sagt
        # ihm nichts ueber exc_typ. exc_typ und exc_tb bleiben ungenutzt —
        # bei Contextmanagern der Normalfall.
        if exc_wert is not None:
            self.meldungen.append(
                f"{self.beschreibung}: {type(exc_wert).__name__}: {exc_wert}"
            )
        return self.schlucken
