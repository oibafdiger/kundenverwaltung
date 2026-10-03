"""Kundenliste: ein Container, der sich wie ein eingebauter anfuehlt.

Seit Woche 12 nur noch das. Das Schreiben und Lesen der JSON-Datei ist nach
speicher.py umgezogen — ein Wechsel des Speichers ist ein anderer
Aenderungsgrund als eine neue Container-Methode. Geblieben ist die Umwandlung
in ein dict und zurueck (als_dict/aus_dict). Dass die mit ihrem
{"version": ...}-Umschlag streng genommen auch schon Wissen ueber die DATEI
ist, steht als P2b in REFACTORING.md."""

from collections.abc import Iterator
from typing import Any, overload

from .exceptions import (
    DateiInhaltError,
    KundeNichtGefundenError,
)
from .kunde import Kunde


# ============================================================================
# Container (Woche 6, Donnerstag)
# ============================================================================
class Kundenliste:
    """Eine Sammlung von Kunden, die sich wie ein eingebauter Container anfuehlt.

    Komposition, nicht Vererbung: Die Kunden liegen in einem Feld, die Klasse
    erbt NICHT von list. Dieselbe Entscheidung wie in Woche 4 — beim Erben
    kaemen saemtliche list-Methoden mit, auch die, die hier nichts zu suchen
    haben (sort, clear, insert, __iadd__ ...). So bleibt hinzufuegen() der
    einzige Schreibzugriff.

    Vier Dunder machen den Container aus: __len__, __getitem__, __contains__
    und __iter__. Die letzten beiden waeren nicht zwingend noetig — was sie
    trotzdem beitragen, steht bei ihnen.
    """

    def __init__(self, kunden: "list[Kunde] | None" = None) -> None:
        # list(...) macht eine flache Kopie: die Liste ist neu, die Kunden
        # darin sind dieselben Objekte. Ohne die Kopie zeigten Aufrufer und
        # Kundenliste auf dasselbe Listenobjekt — wer die uebergebene Liste
        # anfasst, veraenderte sonst die Kundenliste gleich mit.
        self._kunden: list[Kunde] = list(kunden) if kunden is not None else []


    def hinzufuegen(self, kunde: Kunde) -> None:
        """Haengt einen Kunden hinten an.

        Bewusst der einzige Schreibzugriff: Wer Kunden aufnehmen will, geht
        hier durch. Beim Erben von list waeren daneben append, extend,
        insert, __iadd__ und Konsorten offen — genau das sollte die
        Komposition verhindern.
        """
        self._kunden.append(kunde)

    def finde(self, nummer: int) -> Kunde:
        """Sucht den Kunden mit der angegebenen Nummer.

        Wirft KundeNichtGefundenError, wenn keiner passt — die Klasse hatte
        seit Woche 7 keine Wurfstelle und war damit ein Versprechen, das der
        Code nicht einloest.

        Entscheidung: werfen statt None zurueckgeben. Wer eine Nummer
        nachschlaegt, erwartet einen Kunden. Ein None waere ein zweiter
        Rueckgabetyp, den jeder Aufrufer abfangen muesste — und wer es
        vergisst, bekommt den Fehler erst spaeter als AttributeError an ganz
        anderer Stelle. Wer nur wissen will, OB es den Kunden gibt, nimmt
        stattdessen `in`.
        """
        for kunde in self._kunden:
            if kunde.nummer == nummer:
                return kunde
        raise KundeNichtGefundenError(
            f"Keine Kundennummer {nummer!r} in dieser Liste "
            f"({len(self._kunden)} Eintraege)"
        )

    def __len__(self) -> int:
        return len(self._kunden)

    @overload
    def __getitem__(self, index: int) -> Kunde: ...

    @overload
    def __getitem__(self, index: slice) -> "Kundenliste": ...

    def __getitem__(self, index: "int | slice") -> "Kunde | Kundenliste":
        """Einzelzugriff liefert einen Kunden, ein Slice eine neue Kundenliste.

        Ein Ausschnitt aus einer Kundenliste soll wieder eine Kundenliste
        sein — so verhalten sich auch die eingebauten Typen. Ohne die
        Fallunterscheidung kaeme bei `liste[1:3]` eine nackte list zurueck,
        und am Ausschnitt waere keine Methode dieser Klasse mehr verfuegbar.
        """
        if isinstance(index, slice):
            return Kundenliste(self._kunden[index])
        return self._kunden[index]


    def __contains__(self, item: object) -> bool:
        """Mitgliedschaft per ==, also ueber die Kundennummer.

        EHRLICH ZUM STAND: Diese Fassung delegiert an list.__contains__ und
        tut damit genau dasselbe wie der eingebaute Fallback — ein linearer
        Durchlauf. Sie steht hier als Platz fuer den naechsten Schritt: ein
        gepflegtes set der Kundennummern wuerde in einem Schritt antworten
        statt in n. Als Ausgangspunkt in Ordnung, aber noch kein Gewinn.

        Der Parametertyp ist object, weil `x in liste` mit jedem Typ gefragt
        werden darf. Ein isinstance-Wachposten ist trotzdem nicht noetig, weil
        Kunde.__eq__ fuer Fremdtypen NotImplemented liefert und Python dann
        auf den Identitaetsvergleich zurueckfaellt.
        """
        return item in self._kunden

    def __iter__(self) -> Iterator[Kunde]:
        """Liefert bei jedem Aufruf einen frischen Iterator ueber die Kunden.

        Drei Varianten koennen hier stehen und sind alle korrekt:

            a) return iter(self._kunden)                 1 Zeile
            b) return KundenlisteIterator(self._kunden)  1 Zeile + eigene Klasse
            c) yield from self._kunden                   1 Zeile (Generator)

        Geblieben ist (a). Die Iteration dieser Klasse IST die Iteration ihrer
        Liste — dann soll der Code genau das sagen. (b) steht als Lerncode
        unten in der Datei: von Hand gebaut, aber hier nicht verdrahtet, weil
        eine eigene Klasse nur lohnt, wenn der Iterator mehr kann als
        mitzaehlen. (c) waere die Wahl, sobald beim Durchlaufen gefiltert oder
        umgeformt werden soll — dafuer muesste sich an der Signatur nichts
        aendern, nur der Rumpf.
        """
        return iter(self._kunden)


    def __repr__(self) -> str:
        return f"Kundenliste({self._kunden!r})"

    # ------------------------------------------------------------------
    # Serialisierung (Woche 9, Montag)
    # ------------------------------------------------------------------
    # Entschieden am 11.09.2026: Variante B, ein dict mit Versionsfeld, statt
    # einer nackten Liste. Die Begruendung steht im Docstring von als_dict().
    #
    # Version 2 (Woche 10, Freitag): Kunden speichern "zustand" statt "aktiv".
    # Genau fuer so eine Aenderung war das Versionsfeld gedacht. Version 1 wird
    # weiterhin gelesen, alte Dateien bleiben benutzbar und werden beim
    # naechsten Speichern von selbst zu Version 2.
    #
    # Ein Tupel statt eines sets: `in` vergleicht dort mit ==. Bei einem set
    # wuerde eine kaputte Datei mit "version": [1] einen nackten TypeError
    # (unhashable) werfen statt einer verstaendlichen Meldung.
    FORMAT_VERSION = 2
    LESBARE_VERSIONEN = (1, 2)

    def als_dict(self) -> dict[str, Any]:
        """Die ganze Liste als dict — mit Versionsnummer davor.

        Die naheliegende Alternative waere eine nackte Liste gewesen:

            [ {...}, {...} ]          statt   {"version": 1, "kunden": [...]}

        Die Zeile extra kauft zwei Dinge:

        1. Das Format kann sich aendern. Benennst du in Woche 10 ein Feld um,
           liegen alte Dateien noch auf der Platte. Mit Versionsfeld kann
           aus_dict() das SEHEN und eine klare Meldung geben. Ohne bekommst du
           irgendwo tief drin einen KeyError, der nicht verraet, dass die
           Datei einfach alt ist.

        2. Es ist Platz fuer das, was spaeter dazukommt — der Notizspeicher
           vom Dienstag zum Beispiel. Eine nackte Liste hat keinen Platz fuer
           ein zweites Feld; man muesste das Format dann brechen.

        Der Preis ist eine Verschachtelungsebene beim Lesen der Datei. Das ist
        bei etwas, das Jahre ueberdauern soll, ein guter Tausch.

        Eingetreten in Woche 10: Aus "aktiv" wurde "zustand". Weil die Datei
        ihre Version mitbringt, lassen sich alte Dateien (Version 1) weiter
        lesen, statt an einem fehlenden Feld zu scheitern.
        """
        return {
            "version": Kundenliste.FORMAT_VERSION,
            "kunden": [kunde.als_dict() for kunde in self._kunden],
        }

    @classmethod
    def aus_dict(cls, daten: dict[str, Any]) -> "Kundenliste":
        """Baut die Liste zurueck und prueft vorher die Formatversion.

        Die Pruefung steht ganz vorn, vor jedem Zugriff auf "kunden": Eine
        Datei aus der Zukunft (Version 2, von einer neueren Programmfassung
        geschrieben) soll eine verstaendliche Meldung geben und nicht an
        einem fehlenden Feld stolpern.

        Die Typpruefung ganz oben faengt einen Fall ab, den json.load()
        klaglos durchlaesst: eine Datei, die eine LISTE enthaelt statt eines
        Objekts — etwa aus der Zeit, bevor das Versionsfeld eingefuehrt
        wurde. `daten.get(...)` wuerde daran mit AttributeError scheitern,
        und der ist kein Fachfehler.

        Der Parametertyp sagt dict, der Code prueft trotzdem. Kein
        Widerspruch: mypy prueft den Quelltext, eine JSON-Datei ist zur
        Laufzeit da. An der Vertrauensgrenze zaehlt, was ankommt, nicht was
        angekuendigt war.
        """
        if not isinstance(daten, dict):
            raise DateiInhaltError(
                f"Erwartet wird ein JSON-Objekt, gefunden wurde "
                f"{type(daten).__name__}"
            )

        version = daten.get("version")
        if version not in cls.LESBARE_VERSIONEN:
            raise DateiInhaltError(
                f"Unbekannte Formatversion {version!r}, lesbar sind "
                f"{list(cls.LESBARE_VERSIONEN)}. Stammt die Datei aus einer "
                f"anderen Programmfassung?"
            )

        try:
            eintraege = daten["kunden"]
        except KeyError as e:
            raise DateiInhaltError("Feld 'kunden' fehlt in der Datei") from e

        return cls([Kunde.aus_dict(eintrag) for eintrag in eintraege])


# ============================================================================
# Kuer Woche 6: der Iterator eine Ebene tiefer, von Hand gebaut
# ============================================================================
class KundenlisteIterator:
    """Haelt die Position beim Durchlaufen einer Kundenliste.

    LERNCODE — nicht verdrahtet. Kundenliste.__iter__ delegiert bewusst an
    iter(self._kunden); diese Klasse baut nach, was dabei intern passiert.
    Eine eigene Iterator-Klasse lohnt erst, wenn der Iterator mehr kann als
    mitzaehlen: eigene Methoden (peek), Filterlogik mit Zustand, oder wenn er
    unabhaengig vom Container weitergereicht werden soll.

    Arbeitsteilung: Die Kundenliste weiss, WAS drin ist. Der Iterator weiss,
    WO man gerade steht. Deshalb sind es zwei Objekte und nicht eines — die
    kuerzere Fassung mit der Position im Container laesst keine zwei
    gleichzeitigen Durchlaeufe zu.
    """

    def __init__(self, kunden: list[Kunde]) -> None:
        self._kunden = kunden
        self._position = 0

    def __iter__(self) -> "KundenlisteIterator":
        """Ein Iterator ist selbst iterierbar und gibt sich selbst zurueck."""
        return self

    def __next__(self) -> Kunde:
        """Liefert das naechste Element, sonst StopIteration.

        Geprueft wird per Laengenvergleich (LBYL) statt per
        try/except IndexError (EAFP). Grund: try/except faenge JEDEN
        IndexError, auch einen aus ganz anderer Ursache — der Iterator
        meldete dann "fertig", obwohl in Wirklichkeit ein Bug vorliegt.
        Dasselbe Muster wie bei info_eafp(). Und len() ist billig.
        """
        if self._position >= len(self._kunden):
            raise StopIteration
        kunde = self._kunden[self._position]
        self._position += 1
        return kunde
