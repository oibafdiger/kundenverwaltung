"""Fehlerhierarchie, Chaining und der Fehlerprotokoll-Contextmanager."""

import pytest

from kundenverwaltung import (
    CsvFormatError,
    DateiInhaltError,
    DateiNichtGefundenError,
    DateiNichtLesbarError,
    Fehlerprotokoll,
    InfoLieferant,
    Kunde,
    KundenCsv,
    KundeNichtGefundenError,
    KundenverwaltungError,
    UnbekannteKomponenteError,
    UngueltigeAdresseError,
    UngueltigeEmailError,
    UngueltigerBetragError,
    UngueltigerNameError,
)

FACHKLASSEN = [
    KundeNichtGefundenError,
    UnbekannteKomponenteError,
    UngueltigeEmailError,
    UngueltigerNameError,
    UngueltigerBetragError,
    UngueltigeAdresseError,
    CsvFormatError,
    DateiNichtGefundenError,
    DateiNichtLesbarError,
    DateiInhaltError,
]


# --- Aufbau der Hierarchie -------------------------------------------------

@pytest.mark.parametrize("klasse", FACHKLASSEN, ids=lambda k: k.__name__)
def test_fachklasse_haengt_unter_der_basis(klasse: type[Exception]) -> None:
    assert issubclass(klasse, KundenverwaltungError)


@pytest.mark.parametrize("klasse", FACHKLASSEN, ids=lambda k: k.__name__)
def test_fachklasse_erbt_nicht_von_valueerror(klasse: type[Exception]) -> None:
    """Die eigene Hierarchie soll die einzige Wahrheit sein.

    Wuerden die Klassen zusaetzlich von ValueError erben, koennte ein
    `except ValueError` sie mitfangen — und damit auch fremde Fehler.
    """
    assert not issubclass(klasse, ValueError)


def test_basis_erbt_von_exception_nicht_von_baseexception() -> None:
    """BaseException umfasst KeyboardInterrupt und SystemExit.

    Wer von dort erbt, wird von einem gewoehnlichen `except Exception` nicht
    mehr gefangen — und macht das Programm im Zweifel unabbrechbar.
    """
    assert issubclass(KundenverwaltungError, Exception)


# --- Jede Wurfstelle wirft die vorgesehene Klasse --------------------------

def test_unbekannter_registry_schluessel() -> None:
    with pytest.raises(UnbekannteKomponenteError) as info:
        InfoLieferant.erzeugt("quatsch")
    assert "quatsch" in str(info.value), "die Meldung nennt den falschen Schluessel"
    assert "privat" in str(info.value), "und die bekannten Schluessel"


def test_csv_zeile_mit_falscher_feldanzahl() -> None:
    with pytest.raises(CsvFormatError, match="3 Felder"):
        KundenCsv.aus_zeile("Anna;anna@example.de")


def test_csv_zeile_mit_unlesbarem_umsatz() -> None:
    with pytest.raises(CsvFormatError, match="muss eine Zahl sein"):
        KundenCsv.aus_zeile("Anna;anna@example.de;keine-zahl")


def test_ungueltige_email_beim_anlegen() -> None:
    with pytest.raises(UngueltigeEmailError):
        Kunde("Anna", "keine-email")


@pytest.mark.parametrize("name", ["", "   "], ids=["leer", "nur-leerzeichen"])
def test_leerer_name_beim_anlegen(name: str) -> None:
    with pytest.raises(UngueltigerNameError):
        Kunde(name, "anna@example.de")


def test_negativer_umsatz(kunde: Kunde) -> None:
    with pytest.raises(UngueltigerBetragError):
        kunde.umsatz = -5


@pytest.mark.parametrize("wert", ["gesperrt", True, None], ids=["str", "bool", "None"])
def test_zustand_mit_falschem_typ_wirft_typeerror(kunde: Kunde, wert: object) -> None:
    """Ein falscher TYP ist ein Programmierfehler, kein Fachfehler.

    Python trennt das: falscher Typ -> TypeError, richtiger Typ mit
    unzulaessigem Wert -> ValueError-artig. Diese Stelle gehoert deshalb
    bewusst NICHT in die eigene Hierarchie. Und genau hier faengt die Enum den
    Fall ab, den ein String durchgelassen haette: "gesperrt" ist ein Wort,
    kein Zustand.
    """
    with pytest.raises(TypeError):
        kunde.zustand = wert  # type: ignore[assignment]


# --- Fehlermeldungen tragen Kontext ---------------------------------------

def test_meldung_nennt_den_verstoss_nicht_die_regel(kunde: Kunde) -> None:
    """"Umsaetze muessen nicht-negativ sein" steht schon im Code.

    Was im Log fehlt, ist der Wert, der tatsaechlich ankam.
    """
    with pytest.raises(UngueltigerBetragError, match="-5"):
        kunde.umsatz = -5


def test_typfehler_nennt_den_erhaltenen_typ(kunde: Kunde) -> None:
    with pytest.raises(TypeError, match="str"):
        kunde.zustand = "gesperrt"  # type: ignore[assignment]


# --- Exception-Chaining ----------------------------------------------------

def test_from_e_legt_die_ursache_in_cause() -> None:
    """Der ValueError von float() sagt, WAS nicht lesbar war."""
    with pytest.raises(CsvFormatError) as info:
        KundenCsv.aus_zeile("Anna;anna@example.de;keine-zahl")
    assert isinstance(info.value.__cause__, ValueError)


def test_from_none_verschweigt_die_ursache_loescht_sie_aber_nicht() -> None:
    """Der KeyError verraet nur die interne Mechanik der Registry.

    Er wird deshalb nicht als Ursache ausgewiesen — bleibt aber im Objekt
    erhalten und ist nur im Traceback unsichtbar.
    """
    with pytest.raises(UnbekannteKomponenteError) as info:
        InfoLieferant.erzeugt("quatsch")
    assert info.value.__cause__ is None
    assert isinstance(info.value.__context__, KeyError)


def test_fehlende_datei_reicht_den_oserror_weiter() -> None:
    """Hier ist die untere Exception wertvoll: fehlt die Datei, oder fehlen
    nur die Rechte? Das kann der eigene Fehler nicht wissen."""
    with pytest.raises(CsvFormatError) as info:
        KundenCsv.aus_datei("gibt-es-nicht.csv")
    assert isinstance(info.value.__cause__, FileNotFoundError)


# --- Fehlerprotokoll (Contextmanager) --------------------------------------

def test_protokoll_zeichnet_auf_und_wirft_weiter() -> None:
    protokoll = Fehlerprotokoll("Import")
    with pytest.raises(UngueltigerNameError):
        with protokoll:
            Kunde("", "leer@example.de")
    assert len(protokoll.meldungen) == 1
    assert "UngueltigerNameError" in protokoll.meldungen[0]
    assert "Import" in protokoll.meldungen[0]


def test_protokoll_bleibt_ohne_fehler_leer() -> None:
    """__exit__ laeuft auch im Erfolgsfall — es passiert nur nichts."""
    protokoll = Fehlerprotokoll("Import")
    with protokoll:
        Kunde("Anna", "anna@example.de")
    assert protokoll.meldungen == []


def test_truthy_rueckgabe_schluckt_die_exception() -> None:
    """Kein pytest.raises noetig — der Fehler kommt gar nicht erst an."""
    protokoll = Fehlerprotokoll("Import", schlucken=True)
    with protokoll:
        Kunde("", "leer@example.de")
    assert len(protokoll.meldungen) == 1, "aufgezeichnet wird trotzdem"


def test_protokollieren_und_weiterreichen_sind_getrennt() -> None:
    """Beide Varianten zeichnen dasselbe auf; nur der Rueckgabewert von
    __exit__ unterscheidet sie."""
    durchlassend = Fehlerprotokoll("Import")
    schluckend = Fehlerprotokoll("Import", schlucken=True)

    with pytest.raises(UngueltigerNameError):
        with durchlassend:
            Kunde("", "leer@example.de")
    with schluckend:
        Kunde("", "leer@example.de")

    assert durchlassend.meldungen == schluckend.meldungen
