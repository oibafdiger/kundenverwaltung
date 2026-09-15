"""Uebersetzung zwischen Kunde und CSV.

Herausgeloest aus Kunde (SRP): Ein neues Trennzeichen oder eine
zusaetzliche Spalte ist ein anderer Aenderungsgrund als die Frage,
was ein Kunde ist."""

from .exceptions import CsvFormatError, KundenverwaltungError
from .kunde import Kunde


# ============================================================================
# CSV-Format (Woche 8, Kuer: SRP)
# Aufgabe: Kunden aus CSV lesen und nach CSV schreiben
# ============================================================================
class KundenCsv:
    """Uebersetzt zwischen Kunde und CSV — in beide Richtungen.

    Herausgeloest aus Kunde (Kuer Woche 8). Der Aenderungsgrund ist ein
    anderer: Ein neues Trennzeichen, eine zusaetzliche Spalte oder ein Wechsel
    zu JSON hat nichts damit zu tun, was ein Kunde IST. Kunde behaelt seine
    eigentliche Verantwortung — Zustand und Grosskunden-Logik.

    Mit dem Schreiben ist auch ExportierbarMixin entfallen: Es enthielt nur
    als_csv() und die drei Vertragsdeklarationen, die allein dieser Methode
    dienten. Damit hat Kunde keine Basisklasse mehr, und im Projekt gibt es
    keine Mehrfachvererbung.

    Alle Methoden sind statisch: Keine braucht Zustand, und die Klasse wird
    nie instanziiert. Sie ist ein benannter Ort fuer zusammengehoerige
    Funktionen, kein Objekt.
    """

    TRENNZEICHEN = ";"

    @staticmethod
    def als_zeile(kunde: "Kunde") -> str:
        """Schreibt einen Kunden als CSV-Zeile.

        Frueher Kunde.als_csv() im ExportierbarMixin. Liegt jetzt neben dem
        Lesen, weil beide Richtungen dasselbe Format kennen — aendert sich
        das Trennzeichen, steht es an einer Stelle.
        """
        return KundenCsv.TRENNZEICHEN.join(
            [kunde.name, kunde.email, str(kunde.umsatz)]
        )
    # ------------------------------------------------------------------
    # Klassenmethoden (Factory-Methoden)
    # ------------------------------------------------------------------
    @staticmethod
    def aus_zeile(zeile: str) -> "Kunde":
        """Factory-Method: erstellt Kunde aus CSV-Zeile (Name;email;umsatz)"""
        teile = zeile.split(KundenCsv.TRENNZEICHEN)
        if len(teile) != 3:
            raise CsvFormatError(
                f"CSV-Zeile muss 3 Felder haben, hat aber {len(teile)}: {zeile!r}"
            )

        name, email, umsatz_str = teile
        # `from e` statt nur `raise`: Der ValueError von float() sagt, WAS
        # nicht als Zahl lesbar war — das kann der eigene Fehler nicht wissen.
        # Ohne `from` haenge Python ihn zwar automatisch als __context__ an,
        # der Traceback meldete dann aber nur "During handling of the above
        # exception" statt "direct cause". Der Unterschied ist nicht
        # kosmetisch: __context__ heisst "passierte gleichzeitig",
        # __cause__ heisst "war der Grund".
        try:
            umsatz = float(umsatz_str)
        except ValueError as e:
            raise CsvFormatError(f"Umsatz muss eine Zahl sein: {umsatz_str!r}") from e

        kunde = Kunde(name, email)
        kunde.umsatz = umsatz
        return kunde

    @staticmethod
    def aus_datei(pfad: str) -> "list[Kunde]":
        """Liest eine CSV-Datei zeilenweise ein und ueberspringt kaputte Zeilen.

        Die einzige Stelle im Projekt, an der alle vier Bloecke einen echten
        Job haben — weil hier zum ersten Mal eine Ressource im Spiel ist:

            try     nur das Oeffnen. Was hier schiefgehen kann, ist genau
                    das, was das except behandelt.
            except  uebersetzt den OSError in einen Fachfehler. Ohne `from e`
                    ginge die Ursache verloren (Donnerstag).
            else    das Lesen. Gehoert NICHT in den try-Block: sonst wuerde
                    das except auch Fehler aus der Schleife als "Datei nicht
                    lesbar" melden. Dieselbe Ueberdehnung wie in info_eafp().
            finally laeuft immer — auch bei return oder raise. Ohne ihn
                    bliebe die Datei bei jedem Fehler offen.

        Falle, die beim Bauen zugeschlagen hat: `datei = None` davor ist
        noetig. finally laeuft IMMER — auch wenn open() fehlgeschlagen ist und
        `datei` nie zugewiesen wurde. Ohne die Vorbelegung wirft `datei.close()`
        dann einen UnboundLocalError, der den eigentlichen Fehler ueberdeckt.

        Genau diese Buchfuehrung nimmt `with` einem ab — die Kuer ersetzt das
        ganze try/finally durch eine Zeile.
        """
        datei = None
        try:
            datei = open(pfad, encoding="utf-8")
        except OSError as e:
            raise CsvFormatError(f"Datei nicht lesbar: {pfad!r}") from e
        else:
            kunden = []
            for nummer, zeile in enumerate(datei, start=1):
                zeile = zeile.strip()
                if not zeile:
                    continue
                # Kaputte Zeile heisst: diese Zeile ueberspringen, nicht die
                # ganze Datei aufgeben. Gefangen wird die Basisklasse, weil
                # aus_csv_zeile auch UngueltigeEmailError oder
                # UngueltigerNameError werfen kann — nicht nur CsvFormatError.
                try:
                    kunden.append(KundenCsv.aus_zeile(zeile))
                except KundenverwaltungError as e:
                    print(f"  Zeile {nummer} uebersprungen: {e}")
            return kunden
        finally:
            if datei is not None:
                datei.close()
