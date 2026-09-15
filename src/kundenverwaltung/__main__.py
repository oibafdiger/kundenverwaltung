"""Einstiegspunkt fuer `python -m kundenverwaltung` (Woche 11).

`python -m paket` sucht im Paket nach __main__.py und fuehrt es aus. Die Datei
ist deshalb nur eine Weiterleitung: Die eigentliche Vorfuehrung steht in
main.py, damit sie sich auch importieren und testen laesst.
"""

from .main import main

if __name__ == "__main__":
    main()
