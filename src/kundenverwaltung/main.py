"""Kurzer Vorfuehrdurchlauf der Kundenverwaltung (Woche 11).

Starten mit:

    python -m kundenverwaltung.main     # dieses Modul direkt
    python -m kundenverwaltung          # dasselbe, ueber __main__.py

NICHT mit `python kundenverwaltung/main.py`: Dann ist die Datei ein loses
Skript ohne Paket drumherum, und die relativen Importe unten (`from .kunde`)
scheitern mit "attempted relative import with no known parent package".

Die `if __name__ == "__main__"`-Abfrage unten sorgt dafuer, dass die
Vorfuehrung nicht bei jedem `import` loslaeuft — etwa in einem Test, der nur
main() pruefen will.
"""

import tempfile
from pathlib import Path

from .komponenten import Adresse, GeschaeftsDaten, Notiz
from .kunde import Kunde
from .persistenz import KundenDatei
from .speicher import DateiSpeicher


def main() -> None:
    """Legt zwei Kunden an, speichert, laedt neu und zeigt das Ergebnis."""
    with tempfile.TemporaryDirectory() as ordner:
        pfad = str(Path(ordner) / "kunden.json")

        with KundenDatei(DateiSpeicher(pfad)) as kunden:
            anna = Kunde(
                "Anna Beispiel",
                "anna@example.de",
                geschaefts_daten=GeschaeftsDaten("Beispiel GmbH", "DE123456789"),
                adresse=Adresse("Hauptstrasse", "1", "10115", "Berlin"),
            )
            anna.umsatz = 150_000
            anna.komponente_hinzufuegen(Notiz("Rueckruf nach 16 Uhr"))
            kunden.hinzufuegen(anna)

            bob = Kunde("Bob Muster", "bob@example.de")
            bob.umsatz = 900
            bob.sperren()
            kunden.hinzufuegen(bob)

        print(f"Gespeichert in {Path(pfad).name} (und {Path(pfad).stem}.notizen.json)\n")

        with KundenDatei(DateiSpeicher(pfad)) as kunden:
            print("Neu geladen, nach Umsatz sortiert:")
            for kunde in sorted(kunden, reverse=True):
                print(f"  {kunde}")
            print(f"\n{kunden[0].info()}")


if __name__ == "__main__":
    main()
