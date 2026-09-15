"""Persistenz: JSON-Format, Dateifehler, atomares Schreiben, KundenDatei."""

import json
import os
from pathlib import Path
from typing import Any

import pytest

from kundenverwaltung import (
    Adresse,
    DateiInhaltError,
    DateiNichtGefundenError,
    DateiNichtLesbarError,
    GeschaeftsDaten,
    InfoLieferant,
    Kunde,
    KundenDatei,
    Kundenliste,
    KundenverwaltungError,
    KundenZustand,
    Notiz,
    NotizSpeicher,
    PrivatDaten,
    json_atomar_schreiben,
    kunden_datei,
)

# Rechte-Tests brauchen Unix-Rechte und duerfen nicht als root laufen —
# root liest auch Dateien mit chmod 000.
OHNE_RECHTEPRUEFUNG = os.name != "posix" or os.geteuid() == 0


def _kunde_mit_allem() -> Kunde:
    kunde = Kunde(
        "Jörg Straßburger", "joerg@example.de",
        geschaefts_daten=GeschaeftsDaten("Müller & Söhne GmbH", "DE811234567"),
        private_daten=PrivatDaten(1978),
        adresse=Adresse("Königsallee", "12a", "40212", "Düsseldorf"),
        tags=["vip"],
    )
    kunde.umsatz = 148_500.75
    kunde.sperren()
    return kunde


# --- Round-Trip ------------------------------------------------------------

def test_round_trip_haelt_alle_felder(tmp_path: Path) -> None:
    """Feldweise statt mit ==: Kunde.__eq__ vergleicht nur die Nummer und
    waere auch bei verlorenen Daten gruen (siehe naechster Test)."""
    original = _kunde_mit_allem()
    pfad = tmp_path / "kunden.json"
    Kundenliste([original]).speichern(str(pfad))
    geladen = Kundenliste.laden(str(pfad))[0]

    assert geladen.name == original.name
    assert geladen.email == original.email
    assert geladen.umsatz == original.umsatz
    assert geladen.nummer == original.nummer
    assert geladen.zustand is KundenZustand.GESPERRT
    assert geladen.tags == ["vip"]
    assert geladen.adresse == original.adresse
    assert geladen.geschaefts_daten == original.geschaefts_daten
    assert geladen.private_daten == original.private_daten


def test_eq_allein_waere_als_round_trip_test_wertlos() -> None:
    """Die Falle als Test: gleiche Nummer, drei verfaelschte Felder — und
    == ist trotzdem True."""
    original = Kunde("Anna", "anna@example.de")
    daten = original.als_dict()
    daten.update(name="Ganz anders", email="anders@example.de", umsatz=999.0)
    assert Kunde.aus_dict(daten) == original


def test_datei_steht_im_format_version_2(tmp_path: Path) -> None:
    pfad = tmp_path / "kunden.json"
    Kundenliste([_kunde_mit_allem()]).speichern(str(pfad))
    roh = json.loads(pfad.read_text(encoding="utf-8"))

    assert roh["version"] == 2
    eintrag = roh["kunden"][0]
    assert eintrag["zustand"] == "gesperrt", "die Enum steht als ihr Wert in der Datei"
    assert "aktiv" not in eintrag
    assert {k["typ"] for k in eintrag["komponenten"]} == {"geschaeft", "privat"}
    assert "Straßburger" in pfad.read_text(encoding="utf-8"), "Umlaute bleiben lesbar"


def test_version_1_bleibt_lesbar_und_wird_beim_speichern_zu_version_2(
    tmp_path: Path,
) -> None:
    """Migration: alte Dateien weiter lesen, nur noch das neue Format schreiben."""
    pfad = tmp_path / "alt.json"
    pfad.write_text(json.dumps({"version": 1, "kunden": [
        {"name": "A", "email": "a@example.de", "nummer": 8101, "aktiv": True},
        {"name": "B", "email": "b@example.de", "nummer": 8102, "aktiv": False},
    ]}), encoding="utf-8")

    liste = Kundenliste.laden(str(pfad))
    assert [k.zustand for k in liste] == [KundenZustand.AKTIV, KundenZustand.INAKTIV]

    liste.speichern(str(pfad))
    assert json.loads(pfad.read_text(encoding="utf-8"))["version"] == 2


def test_nummer_ueberlebt_und_neue_nummern_kollidieren_nicht() -> None:
    geladen = Kunde.aus_dict({"name": "Alt", "email": "alt@example.de", "nummer": 950_000})
    neu = Kunde("Neu", "neu@example.de")
    assert geladen.nummer == 950_000
    assert neu.nummer > 950_000, "der Zaehler wird ueber geladene Nummern gezogen"


# --- kaputte Dateien -------------------------------------------------------

def test_fehlende_datei(tmp_path: Path) -> None:
    with pytest.raises(DateiNichtGefundenError) as info:
        Kundenliste.laden(str(tmp_path / "gibts-nicht.json"))
    assert isinstance(info.value.__cause__, FileNotFoundError)


def test_verzeichnis_statt_datei(tmp_path: Path) -> None:
    with pytest.raises(DateiNichtLesbarError):
        Kundenliste.laden(str(tmp_path))


@pytest.mark.parametrize(
    ("beschreibung", "inhalt"),
    [
        ("abgeschnittenes JSON", '{"version": 2, "kunden": ['),
        ("Liste statt Objekt", "[]"),
        ("Version fehlt", '{"kunden": []}'),
        ("Version aus der Zukunft", '{"version": 99, "kunden": []}'),
        ("Version als Liste", '{"version": [1], "kunden": []}'),
        ("Pflichtfeld fehlt", '{"version": 2, "kunden": [{"email": "a@example.de"}]}'),
        (
            "unbekannter Zustand",
            '{"version": 2, "kunden": [{"name": "A", "email": "a@example.de",'
            ' "nummer": 1, "zustand": "geloescht"}]}',
        ),
    ],
)
def test_unbrauchbarer_inhalt_ist_ein_dateiinhaltfehler(
    tmp_path: Path, beschreibung: str, inhalt: str
) -> None:
    """Gueltiges JSON ist noch keine gueltige Datei. Nie ein nackter KeyError,
    TypeError oder AttributeError."""
    pfad = tmp_path / "kaputt.json"
    pfad.write_text(inhalt, encoding="utf-8")
    with pytest.raises(DateiInhaltError):
        Kundenliste.laden(str(pfad))


@pytest.mark.skipif(OHNE_RECHTEPRUEFUNG, reason="braucht Unix-Rechte und kein root")
def test_unlesbare_datei(tmp_path: Path) -> None:
    pfad = tmp_path / "gesperrt.json"
    Kundenliste().speichern(str(pfad))
    pfad.chmod(0o000)
    try:
        with pytest.raises(DateiNichtLesbarError):
            Kundenliste.laden(str(pfad))
    finally:
        pfad.chmod(0o644)


@pytest.mark.skipif(OHNE_RECHTEPRUEFUNG, reason="braucht Unix-Rechte und kein root")
def test_gesperrtes_verzeichnis_laesst_nichts_zurueck(tmp_path: Path) -> None:
    """Ein Fehlerfall ist erst geprueft, wenn auch geprueft ist, was er hinterlaesst."""
    ordner = tmp_path / "nur_lesen"
    ordner.mkdir()
    pfad = ordner / "kunden.json"
    Kundenliste([Kunde("Vorher", "vorher@example.de")]).speichern(str(pfad))
    ordner.chmod(0o555)
    try:
        with pytest.raises(DateiNichtLesbarError):
            Kundenliste([Kunde("Nachher", "nachher@example.de")]).speichern(str(pfad))
        assert [p.name for p in ordner.iterdir()] == ["kunden.json"], "keine temporaere Datei"
        assert Kundenliste.laden(str(pfad))[0].name == "Vorher", "alter Stand unberuehrt"
    finally:
        ordner.chmod(0o755)


# --- atomares Schreiben ----------------------------------------------------

def test_abbruch_mitten_im_schreiben_laesst_den_alten_stand_stehen(
    tmp_path: Path,
) -> None:
    """Ein Serialisierungsfehler reicht fuer einen Abbruch mitten im Schreiben.
    Weil in eine temporaere Datei geschrieben und erst danach umbenannt wird,
    bleibt die alte Datei vollstaendig erhalten."""
    pfad = tmp_path / "wichtig.json"
    json_atomar_schreiben(str(pfad), {"version": 2, "kunden": []})

    with pytest.raises(TypeError):
        json_atomar_schreiben(str(pfad), {"kunden": [{"a": 1}, {"b": object()}]})

    assert json.loads(pfad.read_text(encoding="utf-8")) == {"version": 2, "kunden": []}
    assert [p.name for p in tmp_path.iterdir()] == ["wichtig.json"], "keine Reste"


@pytest.mark.skipif(os.name != "posix", reason="braucht Unix-Rechte")
def test_zugriffsrechte_bleiben_erhalten(tmp_path: Path) -> None:
    """Eine temporaere Datei hat 0600 — ohne Uebernahme der alten Rechte waere
    die Datei nach dem ersten Speichern nur noch fuer den Eigentuemer lesbar."""
    pfad = tmp_path / "kunden.json"
    json_atomar_schreiben(str(pfad), {"version": 2, "kunden": []})
    pfad.chmod(0o644)
    json_atomar_schreiben(str(pfad), {"version": 2, "kunden": []})
    assert pfad.stat().st_mode & 0o777 == 0o644


# --- KundenDatei -----------------------------------------------------------

def test_erster_start_ohne_datei_liefert_eine_leere_liste(tmp_path: Path) -> None:
    pfad = tmp_path / "kunden.json"
    with KundenDatei(str(pfad)) as kunden:
        assert len(kunden) == 0
        kunden.hinzufuegen(Kunde("Erster", "erster@example.de"))
    assert len(Kundenliste.laden(str(pfad))) == 1


def test_fehler_im_block_speichert_nichts(tmp_path: Path) -> None:
    """Transaktional: Eine Datei enthaelt immer einen vollstaendig erreichten Zustand."""
    pfad = tmp_path / "kunden.json"
    with KundenDatei(str(pfad)) as kunden:
        kunden.hinzufuegen(Kunde("Bleibt", "bleibt@example.de"))

    with pytest.raises(ValueError):
        with KundenDatei(str(pfad)) as kunden:
            kunden.hinzufuegen(Kunde("Verworfen", "weg@example.de"))
            raise ValueError("Fehler im Block")

    assert [k.name for k in Kundenliste.laden(str(pfad))] == ["Bleibt"]


def test_kaputte_datei_wird_nicht_durch_eine_leere_ersetzt(tmp_path: Path) -> None:
    pfad = tmp_path / "kunden.json"
    pfad.write_text("{kaputt", encoding="utf-8")
    with pytest.raises(DateiInhaltError):
        with KundenDatei(str(pfad)):
            pass
    assert pfad.read_text(encoding="utf-8") == "{kaputt"


def test_notizen_liegen_in_einer_eigenen_datei(tmp_path: Path) -> None:
    pfad = tmp_path / "kunden.json"
    with KundenDatei(str(pfad)) as kunden:
        kunde = Kunde("Mit Notiz", "notiz@example.de")
        kunde.komponente_hinzufuegen(Notiz("Rueckruf nach 16 Uhr"))
        kunden.hinzufuegen(kunde)

    assert "Rueckruf" not in pfad.read_text(encoding="utf-8")
    assert "Rueckruf" in (tmp_path / "kunden.notizen.json").read_text(encoding="utf-8")
    with KundenDatei(str(pfad)) as kunden:
        assert "Rueckruf nach 16 Uhr" in kunden[0].info()


def test_waisen_werden_gemeldet_und_aufbewahrt(tmp_path: Path) -> None:
    """Regressionstest: Frueher loeschte ein with-Block, der gar nichts tat,
    die Notizen zu Kunden, die es nicht mehr gibt. Gemeldet ist nicht
    aufbewahrt."""
    pfad = tmp_path / "kunden.json"
    notizen = tmp_path / "kunden.notizen.json"
    Kundenliste().speichern(str(pfad))
    NotizSpeicher({987_654: [Notiz("Kunde ist weg")]}).speichern(str(notizen))

    datei = KundenDatei(str(pfad))
    with datei:
        pass

    assert datei.waisen == [987_654]
    assert NotizSpeicher.laden(str(notizen)).fuer(987_654) == [Notiz("Kunde ist weg")]
    assert Kunde("Neu", "neu@example.de").nummer > 987_654, "eine Nummer mit Notizen ist nicht frei"


def test_zweites_betreten_desselben_objekts_wird_abgewiesen(tmp_path: Path) -> None:
    datei = KundenDatei(str(tmp_path / "kunden.json"))
    with datei:
        with pytest.raises(KundenverwaltungError):
            with datei:
                pass


# --- dieselbe Klammer als Generator ----------------------------------------

def test_generator_variante_ist_ebenfalls_transaktional(tmp_path: Path) -> None:
    """Ohne try um das yield wird die Zeile danach bei einem Fehler nie
    erreicht — transaktional ohne ein einziges if."""
    pfad = tmp_path / "kunden.json"
    with kunden_datei(str(pfad)) as kunden:
        kunden.hinzufuegen(Kunde("Bleibt", "bleibt@example.de"))

    with pytest.raises(ValueError):
        with kunden_datei(str(pfad)) as kunden:
            kunden.hinzufuegen(Kunde("Verworfen", "weg@example.de"))
            raise ValueError("Fehler im Block")

    assert [k.name for k in Kundenliste.laden(str(pfad))] == ["Bleibt"]


# --- Open-Closed: eine neue Komponentenklasse ohne Aenderung an Kunde ------

def test_neue_komponentenklasse_uebersteht_speichern_ohne_aenderung_an_kunde(
    tmp_path: Path,
) -> None:
    """Komponenten stehen als getaggte Liste in der Datei. Diese Klasse entsteht
    erst hier im Test — in Kunde, Kundenliste oder der Speicherschicht steht
    keine Zeile fuer sie, und sie uebersteht Speichern und Laden trotzdem."""

    class VertragsDaten(InfoLieferant, key="vertrag"):
        def __init__(self, laufzeit_monate: int) -> None:
            self.laufzeit_monate = laufzeit_monate

        def info(self) -> str:
            return f"Vertrag: {self.laufzeit_monate} Monate"

        def label(self) -> str:
            return "Typ: Vertragskunde"

        def felder(self) -> dict[str, Any]:
            return {"laufzeit_monate": self.laufzeit_monate}

        @classmethod
        def aus_felder(cls, daten: dict[str, Any]) -> "VertragsDaten":
            return cls(daten["laufzeit_monate"])

    try:
        kunde = Kunde("Vertrag", "vertrag@example.de")
        kunde.komponente_hinzufuegen(VertragsDaten(24))
        pfad = tmp_path / "kunden.json"
        Kundenliste([kunde]).speichern(str(pfad))
        assert "Vertrag: 24 Monate" in Kundenliste.laden(str(pfad))[0].info()
    finally:
        # Die Registry ist global. Ohne Aufraeumen saehe ein spaeterer Test
        # einen Schluessel, den es im Paket gar nicht gibt.
        InfoLieferant.registry.pop("vertrag", None)
