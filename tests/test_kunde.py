"""Kunde: Properties, Delegation an Komponenten, Darstellung, Vergleich, CSV."""

from pathlib import Path

import pytest

from kundenverwaltung import (
    CsvFormatError,
    GeschaeftsDaten,
    Kunde,
    KundenCsv,
    Kundenliste,
    KundenverwaltungError,
    email_gueltig,
    PrivatDaten,
    UngueltigeEmailError,
)


# --- Grundlagen ------------------------------------------------------------

def test_kundennummern_sind_eindeutig() -> None:
    assert Kunde("A", "a@example.de").nummer != Kunde("B", "b@example.de").nummer


def test_umsatz_startet_bei_null(kunde: Kunde) -> None:
    assert kunde.umsatz == 0.0


def test_tags_werden_nicht_zwischen_instanzen_geteilt() -> None:
    """Die Mutable-Default-Falle: ein `tags=[]` in der Signatur waere EIN
    Objekt fuer alle Instanzen."""
    erster = Kunde("A", "a@example.de")
    zweiter = Kunde("B", "b@example.de")
    erster.tags.append("Premium")
    assert zweiter.tags == []


@pytest.mark.parametrize(
    "email",
    ["ohne-at", "@example.de", "zwei@@example.de", "anna@ohnepunkt", "anna@example.d"],
)
def test_ungueltige_emails_werden_abgelehnt(email: str) -> None:
    with pytest.raises(UngueltigeEmailError):
        Kunde("Anna", email)


# --- Delegation an die Komponenten ----------------------------------------

def test_kunde_ohne_komponente_nutzt_die_basisgrenze(kunde: Kunde) -> None:
    kunde.umsatz = 15_000
    assert kunde.is_grosskunde(), "15.000 liegt ueber der Basisgrenze von 10.000"


def test_geschaeftskunde_nutzt_die_hoehere_grenze(geschaeftskunde: Kunde) -> None:
    """Der urspruengliche Fragile-Base-Class-Bug: status() verglich frueher
    immer gegen die Basisgrenze, auch bei Geschaeftskunden."""
    geschaeftskunde.umsatz = 12_000
    assert not geschaeftskunde.is_grosskunde(), (
        "12.000 liegt zwar ueber der Basisgrenze, aber unter der Geschaeftsgrenze"
    )
    geschaeftskunde.umsatz = 150_000
    assert geschaeftskunde.is_grosskunde()


def test_grosskundengrenze_hat_vorrang(grosskunde: Kunde) -> None:
    grosskunde.umsatz = 200_000
    assert not grosskunde.is_grosskunde(), (
        "die Grosskundengrenze von 500.000 sticht die Geschaeftsgrenze von 100.000"
    )
    grosskunde.umsatz = 600_000
    assert grosskunde.is_grosskunde()


def test_inaktive_kunden_sind_inaktiv_unabhaengig_vom_umsatz(kunde: Kunde) -> None:
    kunde.umsatz = 20_000
    kunde.deaktivieren()
    assert kunde.status() == "inaktiv"


def test_info_haengt_alle_komponenten_an(grosskunde: Kunde) -> None:
    """Nicht nur die erste zutreffende — alle."""
    ausgabe = grosskunde.info()
    assert "MegaCorp AG" in ausgabe and "Frau Mueller" in ausgabe


def test_info_ueberlebt_eine_kaputte_komponente(kunde: Kunde) -> None:
    """Eine Komponente, deren info() abstuerzt, darf die uebrigen nicht
    mitreissen — sie wird als Fehlermeldung eingebettet."""

    class Kaputt:
        def info(self) -> str:
            raise RuntimeError("DB nicht erreichbar")

    kunde.komponente_hinzufuegen(Kaputt())
    kunde.komponente_hinzufuegen(PrivatDaten(1990))
    ausgabe = kunde.info()
    assert "fehlgeschlagen" in ausgabe
    assert "1990" in ausgabe, "die intakte Komponente kommt trotzdem durch"


# --- Darstellung -----------------------------------------------------------

def test_str_ist_einzeilig_und_menschenlesbar(kunde: Kunde) -> None:
    assert "\n" not in str(kunde)
    assert kunde.name in str(kunde)


def test_repr_sieht_aus_wie_ein_konstruktoraufruf(kunde: Kunde) -> None:
    assert repr(kunde).startswith("Kunde(")
    assert "'Anna Beispiel'" in repr(kunde), "repr setzt Werte in Anfuehrungszeichen"


def test_str_und_repr_haben_getrennte_rollen(kunde: Kunde) -> None:
    assert str(kunde) != repr(kunde)


def test_container_zeigen_das_repr_der_elemente(kunde: Kunde) -> None:
    """print(k) nimmt __str__, print([k]) das __repr__ der Elemente."""
    assert repr(kunde) in str([kunde])
    assert repr(kunde) in str({"a": kunde})


# --- Gleichheit und Hashing ------------------------------------------------

def test_gleichheit_haengt_an_der_kundennummer(kunde: Kunde) -> None:
    zwilling = Kunde("Ganz anderer Name", "anders@example.de")
    zwilling._nummer = kunde.nummer
    assert zwilling == kunde
    assert zwilling is not kunde


def test_gleiche_daten_aber_andere_nummer_sind_ungleich() -> None:
    """Der Gegenfall: ohne ihn wuerde der Test auch bestehen, wenn __eq__
    immer True zurueckgaebe."""
    assert Kunde("A", "a@example.de") != Kunde("A", "a@example.de")


def test_gleiche_kunden_liegen_im_set_nur_einmal(kunde: Kunde) -> None:
    zwilling = Kunde("Anders", "anders@example.de")
    zwilling._nummer = kunde.nummer
    assert len({kunde, zwilling}) == 1
    assert hash(kunde) == hash(zwilling), "gleich impliziert gleicher Hash"


def test_vergleich_mit_fremdtyp_liefert_false_statt_abzustuerzen(kunde: Kunde) -> None:
    """Gleichheit ueber Typgrenzen hat eine sinnvolle Antwort: nicht gleich."""
    assert (kunde == "ein String") is False
    assert ("ein String" == kunde) is False
    assert (kunde != "ein String") is True


# --- Ordnung ---------------------------------------------------------------

def test_sortiert_ohne_key_nach_umsatz(kundenliste: Kundenliste) -> None:
    assert [k.umsatz for k in sorted(kundenliste)] == [50, 10_000, 100_000]


def test_gleicher_umsatz_wird_ueber_die_nummer_entschieden() -> None:
    """Ohne diesen Tie-Break waeren bei gleichem Umsatz beide Kunden
    gleichzeitig groesser als der andere — total_ordering baut `a > b` als
    `(not a < b) and (a != b)`."""
    frueher = Kunde("Frueher", "f@example.de")
    spaeter = Kunde("Spaeter", "s@example.de")
    frueher.umsatz = spaeter.umsatz = 5_000

    beziehungen = [frueher < spaeter, frueher > spaeter, frueher == spaeter]
    assert sum(beziehungen) == 1, "genau eine der drei Beziehungen muss gelten"
    assert frueher < spaeter, "bei Gleichstand entscheidet die kleinere Nummer"


@pytest.mark.parametrize("operator", ["<", ">", "<=", ">="])
def test_ordnungsvergleich_mit_fremdtyp_wirft(kunde: Kunde, operator: str) -> None:
    """Anders als bei ==: eine Reihenfolge zwischen Kunde und str hat keine
    sinnvolle Antwort, also ist der Absturz richtig. Python macht es bei
    seinen eigenen Typen genauso (1 == "a" ist False, 1 < "a" wirft)."""
    with pytest.raises(TypeError):
        eval(f"kunde {operator} 'ein String'")  # noqa: S307


# --- CSV -------------------------------------------------------------------

def test_aus_csv_zeile_liest_eine_gueltige_zeile() -> None:
    gelesen = KundenCsv.aus_zeile("Anna;anna@example.de;5000")
    assert gelesen.name == "Anna"
    assert gelesen.umsatz == 5000.0


def test_kunden_aus_datei_ueberspringt_kaputte_zeilen(beispiel_csv: Path) -> None:
    """Eine kaputte Zeile darf nicht die ganze Datei scheitern lassen."""
    eingelesen = KundenCsv.aus_datei(str(beispiel_csv))
    assert [k.name for k in eingelesen] == ["Anna", "Bob", "Dora"]


def test_kunden_aus_datei_laesst_sich_wiederholen(beispiel_csv: Path) -> None:
    """Beleg dafuer, dass die Datei sauber geschlossen wird."""
    erster = KundenCsv.aus_datei(str(beispiel_csv))
    zweiter = KundenCsv.aus_datei(str(beispiel_csv))
    assert len(erster) == len(zweiter) == 3


# --- Haertung --------------------------------------------------------------

@pytest.mark.parametrize(
    ("beschreibung", "zeile"),
    [
        ("leere Zeile", ""),
        ("nur Trennzeichen", ";;"),
        ("kaputte Email", "A;kaputt;100"),
        ("negativer Umsatz", "A;a@example.de;-5"),
    ],
)
def test_muelleingaben_liefern_immer_einen_fachfehler(
    beschreibung: str, zeile: str
) -> None:
    """Ein nackter KeyError oder IndexError waere ein Leck: dann schluege
    eine interne Mechanik nach aussen durch, statt uebersetzt zu werden."""
    with pytest.raises(KundenverwaltungError):
        KundenCsv.aus_zeile(zeile)


def test_gueltige_eingaben_gehen_weiterhin_durch() -> None:
    """Gegenprobe zur Haertung: ohne sie wuerde der Test oben auch bestehen,
    wenn die Klasse jede Eingabe ablehnte."""
    assert KundenCsv.aus_zeile("Gut;gut@example.de;1500").umsatz == 1500


# --- Zwischenspeicherung ---------------------------------------------------

def test_risiko_score_wird_nach_dem_ersten_zugriff_zwischengespeichert(
    kunde: Kunde,
) -> None:
    """cached_property legt den Wert in __dict__ ab.

    Ueber den Mechanismus geprueft statt ueber die Laufzeit — das ist
    schneller und aussagekraeftiger als eine Stoppuhr.
    """
    assert "risiko_score" not in kunde.__dict__, "vor dem ersten Zugriff leer"
    wert = kunde.risiko_score
    assert kunde.__dict__["risiko_score"] == wert, "danach im Instanz-Dict"
    assert kunde.risiko_score is wert, "zweiter Zugriff liefert dasselbe Objekt"


def test_gecachter_score_altert(kunde: Kunde) -> None:
    """Der Preis der Zwischenspeicherung: eine spaetere Umsatzaenderung
    wirkt sich nicht mehr aus."""
    kunde.umsatz = 50
    erster = kunde.risiko_score
    kunde.umsatz = 500_000
    assert kunde.risiko_score == erster


# --- CSV-Export ------------------------------------------------------------

def test_als_zeile_schreibt_das_gelesene_format(kunde: Kunde) -> None:
    """Lesen und Schreiben sind Umkehrungen voneinander — beide kennen
    dasselbe Trennzeichen, weil beide in derselben Klasse stehen."""
    kunde.umsatz = 1500
    zeile = KundenCsv.als_zeile(kunde)
    assert zeile == f"{kunde.name};{kunde.email};1500.0"
    assert KundenCsv.aus_zeile(zeile).umsatz == 1500.0


# --- Email-Pruefung als eigenstaendige Funktion ----------------------------

@pytest.mark.parametrize(
    "email",
    ["anna@example.de", "a@b.co", "vor.nach@firma.example.com"],
)
def test_gueltige_adressen(email: str) -> None:
    assert email_gueltig(email) is True


@pytest.mark.parametrize(
    ("email", "grund"),
    [
        ("ohne-at", "kein @"),
        ("@example.de", "kein lokaler Teil"),
        ("zwei@@example.de", "zwei @"),
        ("anna@ohnepunkt", "kein Punkt in der Domain"),
        ("anna@example.d", "Top-Level-Domain zu kurz"),
    ],
)
def test_ungueltige_adressen(email: str, grund: str) -> None:
    assert email_gueltig(email) is False, f"haette an '{grund}' scheitern muessen"


def test_pruefung_braucht_keinen_kunden() -> None:
    """Der Grund fuer die Herausloesung: Die Funktion arbeitet auf einem
    String, nicht auf einem Objekt. Man kann pruefen, BEVOR man baut."""
    if email_gueltig("neu@example.de"):
        Kunde("Neu", "neu@example.de")
