"""Contextmanager zum Protokollieren von Fehlern."""

from dataclasses import dataclass, field
from types import TracebackType


# ============================================================================
# Kuer Woche 7: eigener Contextmanager
# ============================================================================
@dataclass(eq=False)
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

    # Seit Woche 10 eine dataclass. Die drei Felder ersetzen das bisherige
    # __init__.
    #
    # meldungen: field(default_factory=list) statt `= []`. Das ist die
    # Mutable-Default-Falle aus Woche 1 (Notizen.md, ganz oben): Ein `= []`
    # als Default entsteht EINMAL beim Definieren der Klasse und wird von
    # allen Instanzen geteilt — die Meldungen von Import A stuenden auch in
    # Import B. default_factory ruft list() fuer JEDE Instanz neu auf.
    # @dataclass laesst `= []` gar nicht erst zu und wirft beim Bauen der
    # Klasse einen ValueError.
    #
    # init=False: meldungen ist ein Ergebnis, kein Parameter. Niemand soll
    # Fehlerprotokoll("x", False, ["erfunden"]) schreiben koennen.
    #
    # eq=False (am Dekorator): Zwei Protokolle mit gleicher Beschreibung sind
    # nicht "gleich" — es sind zwei verschiedene Vorgaenge. Ohne eq=False
    # wuerde @dataclass Wertgleichheit erzeugen und __hash__ auf None setzen.
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
