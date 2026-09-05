"""Contextmanager zum Protokollieren von Fehlern."""

from types import TracebackType


class Fehlerprotokoll:
    """Contextmanager: haelt fest, was im with-Block schiefging.

    Ein `with`-Block ist im Kern ein try/finally:

        with Fehlerprotokoll("Import") as p:   |  it = Fehlerprotokoll("Import")
            arbeite()                          |  p = it.__enter__()
                                               |  try:
                                               |      arbeite()
                                               |  finally:
                                               |      it.__exit__(typ, wert, tb)

    __enter__ laeuft VORHER und weiss deshalb nichts von Fehlern — hier gibt
    es nichts vorzubereiten, also nur `return self`, damit `as p` etwas
    bekommt. Die ganze Arbeit liegt in __exit__, das als einziges erfaehrt,
    ob etwas schiefging.

    Der Rueckgabewert von __exit__ entscheidet ueber die Exception:

        falsy (None, False)   sie fliegt weiter   <- Standardfall
        truthy (True)         sie wird GESCHLUCKT

    Da Python None zurueckgibt, wenn man nichts zurueckgibt, ist
    Weiterwerfen die Voreinstellung. Einen Fehler verschwinden zu lassen
    verlangt eine bewusste Handlung — dieselbe Haltung wie bei `except:`
    gegenueber `except Exception:`.

    Das Flag `schlucken` gibt es nur, damit sich beide Faelle im Test
    vergleichen lassen. Ein echter Contextmanager haette die Wahl selten.
    """

    def __init__(self, beschreibung: str, schlucken: bool = False) -> None:
        self.beschreibung = beschreibung
        self.schlucken = schlucken
        self.meldungen: list[str] = []

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
