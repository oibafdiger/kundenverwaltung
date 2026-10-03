"""Fehlerhierarchie der Kundenverwaltung.

Eine Basisklasse, zehn Unterklassen, keine Zwischenebene. Wer
KundenverwaltungError faengt, faengt alles aus diesem Paket — und nur das.

Die drei Datei-Fehler sind absichtlich getrennt: DateiNichtGefundenError
ist der einzige, auf den ein Aufrufer sinnvoll REAGIEREN kann (beim ersten
Programmstart gibt es noch nichts), die anderen beiden bedeuten abbrechen."""


# ============================================================================
# Exceptions (Woche 7, Montag)
# ============================================================================
# Flache Hierarchie: eine Basis, fuenf Unterklassen, keine Zwischenebene.
# Eine Zwischenebene (etwa CsvError ueber CsvFormatError) lohnt erst, wenn es
# einen Aufrufer gibt, der genau dort fangen will UND dort alles bekommt, was
# er braucht. Bei "alles rund um CSV" waere das hier nicht der Fall:
# aus_csv_zeile baut einen Kunden und loest dabei auch den email-Setter aus —
# eine Zeile mit kaputter Email wirft UngueltigeEmailError, nicht CsvError.
# Die Gruppierung nach Herkunft waere also undicht.


class KundenverwaltungError(Exception):
    """Basis aller fachlichen Fehler der Kundenverwaltung.

    Wer diesen Typ faengt, faengt alles, was dieses Modul selbst als Fehler
    meldet — und nur das. Programmierfehler wie TypeError oder AttributeError
    bleiben absichtlich draussen und schlagen durch: Sie sind Bugs, keine
    Fachfehler, und sollen auffallen statt behandelt zu werden.

    Geerbt wird von Exception, nicht von BaseException — sonst laege diese
    Hierarchie in derselben Kategorie wie KeyboardInterrupt und wuerde von
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


class UngueltigeAdresseError(KundenverwaltungError):
    """Eine Adresse hat ein leeres oder fehlendes Feld.

    Wurfstelle: Adresse.__post_init__ — also beim Bauen, bei replace() und
    beim Laden aus einer Datei, weil alle drei ueber __init__ laufen.

    Geprueft wird nur, ob jedes Feld ein nicht-leerer Text ist, keine
    PLZ-Formate: Die Klasse soll kaputte Daten abweisen, nicht Postregeln
    einzelner Laender kennen. Wer den Fehler faengt, kann die Adresse
    korrigiert neu anlegen. Weil er zur Hierarchie gehoert, muss ihn das
    Laden aus einer Datei nicht erst uebersetzen.
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


# Zuordnung der bestehenden Wurfstellen — Umbau am Dienstag:
#
#   InfoLieferant.erzeugt   unbekannter Schluessel  ->  UnbekannteKomponenteError
#   aus_csv_zeile           falsche Feldanzahl      ->  CsvFormatError
#   aus_csv_zeile           Umsatz keine Zahl       ->  CsvFormatError
#   email-Setter            ungueltige Email        ->  UngueltigeEmailError
#   umsatz-Setter           negativer Betrag        ->  UngueltigerBetragError
#   aktiv-Setter            kein bool               ->  TypeError  (siehe unten)
#
# Der aktiv-Setter prueft mit isinstance den TYP, nicht den Wert. Python
# trennt das: falscher Typ -> TypeError, richtiger Typ mit unzulaessigem Wert
# -> ValueError. `aktiv = "ja"` ist ein Programmierfehler am Aufrufort, kein
# Fachfehler der Kundenverwaltung — die Stelle gehoert deshalb NICHT in diese
# Hierarchie. Nicht jeder Fehler ist ein Fachfehler.
#
# Kein Miterben von ValueError: Die Unterklassen erben ausschliesslich von
# KundenverwaltungError, damit die Hierarchie die einzige Wahrheit ist. Preis
# dafuer war, jede `except ValueError`-Stelle in den Tests mitzuziehen — was
# ohnehin gut ist, weil jeder Test dann benennt, welchen Fehler er erwartet.


# ============================================================================
# Dateizugriff (Woche 9, Dienstag)
# ============================================================================
# Drei Klassen, nicht eine und nicht fuenf. Die Regel aus Woche 7: Eine
# eigene Klasse lohnt, wenn ein Aufrufer genau dort fangen will UND dann
# etwas anderes tut als bei den Nachbarn.
#
#   DateiNichtGefundenError  Klar begruendet: Beim ERSTEN Programmstart gibt
#                            es die Datei noch nicht. Das ist kein Fehler,
#                            sondern der Normalfall — der Aufrufer faengt
#                            und startet mit einer leeren Liste. Der
#                            Kontextmanager am Mittwoch braucht genau das.
#
#   DateiNichtLesbarError    Datei da, aber das Betriebssystem gibt sie nicht
#                            her: Verzeichnis statt Datei, keine Rechte,
#                            defekter Datentraeger. Nicht behebbar, abbrechen.
#
#   DateiInhaltError         Gelesen, aber unbrauchbar: kein gueltiges JSON,
#                            falsche Formatversion, fehlendes Pflichtfeld.
#                            Ebenfalls abbrechen — und zwar unbedingt, denn
#                            Weitermachen hiesse hier Datenverlust.
#
# Ehrlich zur Grenze zwischen den letzten beiden: Ein Aufrufer reagiert auf
# beide gleich (abbrechen), nach der strengen Lesart der Regel koennte man
# sie also zusammenlegen. Getrennt geblieben sind sie, weil die DIAGNOSE
# verschieden ist — "repariere dein Dateisystem" gegen "repariere deine
# Daten" — und weil ein Reparaturwerkzeug bei kaputtem Inhalt noch etwas
# retten koennte, bei einem unlesbaren Datentraeger nicht. Zusammenlegen
# waere spaeter billig, Auseinanderziehen teurer.


class DateiNichtGefundenError(KundenverwaltungError):
    """Unter dem angegebenen Pfad liegt keine Datei.

    Wurfstellen: Kundenliste.laden(), NotizSpeicher.laden().

    Der einzige Dateifehler, der regulaer vorkommt statt etwas anzuzeigen,
    was schiefging: Beim ersten Programmstart existiert noch nichts. Wer
    diesen Fehler faengt, faengt typischerweise mit einer leeren Liste an —
    siehe KundenDatei (Mittwoch). Deshalb steht er getrennt von
    DateiNichtLesbarError, obwohl beide aus derselben OSError-Familie kommen.
    """


class DateiNichtLesbarError(KundenverwaltungError):
    """Die Datei existiert, das Betriebssystem gibt sie aber nicht her.

    Wurfstellen: Kundenliste.speichern()/laden(), NotizSpeicher entsprechend.

    Faelle: ein Verzeichnis statt einer Datei, fehlende Rechte, ein
    schreibgeschuetzter oder voller Datentraeger. Alle nicht aus dem Programm
    heraus behebbar — hier hilft nur eine Meldung an den Benutzer.
    """


class DateiInhaltError(KundenverwaltungError):
    """Die Datei war lesbar, ihr Inhalt ist aber nicht verwertbar.

    Wurfstellen: Kundenliste.laden() und aus_dict(), Kunde.aus_dict().

    Deckt drei Stufen des Scheiterns ab, die alle dieselbe Reaktion
    verlangen — abbrechen, nichts ueberschreiben:

        kein gueltiges JSON      die Datei ist abgeschnitten oder verfremdet
        falsche Formatversion    von einer anderen Programmfassung geschrieben
        fehlendes Pflichtfeld    JSON in Ordnung, Struktur nicht

    Warum nicht CsvFormatError mitbenutzen? Der Name wuerde luegen — hier ist
    kein CSV im Spiel. Ein Fehlername, der die Herkunft falsch angibt, kostet
    beim naechsten Debuggen mehr als eine zusaetzliche Klasse.
    """
