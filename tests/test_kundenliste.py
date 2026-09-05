"""Kundenliste: Container-Protokoll, Slicing, Iterator."""

import pytest

from kundenverwaltung import Kunde, Kundenliste, KundenlisteIterator


# --- Aufbau ----------------------------------------------------------------

def test_leere_liste_ohne_argument() -> None:
    assert len(Kundenliste()) == 0


def test_konstruktor_kopiert_die_uebergebene_liste() -> None:
    """Ohne Kopie zeigten Aufrufer und Kundenliste auf dasselbe Objekt — wer
    die Ausgangsliste anfasst, veraenderte den Container mit."""
    ausgang = [Kunde("A", "a@example.de")]
    liste = Kundenliste(ausgang)
    ausgang.append(Kunde("B", "b@example.de"))
    assert len(liste) == 1


def test_hinzufuegen_ist_der_einzige_schreibzugriff() -> None:
    """Komposition statt Vererbung: beim Erben von list waeren append,
    extend, insert, sort und clear alle mit dabei."""
    liste = Kundenliste()
    liste.hinzufuegen(Kunde("A", "a@example.de"))
    assert len(liste) == 1
    assert not hasattr(liste, "append")
    assert not hasattr(liste, "sort")


# --- Container-Protokoll ---------------------------------------------------

def test_laenge_und_indexzugriff(kundenliste: Kundenliste) -> None:
    assert len(kundenliste) == 3
    assert kundenliste[0].name == "Klein"
    assert kundenliste[-1].name == "Gross"


def test_zu_grosser_index_wirft_indexerror(kundenliste: Kundenliste) -> None:
    """Der IndexError ist nicht nur ein Fehler, sondern das Stoppsignal fuer
    das alte Sequenzprotokoll."""
    with pytest.raises(IndexError):
        kundenliste[99]


def test_for_schleife_liefert_die_einfuegereihenfolge(kundenliste: Kundenliste) -> None:
    assert [k.name for k in kundenliste] == ["Klein", "Mittel", "Gross"]


def test_jeder_durchlauf_startet_neu(kundenliste: Kundenliste) -> None:
    """__iter__ muss bei jedem Aufruf einen frischen Iterator liefern.

    Gaebe es nur einen, waere die Liste nach dem ersten Durchlauf leer.
    """
    assert list(kundenliste) == list(kundenliste)


def test_verschachtelte_schleifen_stoeren_sich_nicht(kundenliste: Kundenliste) -> None:
    """Der schaerfere Fall: hier leben zwei Iteratoren gleichzeitig statt
    nacheinander. Laege die Position im Container, kaemen 2 Paare heraus."""
    paare = [(a.name, b.name) for a in kundenliste for b in kundenliste]
    assert len(paare) == 9


# --- Mitgliedschaft --------------------------------------------------------

def test_in_findet_enthaltene_kunden(kundenliste: Kundenliste) -> None:
    assert kundenliste[0] in kundenliste
    assert Kunde("Fremd", "fremd@example.de") not in kundenliste


def test_in_vergleicht_mit_gleichheit_nicht_mit_identitaet(
    kundenliste: Kundenliste,
) -> None:
    """Kunde.__eq__ haengt an der nummer — also findet `in` auch einen
    anderen Kunden mit derselben Nummer."""
    zwilling = Kunde("Ganz anderer Name", "zwilling@example.de")
    zwilling._nummer = kundenliste[0].nummer
    assert zwilling is not kundenliste[0]
    assert zwilling in kundenliste


@pytest.mark.parametrize("fremd", ["ein String", 1042, None], ids=["str", "int", "None"])
def test_in_mit_fremdtyp_liefert_false(kundenliste: Kundenliste, fremd: object) -> None:
    """__contains__ darf hier kein NotImplemented zurueckgeben: es gibt
    keinen Spiegelpartner, und der Rueckgabewert laeuft durch bool() —
    bool(NotImplemented) ist True."""
    assert (fremd in kundenliste) is False


# --- Slicing ---------------------------------------------------------------

def test_slice_liefert_wieder_eine_kundenliste(kundenliste: Kundenliste) -> None:
    """So verhalten sich auch die eingebauten Typen: list[1:3] ist eine list."""
    ausschnitt = kundenliste[1:3]
    assert isinstance(ausschnitt, Kundenliste)
    assert len(ausschnitt) == 2
    assert ausschnitt[0].name == "Mittel"


def test_ausschnitt_ist_eigenstaendig(kundenliste: Kundenliste) -> None:
    ausschnitt = kundenliste[1:3]
    ausschnitt.hinzufuegen(Kunde("Neu", "neu@example.de"))
    assert len(kundenliste) == 3


# --- Sortierung ------------------------------------------------------------

def test_sorted_funktioniert_ohne_key(kundenliste: Kundenliste) -> None:
    """sorted() iteriert sein Argument — dank __iter__ geht das auch mit
    einer Kundenliste, nicht nur mit einer gewoehnlichen list."""
    unsortiert = Kundenliste([kundenliste[2], kundenliste[0], kundenliste[1]])
    assert [k.umsatz for k in sorted(unsortiert)] == [50, 10_000, 100_000]


# --- Darstellung -----------------------------------------------------------

def test_repr_nennt_die_eigene_klasse(kundenliste: Kundenliste) -> None:
    """Ohne den Klassennamen waere die Ausgabe von einer echten Liste nicht
    zu unterscheiden."""
    assert repr(kundenliste).startswith("Kundenliste(")
    assert "Kunde(" in repr(kundenliste)


# --- Der handgebaute Iterator ---------------------------------------------

def test_iterator_liefert_alle_elemente_und_endet(kundenliste: Kundenliste) -> None:
    it = KundenlisteIterator(list(kundenliste))
    assert [next(it).name for _ in range(3)] == ["Klein", "Mittel", "Gross"]
    with pytest.raises(StopIteration):
        next(it)


def test_iterator_gibt_bei_iter_sich_selbst_zurueck(kundenliste: Kundenliste) -> None:
    """Ein Iterator ist selbst iterierbar. Gaebe er ein neues Objekt heraus,
    spraenge die Position bei jedem `for` auf 0 zurueck."""
    it = KundenlisteIterator(list(kundenliste))
    assert iter(it) is it
