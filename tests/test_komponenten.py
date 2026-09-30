"""ABC-Vertrag, Protocol, Registry/Factory und die Darstellung der Komponenten."""

import pytest

from kundenverwaltung import (
    Adresse,
    GeschaeftsDaten,
    GrosskundenDaten,
    InfoFaehig,
    InfoLieferant,
    Kunde,
    Notiz,
    PrivatDaten,
    UnbekannteKomponenteError,
)

KOMPONENTEN = [
    PrivatDaten(1980),
    GeschaeftsDaten("AnnaFirma", "DE123456789"),
    GrosskundenDaten("Herr Mueller"),
    Adresse("Hauptstrasse", "42", "10115", "Berlin"),
    Notiz("Rueckruf vereinbart"),
]


# --- Der ABC-Vertrag -------------------------------------------------------

def test_infolieferant_ist_nicht_instanziierbar() -> None:
    """Ein ABC mit abstrakten Methoden laesst sich nicht direkt bauen."""
    with pytest.raises(TypeError, match="abstract"):
        InfoLieferant()  # type: ignore[abstract]


def test_unvollstaendige_subklasse_ist_nicht_instanziierbar() -> None:
    """Wer nur info() implementiert und label() vergisst, faellt beim
    Instanziieren auf — nicht erst beim Aufruf der fehlenden Methode."""

    class Unvollstaendig(InfoLieferant):
        def info(self) -> str:
            return "nur die Haelfte"

    with pytest.raises(TypeError, match="label"):
        Unvollstaendig()  # type: ignore[abstract]


# --- Das Protocol (strukturell statt nominal) -----------------------------

@pytest.mark.parametrize(
    "komponente",
    [PrivatDaten(1990), GeschaeftsDaten("X", "DE1"), Notiz("Text")],
    ids=["PrivatDaten", "GeschaeftsDaten", "Notiz"],
)
def test_alles_mit_info_erfuellt_das_protocol(komponente: object) -> None:
    """Notiz erbt von nichts und erfuellt InfoFaehig trotzdem — genau das
    ist der Unterschied zwischen strukturell und nominal."""
    assert isinstance(komponente, InfoFaehig)


def test_protocol_prueft_nur_die_anwesenheit_der_methode() -> None:
    """isinstance gegen ein Protocol schaut nicht auf die Signatur.

    Wer info() mit falschen Parametern hat, gilt trotzdem als InfoFaehig —
    die Pruefung ist zur Laufzeit bewusst grob.
    """

    class FalscheSignatur:
        def info(self, ueberfluessig: int) -> str:
            return "..."

    assert isinstance(FalscheSignatur(), InfoFaehig)


# --- Registry und Factory --------------------------------------------------

def test_registry_kennt_alle_drei_schluessel() -> None:
    assert set(InfoLieferant.registry) == {"privat", "geschaeft", "gross"}


@pytest.mark.parametrize(
    ("schluessel", "klasse", "argument"),
    [
        ("privat", PrivatDaten, 1999),
        ("geschaeft", GeschaeftsDaten, "Firma"),
        ("gross", GrosskundenDaten, "Frau Meier"),
    ],
)
def test_factory_erzeugt_die_richtige_klasse(
    schluessel: str, klasse: type, argument: object
) -> None:
    if schluessel == "geschaeft":
        erzeugt = InfoLieferant.erzeugt(schluessel, argument, "DE1")
    else:
        erzeugt = InfoLieferant.erzeugt(schluessel, argument)
    assert isinstance(erzeugt, klasse)


def test_factory_meldet_unbekannten_schluessel_mit_alternativen() -> None:
    with pytest.raises(UnbekannteKomponenteError) as info:
        InfoLieferant.erzeugt("gibts-nicht")
    meldung = str(info.value)
    assert "gibts-nicht" in meldung
    assert "geschaeft" in meldung, "die gueltigen Schluessel gehoeren in die Meldung"


def test_erzeugte_komponente_laesst_sich_einhaengen(kunde: Kunde) -> None:
    kunde.komponente_hinzufuegen(InfoLieferant.erzeugt("privat", 1999))
    assert "1999" in kunde.info()


# --- Darstellung -----------------------------------------------------------

@pytest.mark.parametrize(
    "komponente", KOMPONENTEN, ids=lambda k: type(k).__name__
)
def test_repr_ist_eval_faehig(komponente: object) -> None:
    """Die eval-Rundreise belegt zweierlei auf einmal: die Form stimmt, und
    alle Werte sind enthalten."""
    darstellung = repr(komponente)
    assert darstellung.startswith(f"{type(komponente).__name__}(")
    assert "object at 0x" not in darstellung
    assert repr(eval(darstellung)) == darstellung  # noqa: S307


def test_adresse_hat_getrennte_str_und_repr() -> None:
    adresse = Adresse("Hauptstrasse", "42", "10115", "Berlin")
    assert str(adresse) == "Hauptstrasse 42, 10115 Berlin"
    assert repr(adresse) != str(adresse)


def test_kunde_repr_traegt_die_repr_seiner_komponenten(
    vollstaendiger_kunde: Kunde,
) -> None:
    """Ein repr ist nur so gut wie die repr seiner Bestandteile."""
    darstellung = repr(vollstaendiger_kunde)
    assert "object at 0x" not in darstellung
    for teil in ("VollCorp", "1975", "Frau Schmidt", "Ringstrasse"):
        assert teil in darstellung


# --- Luecken aus dem Abgleich mit test_kunde.py (Woche 12) ------------------

@pytest.mark.parametrize(
    "komponente, erwartet",
    [
        (PrivatDaten(1980), "Typ: Privatkunde"),
        (GeschaeftsDaten("Firma", "DE1"), "Typ: Geschäftskunde"),
        (GrosskundenDaten("Frau Meier"), "Typ: Grosskunde"),
    ],
)
def test_jede_komponente_nennt_ihren_typ(komponente: InfoLieferant, erwartet: str) -> None:
    """label() gehoert zum ABC-Vertrag und wurde von keinem Test aufgerufen."""
    assert komponente.label() == erwartet


def test_grosskundendaten_ueberstehen_den_round_trip() -> None:
    original = GrosskundenDaten("Frau Meier")
    zurueck = InfoLieferant.aus_dict(original.als_dict())
    assert zurueck == original
    assert isinstance(zurueck, GrosskundenDaten) and zurueck.betreuer == "Frau Meier"


def test_grosskundendaten_vergleichen_sich_ueber_den_betreuer() -> None:
    assert GrosskundenDaten("A") == GrosskundenDaten("A")
    assert GrosskundenDaten("A") != GrosskundenDaten("B")
    assert GrosskundenDaten("A") != "kein GrosskundenDaten"


def test_komponente_ohne_typmarker_wird_abgewiesen() -> None:
    with pytest.raises(UnbekannteKomponenteError, match="ohne Typmarker"):
        InfoLieferant.aus_dict({"geburtsjahr": 1980})


def test_unbekannter_typmarker_nennt_die_bekannten() -> None:
    with pytest.raises(UnbekannteKomponenteError) as fehler:
        InfoLieferant.aus_dict({"typ": "gibtsnicht"})
    assert "privat" in str(fehler.value) and "geschaeft" in str(fehler.value)
