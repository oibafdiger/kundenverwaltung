"""Fehlerhierarchie der Kundenverwaltung.

Eine Basisklasse, sechs Unterklassen, keine Zwischenebene. Wer
KundenverwaltungError faengt, faengt alles aus diesem Paket — und nur das."""


class KundenverwaltungError(Exception):
    """Basis aller fachlichen Fehler der Kundenverwaltung.

    Wer diesen Typ faengt, faengt alles, was dieses Modul selbst als Fehler
    meldet — und nur das. Programmierfehler wie TypeError oder AttributeError
    bleiben absichtlich draussen und schlagen durch: Sie sind Bugs, keine
    Fachfehler, und sollen auffallen statt behandelt zu werden.

    Geerbt wird von Exception, nicht von BaseException. BaseException umfasst
    auch KeyboardInterrupt und SystemExit — "das Programm soll enden"-Signale,
    die ein gewoehnliches `except Exception` absichtlich NICHT erwischt. Wer
    von BaseException erbt, landet in derselben Kategorie und wird von
    normalen Handlern nicht mehr gefangen.
    """


class KundeNichtGefundenError(KundenverwaltungError):
    """Unter der gesuchten Kundennummer existiert kein Kunde.

    Wurfstelle: Kundenliste.finde(nummer). Wer nur wissen will, OB ein Kunde
    enthalten ist, nimmt stattdessen `in` — dann faellt kein Fehler an.
    """


class UnbekannteKomponenteError(KundenverwaltungError):
    """Zu einem Registry-Schluessel ist keine Komponentenklasse eingetragen.

    Betrifft InfoLieferant.erzeugt(). Der Schluessel kommt typischerweise aus
    Konfiguration oder Benutzereingabe, ist also nicht zwingend ein Bug —
    deshalb ein Fachfehler und kein KeyError nach aussen.
    """


class UngueltigeEmailError(KundenverwaltungError):
    """Die uebergebene Adresse erfuellt die Email-Regeln nicht.

    Der Kunde wird damit nicht angelegt bzw. die Adresse nicht geaendert; der
    bisherige Wert bleibt unveraendert. Wer den Fehler faengt, kann eine
    korrigierte Adresse nachreichen.
    """


class UngueltigerNameError(KundenverwaltungError):
    """Der Kundenname ist leer oder besteht nur aus Leerzeichen.

    Geprueft wird im Konstruktor, nicht in einem Setter: name ist bewusst
    read-only, weil ExportierbarMixin.name als read-only Property darauf
    aufbaut. Ein Kunde ohne Namen soll gar nicht erst entstehen.
    """


class UngueltigerBetragError(KundenverwaltungError):
    """Ein Geldbetrag ist zwar eine Zahl, aber inhaltlich unzulaessig.

    Aktuell: negative Umsaetze. Abgrenzung zum TypeError — ein Betrag vom
    falschen Typ ist ein Programmierfehler, ein negativer Betrag eine
    fachliche Regelverletzung.
    """


class CsvFormatError(KundenverwaltungError):
    """Eine CSV-Zeile laesst sich nicht zu einem Kunden verarbeiten.

    Deckt beide Parserfehler ab: falsche Feldanzahl und ein Umsatzfeld, das
    keine Zahl ist. Beide haben dieselbe Ursache — kaputte Eingabedaten — und
    denselben sinnvollen Umgang: Zeile melden und ueberspringen. Ein Aufrufer,
    der eine Datei einliest, braucht deshalb nur einen except-Zweig.

    Achtung: Nicht jeder Fehler aus aus_csv_zeile ist einer davon. Eine Zeile
    mit ungueltiger Email wirft UngueltigeEmailError, weil der Fehler aus dem
    email-Setter kommt. Wer wirklich jede kaputte Zeile abfangen will, faengt
    KundenverwaltungError.
    """
